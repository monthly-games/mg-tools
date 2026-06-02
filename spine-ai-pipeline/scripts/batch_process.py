import os
import sys
import argparse
import subprocess
import json
import importlib
import time
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, TextColumn

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

quality_gate_module = importlib.import_module("lib.quality_gate")
QualityGate = getattr(quality_gate_module, "QualityGate")
QualityGateResult = getattr(quality_gate_module, "QualityGateResult")
QualityLevel = getattr(quality_gate_module, "QualityLevel")

console = Console()

_split_with_sam = None
_matting_engine = None
_inpainting_engine = None  # B-3: LamaClient 공유 인스턴스 (lazy 초기화)


class PipelineException(Exception):
    pass

STEP_TIMEOUT_SECONDS = 600  # 단계별 최대 10분 (hang 방지)


def run_step(step_name: str, command: str, cwd: str, timeout: int = STEP_TIMEOUT_SECONDS) -> bool:
    """단일 파이프라인 단계를 실행합니다.

    Args:
        step_name: 로그에 표시할 단계 이름.
        command: 실행할 셸 명령어.
        cwd: 작업 디렉토리.
        timeout: subprocess 실행 최대 시간(초). 기본 10분.
                 초과 시 프로세스를 강제 종료하고 False를 반환합니다.

    Returns:
        True if the step succeeded, False otherwise.
    """
    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return True
    except subprocess.TimeoutExpired:
        console.print(
            f"[red]Timeout {step_name}: exceeded {timeout}s — worker freed[/red]"
        )
        return False
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed {step_name}: {e}[/red]")
        console.print(f"[dim]{e.stderr.decode(errors='ignore')}[/dim]")
        return False


def run_split_parts_with_lama(image_path: Path, output_dir: Path) -> bool:
    """Run split_parts with LaMa ONNX as the primary inpainting path.

    B-3 fix: inpainting_engine을 None 대신 LamaClient 인스턴스로 주입합니다.
    LamaClient는 ONNX 세션이 없으면 원본 이미지를 반환하므로 안전합니다 (B-5).
    """
    global _split_with_sam
    global _matting_engine
    global _inpainting_engine

    try:
        if _split_with_sam is None:
            script_dir = Path(__file__).parent
            if str(script_dir) not in sys.path:
                sys.path.append(str(script_dir))

            split_parts_module = importlib.import_module("split_parts")
            _split_with_sam = getattr(split_parts_module, "split_with_sam")

        if _matting_engine is None:
            matting_module = importlib.import_module("utils.matting")
            MattingEngine = getattr(matting_module, "MattingEngine")
            _matting_engine = MattingEngine()

        # B-3 fix: LamaClient lazy 초기화 (기존 None → 실제 엔진 주입)
        if _inpainting_engine is None:
            try:
                lama_module = importlib.import_module("lib.lama_client")
                LamaClient = getattr(lama_module, "LamaClient")
                _inpainting_engine = LamaClient()
            except Exception as lama_err:
                console.print(f"[yellow]  LaMa init failed (graceful degradation): {lama_err}[/yellow]")
                _inpainting_engine = None  # B-5: None이면 LamaClient.inpaint()가 원본 반환

        result = _split_with_sam(
            image_path,
            output_dir,
            matting_engine=_matting_engine,
            inpainting_engine=_inpainting_engine,  # B-3 fix: None → LamaClient
            post_process=True,
        )

        return bool(result and result.get("success"))
    except Exception as e:
        console.print(f"[yellow]  LaMa split path failed: {e}[/yellow]")
        return False


def load_json(path: Path):
    if not path.exists():
        raise PipelineException(f"Missing file: {path}")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def report_quality(result):
    color_map = {
        QualityLevel.PASS: "green",
        QualityLevel.WARN: "yellow",
        QualityLevel.FAIL: "red",
    }

    color = color_map.get(result.level, "white")
    metrics = ", ".join(
        [
            f"{key}={value:.3f}" if isinstance(value, float) else f"{key}={value}"
            for key, value in sorted(result.metrics.items())
        ]
    )

    console.print(
        f"[{color}]  QualityGate {result.stage.upper()} {result.level.value.upper()}"
        + (f" ({metrics})" if metrics else "")
        + f"[/{color}]"
    )

    for issue in result.issues:
        console.print(f"[{color}]    - {issue}[/{color}]")


def enforce_quality_gate(result, block_on_warn=False):
    report_quality(result)

    if result.level == QualityLevel.FAIL:
        raise PipelineException(f"{result.stage} failed quality gate")

    if block_on_warn and result.level == QualityLevel.WARN:
        raise PipelineException(f"{result.stage} produced WARN; PASS required for deployment")


def process_single_image(img_path_str, output_base_str, template, venv_python):
    """Process a single image through the full Spine AI pipeline.

    Designed to run in a worker process (ProcessPoolExecutor).
    All arguments are plain strings to ensure pickle compatibility.

    Args:
        img_path_str: Path to input image (str for pickle safety).
        output_base_str: Base output directory.
        template: Rig template name or None.
        venv_python: Path to venv python executable.

    Returns:
        dict: {name, status, quality, error, duration_s}
              status/quality: "pass" | "warn" | "fail" | "error"
    """
    start = time.time()
    img_path = Path(img_path_str)
    name = img_path.stem
    output_base = Path(output_base_str)
    cwd = str(SCRIPT_DIR.parent)
    worst_quality = "pass"

    # Paths
    char_out_dir = output_base / name
    parts_dir = char_out_dir / "parts"
    spine_dir = char_out_dir / "spine"
    char_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 2. Split Parts (YOLO-World + MODNet + LaMa ONNX inpainting)
        # Pass original 'img_path' so MODNet has full context.
        if not parts_dir.exists() or len(list(parts_dir.glob("*.png"))) < 3:
            if not run_split_parts_with_lama(img_path, parts_dir):
                # Fallback keeps existing split_parts subprocess behavior.
                cmd_split = f'"{venv_python}" scripts/split_parts.py --input "{img_path}" --output "{parts_dir}"'
                if not run_step("Split Parts", cmd_split, cwd):
                    return {"name": name, "status": "fail", "quality": "fail",
                            "error": "Split Parts failed", "duration_s": time.time() - start}

        parts_metadata = load_json(parts_dir / "metadata.json")
        segmentation_gate = QualityGate.check_segmentation(parts_metadata, parts_dir=parts_dir)
        enforce_quality_gate(segmentation_gate)
        if segmentation_gate.level == QualityLevel.WARN:
            worst_quality = "warn"

        # 3. Rig
        rig_cmd_parts = [
            f'"{venv_python}"', 'scripts/rig_character.py',
            '--input', f'"{parts_dir}"',
            '--output', f'"{spine_dir}"'
        ]

        if template:
            rig_cmd_parts.extend(['--template', template])
        else:
            rig_cmd_parts.append('--use-api')

        cmd_rig = " ".join(rig_cmd_parts)

        if not run_step("Rigging", cmd_rig, cwd):
            return {"name": name, "status": "fail", "quality": "fail",
                    "error": "Rigging failed", "duration_s": time.time() - start}

        rig_skeleton = load_json(spine_dir / "skeleton.json")
        rigging_gate = QualityGate.check_rigging(rig_skeleton)
        enforce_quality_gate(rigging_gate)
        if rigging_gate.level == QualityLevel.WARN:
            worst_quality = "warn"

        # 3.5 AI Analysis (Gemini) - Determine Mood/Preset
        preset = "combat"
        analysis_result = {}

        if not template:
            pass

        try:
            # Lazy import to avoid dependency issues if not run
            sys.path.append(str(Path(__file__).parent))
            try:
                analyze_character_module = importlib.import_module("analyze_character")
                analyze_character = getattr(analyze_character_module, "analyze_character", None)
            except ImportError:
                analyze_character = None

            key_path = Path("config/gemini_key.txt")
            if key_path.exists() and analyze_character:
                with open(key_path, "r") as f:
                    api_key = f.read().strip()

                console.print(f"[dim]  Analyzing character with Gemini...[/dim]")
                # Use original image for analysis context
                analysis = analyze_character(str(img_path), api_key)

                if analysis and "preset" in analysis:
                    preset = analysis["preset"]
                    console.print(f"[magenta]  AI Director: Detected '{analysis.get('mood')}' -> Preset '{preset}'[/magenta]")
                    console.print(f"[dim]  Desc: {analysis.get('description')}[/dim]")

                analysis_result = analysis

                # Save analysis
                with open(char_out_dir / "analysis.json", "w", encoding="utf-8") as f:
                    json.dump(analysis, f, indent=2, ensure_ascii=False)
        except Exception as e:
            console.print(f"[yellow]  AI Analysis Failed: {e}[/yellow]")

        # 4. Animate (with AI preset)
        cmd_anim = f'"{venv_python}" scripts/animate_character.py --input "{spine_dir}" --preset {preset}'
        if not run_step("Animation", cmd_anim, cwd):
            return {"name": name, "status": "fail", "quality": "fail",
                    "error": "Animation failed", "duration_s": time.time() - start}

        final_skeleton = load_json(spine_dir / "skeleton.json")
        animation_gate = QualityGate.check_animation(final_skeleton)
        enforce_quality_gate(animation_gate)
        if animation_gate.level == QualityLevel.WARN:
            worst_quality = "warn"

        overall_gate = QualityGate.overall_gate(parts_metadata, final_skeleton, parts_dir=parts_dir)
        enforce_quality_gate(overall_gate, block_on_warn=True)

        # 5. Spine Export (Validation & Binary)
        # B-4 fix: export 실패를 단순 경고로 삼키지 않고 FAIL 처리합니다.
        # skeleton.json이 없으면 (export 전에 검증) 즉시 실패합니다.
        skeleton_json = spine_dir / "skeleton.json"
        if not skeleton_json.exists():
            return {
                "name": name, "status": "fail", "quality": "fail",
                "error": "skeleton.json missing before export step",
                "duration_s": time.time() - start,
            }

        try:
            # Lazy import
            sys.path.append(str(Path(__file__).parent))
            export_spine_module = importlib.import_module("export_spine")
            convert_json_to_binary = getattr(export_spine_module, "convert_json_to_binary")

            subprocess.run(f'copy "{parts_dir}\\*.png" "{spine_dir}\\"', shell=True, check=False, stdout=subprocess.DEVNULL)

            convert_json_to_binary(spine_dir)

        except Exception as e:
            # B-4 fix: export 실패 → FAIL 반환 (기존: 경고만 출력하고 성공으로 처리)
            console.print(f"[red]  Spine Export Failed: {e}[/red]")
            return {
                "name": name, "status": "fail", "quality": "fail",
                "error": f"Spine export failed: {e}",
                "duration_s": time.time() - start,
            }

        console.print(f"[blue]  [OK] Completed {name} (Mode: {preset})[/blue]")
        return {"name": name, "status": worst_quality, "quality": worst_quality,
                "error": None, "duration_s": time.time() - start}

    except PipelineException as e:
        console.print(f"[red]  Pipeline blocked for {name}: {e}[/red]")
        return {"name": name, "status": "fail", "quality": "fail",
                "error": str(e), "duration_s": time.time() - start}
    except Exception as e:
        return {"name": name, "status": "error", "quality": "fail",
                "error": str(e), "duration_s": time.time() - start}


def _print_result(result):
    """Print a single processing result with color coding."""
    status_color = {"pass": "green", "warn": "yellow", "fail": "red", "error": "red"}
    color = status_color.get(result["status"], "white")
    msg = f"  {result['name']}: {result['status'].upper()}"
    if result.get("error"):
        msg += f" - {result['error']}"
    if result.get("duration_s", 0) > 0:
        msg += f" ({result['duration_s']:.1f}s)"
    console.print(f"[{color}]{msg}[/{color}]")


def main():
    parser = argparse.ArgumentParser(description="Batch process images through Spine AI Pipeline")
    parser.add_argument("--input_dir", "--input", dest="input_dir", type=str, default="images", help="Input directory")
    parser.add_argument("--output_base", type=str, default="test/output/batch", help="Output base directory")
    parser.add_argument("--venv_python", type=str, default=r"d:\mg-games\repos\mg-tools\venv\Scripts\python.exe", help="Path to venv python")
    parser.add_argument("--template", type=str, help="Rig template to use (humanoid, monster, chibi)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Parallel workers (default: min(4, cpu_count))")
    parser.add_argument("--sequential", action="store_true",
                        help="Force sequential processing (original behavior)")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        console.print(f"[red]Input directory not found: {input_dir}[/red]")
        sys.exit(1)

    output_base = Path(args.output_base)
    output_base.mkdir(parents=True, exist_ok=True)

    # Filter images
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = [
        f for f in input_dir.iterdir()
        if f.suffix.lower() in extensions
        and "_nobg" not in f.name
        and "_clean" not in f.name
        and "다운로드" not in f.name  # Skip specific files if needed
    ]

    if not images:
        console.print("[yellow]No images found to process.[/yellow]")
        return

    console.print(f"[bold cyan]Found {len(images)} images to process.[/bold cyan]")

    # Determine worker count
    n_workers = args.workers if args.workers is not None else min(4, os.cpu_count() or 1)
    if args.sequential:
        n_workers = 1

    batch_start = time.time()
    results = []

    if args.sequential or n_workers <= 1:
        # Sequential mode (original behavior)
        console.print("[dim]Mode: sequential[/dim]")
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            transient=False,
        ) as progress:
            main_task = progress.add_task("[green]Batch Processing...", total=len(images))
            for img_path in images:
                progress.update(main_task, description=f"Processing {img_path.stem}...")
                result = process_single_image(
                    str(img_path), str(output_base), args.template, args.venv_python
                )
                results.append(result)
                _print_result(result)
                progress.advance(main_task)
    else:
        # Parallel mode (ProcessPoolExecutor)
        from concurrent.futures import ProcessPoolExecutor, as_completed

        console.print(f"[dim]Mode: parallel ({n_workers} workers)[/dim]")

        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {
                pool.submit(
                    process_single_image,
                    str(img), str(output_base), args.template, args.venv_python
                ): img
                for img in images
            }
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                transient=False,
            ) as progress:
                task = progress.add_task(
                    f"Processing {len(images)} images ({n_workers}w)...",
                    total=len(images),
                )
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=300)  # 5min timeout per image
                    except Exception as e:
                        img = futures[future]
                        result = {
                            "name": img.stem, "status": "error", "quality": "fail",
                            "error": str(e), "duration_s": 0,
                        }
                    results.append(result)
                    progress.advance(task)
                    _print_result(result)

    # Summary report
    total_time = time.time() - batch_start
    counts = {s: sum(1 for r in results if r['status'] == s) for s in ['pass', 'warn', 'fail', 'error']}
    console.print(
        f"\n[bold]Processed {len(results)}:[/bold] "
        f"[green]{counts['pass']} PASS[/green], "
        f"[yellow]{counts['warn']} WARN[/yellow], "
        f"[red]{counts['fail']} FAIL, {counts['error']} ERROR[/red] "
        f"({n_workers}w, {total_time:.0f}s)"
    )

    # Exit code: non-zero if any failures or errors
    if counts['fail'] + counts['error'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
