#!/usr/bin/env python3
"""
다수 캐릭터 일괄 생성 스크립트

사용법:
    python batch_generate.py --input characters.csv --output output/
    python batch_generate.py --input characters.json --game mg-game-0001
"""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

from rich.console import Console
from rich.progress import Progress, TaskID

console = Console()


def load_characters_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """CSV에서 캐릭터 목록 로드"""
    characters = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            characters.append(row)
    return characters


def load_characters_json(json_path: Path) -> List[Dict[str, Any]]:
    """JSON에서 캐릭터 목록 로드"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("characters", [])


def run_script(script_name: str, args: List[str]) -> bool:
    """스크립트 실행"""
    script_path = Path(__file__).parent / script_name
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        console.print(f"[red]타임아웃: {script_name}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]실행 오류: {e}[/red]")
        return False


def process_character(character: Dict[str, Any], output_dir: Path,
                      progress: Progress, task: TaskID) -> bool:
    """단일 캐릭터 처리"""
    char_id = character.get("character_id", "unknown")
    char_dir = output_dir / char_id

    console.print(f"\n[cyan]처리 중: {char_id}[/cyan]")

    # 1. 설정 파일 생성
    config_path = char_dir / "config.json"
    char_dir.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(character, f, indent=2, ensure_ascii=False)

    # 2. 일러스트 생성
    progress.update(task, description=f"[{char_id}] 일러스트 생성...")
    if not run_script("gen_illustration.py", ["--config", str(config_path),
                                               "--output", str(output_dir)]):
        console.print(f"[yellow]  일러스트 생성 스킵 (SD API 필요)[/yellow]")

    # 3. 파츠 분리
    progress.update(task, description=f"[{char_id}] 파츠 분리...")
    illustration_path = char_dir / "illustration.png"
    if illustration_path.exists():
        run_script("split_parts.py", ["--input", str(illustration_path),
                                       "--output", str(char_dir / "parts")])

    # 4. 리깅 생성
    progress.update(task, description=f"[{char_id}] 리깅 생성...")
    parts_dir = char_dir / "parts"
    if parts_dir.exists():
        run_script("rig_character.py", ["--input", str(parts_dir),
                                         "--output", str(char_dir / "spine")])

    # 5. 애니메이션 추가
    progress.update(task, description=f"[{char_id}] 애니메이션...")
    spine_dir = char_dir / "spine"
    if spine_dir.exists():
        preset = character.get("animation_preset", "combat")
        run_script("animate_character.py", ["--input", str(spine_dir),
                                             "--preset", preset])

    progress.advance(task)
    return True


def main():
    parser = argparse.ArgumentParser(description="캐릭터 일괄 생성")
    parser.add_argument("--input", type=str, required=True,
                        help="캐릭터 목록 파일 (CSV 또는 JSON)")
    parser.add_argument("--output", type=str, default="output",
                        help="출력 경로")
    parser.add_argument("--game", type=str,
                        help="대상 게임 레포")
    parser.add_argument("--skip-existing", action="store_true",
                        help="이미 존재하는 캐릭터 스킵")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        console.print(f"[red]파일을 찾을 수 없습니다: {input_path}[/red]")
        return

    # 캐릭터 목록 로드
    if input_path.suffix == ".csv":
        characters = load_characters_csv(input_path)
    else:
        characters = load_characters_json(input_path)

    console.print(f"[blue]총 {len(characters)}개 캐릭터 처리 예정[/blue]")

    # 일괄 처리
    success_count = 0
    with Progress() as progress:
        task = progress.add_task("[green]처리 중...", total=len(characters))

        for character in characters:
            char_id = character.get("character_id", "unknown")

            if args.skip_existing and (output_dir / char_id / "spine").exists():
                console.print(f"[yellow]스킵: {char_id} (이미 존재)[/yellow]")
                progress.advance(task)
                continue

            if process_character(character, output_dir, progress, task):
                success_count += 1

    console.print(f"\n[green]완료: {success_count}/{len(characters)}개 성공[/green]")


if __name__ == "__main__":
    main()
