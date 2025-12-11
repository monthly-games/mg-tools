#!/usr/bin/env python3
"""
캐릭터 일러스트 파츠 자동 분리 스크립트

사용법:
    python split_parts.py --input illustration.png --output parts/
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from rich.console import Console

console = Console()

# 기본 파츠 정의
DEFAULT_PARTS = [
    "head",
    "body",
    "arm_L",
    "arm_R",
    "leg_L",
    "leg_R",
    "weapon",
]


def split_with_komiko(image_path: Path, output_dir: Path) -> Dict[str, Any]:
    """KomikoAI API를 사용한 파츠 분리 (플레이스홀더)"""
    # TODO: KomikoAI API 연동
    console.print("[yellow]KomikoAI API 연동 필요[/yellow]")
    return {"success": False, "method": "komiko"}


def split_with_sam(image_path: Path, output_dir: Path) -> Dict[str, Any]:
    """SAM (Segment Anything Model)을 사용한 파츠 분리 (플레이스홀더)"""
    # TODO: SAM 연동
    console.print("[yellow]SAM 연동 필요[/yellow]")
    return {"success": False, "method": "sam"}


def split_manual_template(image_path: Path, output_dir: Path) -> Dict[str, Any]:
    """템플릿 기반 수동 분리 (폴백)"""
    try:
        from PIL import Image

        img = Image.open(image_path)
        width, height = img.size

        # 간단한 그리드 기반 분리 (예시)
        parts_regions = {
            "head": (width * 0.3, 0, width * 0.7, height * 0.25),
            "body": (width * 0.2, height * 0.2, width * 0.8, height * 0.5),
            "arm_L": (0, height * 0.2, width * 0.3, height * 0.5),
            "arm_R": (width * 0.7, height * 0.2, width, height * 0.5),
            "leg_L": (width * 0.2, height * 0.5, width * 0.5, height),
            "leg_R": (width * 0.5, height * 0.5, width * 0.8, height),
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        parts_info = []

        for part_name, region in parts_regions.items():
            part_img = img.crop(tuple(int(x) for x in region))
            part_path = output_dir / f"{part_name}.png"
            part_img.save(part_path, "PNG")

            parts_info.append({
                "name": part_name,
                "file": f"{part_name}.png",
                "region": list(region),
            })

        # 메타데이터 저장
        metadata = {
            "source": str(image_path),
            "method": "template",
            "parts": parts_info,
        }

        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return {"success": True, "method": "template", "parts": parts_info}

    except Exception as e:
        console.print(f"[red]분리 실패: {e}[/red]")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="캐릭터 파츠 분리")
    parser.add_argument("--input", type=str, required=True, help="입력 이미지 경로")
    parser.add_argument("--output", type=str, default="parts", help="출력 경로")
    parser.add_argument("--method", type=str, choices=["komiko", "sam", "template"],
                        default="template", help="분리 방법")
    args = parser.parse_args()

    image_path = Path(args.input)
    output_dir = Path(args.output)

    if not image_path.exists():
        console.print(f"[red]파일을 찾을 수 없습니다: {image_path}[/red]")
        return

    console.print(f"[blue]입력: {image_path}[/blue]")
    console.print(f"[blue]방법: {args.method}[/blue]")

    if args.method == "komiko":
        result = split_with_komiko(image_path, output_dir)
    elif args.method == "sam":
        result = split_with_sam(image_path, output_dir)
    else:
        result = split_manual_template(image_path, output_dir)

    if result.get("success"):
        console.print(f"[green]✓ 분리 완료: {output_dir}[/green]")
        console.print(f"[green]  파츠 수: {len(result.get('parts', []))}[/green]")
    else:
        console.print("[red]✗ 분리 실패[/red]")


if __name__ == "__main__":
    main()
