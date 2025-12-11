#!/usr/bin/env python3
"""
Spine 프로젝트 최종 출력 및 게임 레포 배포 스크립트

사용법:
    python export_spine.py --input char_001 --game mg-game-0001
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Any

from rich.console import Console

console = Console()


def copy_spine_assets(source_dir: Path, target_dir: Path) -> Dict[str, Any]:
    """Spine 에셋 복사"""
    try:
        target_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []
        for file_path in source_dir.glob("*"):
            if file_path.is_file():
                target_path = target_dir / file_path.name
                shutil.copy2(file_path, target_path)
                copied_files.append(file_path.name)

        return {"success": True, "files": copied_files}

    except Exception as e:
        console.print(f"[red]복사 실패: {e}[/red]")
        return {"success": False, "error": str(e)}


def generate_thumbnail(spine_dir: Path, output_path: Path) -> bool:
    """썸네일 생성 (플레이스홀더)"""
    # TODO: Spine CLI 또는 Viewer를 사용한 썸네일 생성
    console.print("[yellow]썸네일 생성: Spine CLI 연동 필요[/yellow]")
    return False


def optimize_images(target_dir: Path) -> Dict[str, Any]:
    """이미지 최적화 (플레이스홀더)"""
    # TODO: tinypng CLI 또는 pngquant 연동
    console.print("[yellow]이미지 최적화: tinypng/pngquant 연동 필요[/yellow]")
    return {"success": True, "optimized": 0}


def create_manifest(character_id: str, spine_dir: Path) -> Dict[str, Any]:
    """에셋 매니페스트 생성"""
    manifest = {
        "character_id": character_id,
        "type": "spine",
        "files": [],
        "animations": [],
    }

    # 파일 목록
    for file_path in spine_dir.glob("*"):
        if file_path.is_file():
            manifest["files"].append({
                "name": file_path.name,
                "size": file_path.stat().st_size,
            })

    # 애니메이션 목록 (skeleton.json에서 추출)
    skeleton_path = spine_dir / "skeleton.json"
    if skeleton_path.exists():
        with open(skeleton_path, "r", encoding="utf-8") as f:
            skeleton = json.load(f)
            manifest["animations"] = list(skeleton.get("animations", {}).keys())

    manifest_path = spine_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Spine 프로젝트 출력")
    parser.add_argument("--input", type=str, required=True, help="캐릭터 폴더")
    parser.add_argument("--game", type=str, help="대상 게임 레포 (예: mg-game-0001)")
    parser.add_argument("--output", type=str, help="직접 출력 경로 지정")
    parser.add_argument("--optimize", action="store_true", help="이미지 최적화")
    parser.add_argument("--thumbnail", action="store_true", help="썸네일 생성")
    args = parser.parse_args()

    input_dir = Path(args.input)
    spine_dir = input_dir / "spine"

    if not spine_dir.exists():
        console.print(f"[red]Spine 폴더를 찾을 수 없습니다: {spine_dir}[/red]")
        return

    character_id = input_dir.name

    # 출력 경로 결정
    if args.output:
        target_dir = Path(args.output)
    elif args.game:
        # 게임 레포의 spine 폴더
        repos_dir = Path(__file__).parent.parent.parent.parent
        target_dir = repos_dir / args.game / "spine" / character_id
    else:
        target_dir = input_dir / "export"

    console.print(f"[blue]캐릭터: {character_id}[/blue]")
    console.print(f"[blue]출력: {target_dir}[/blue]")

    # 에셋 복사
    result = copy_spine_assets(spine_dir, target_dir)
    if not result.get("success"):
        console.print("[red][FAIL] Export failed[/red]")
        return

    console.print(f"[green][OK] Files copied: {len(result.get('files', []))}[/green]")

    # 이미지 최적화
    if args.optimize:
        optimize_images(target_dir)

    # 썸네일 생성
    if args.thumbnail:
        generate_thumbnail(target_dir, target_dir / "thumbnail.png")

    # 매니페스트 생성
    manifest = create_manifest(character_id, target_dir)
    console.print(f"[green][OK] Manifest created: {len(manifest['animations'])} animations[/green]")

    console.print(f"[green][OK] Export complete: {target_dir}[/green]")


if __name__ == "__main__":
    main()
