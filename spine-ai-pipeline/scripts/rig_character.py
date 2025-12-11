#!/usr/bin/env python3
"""
Spine2D AI를 활용한 리깅 자동 생성 스크립트

사용법:
    python rig_character.py --input char_001/parts --output char_001/spine
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

from rich.console import Console

console = Console()


def load_parts_metadata(parts_dir: Path) -> Dict[str, Any]:
    """파츠 메타데이터 로드"""
    metadata_path = parts_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_rig_preset(preset_name: str, config_dir: Path) -> Dict[str, Any]:
    """리깅 프리셋 로드"""
    presets_path = config_dir / "presets.json"
    if presets_path.exists():
        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)
            return presets.get("rig_types", {}).get(preset_name, {})
    return {}


def generate_spine_skeleton(parts_metadata: Dict, rig_preset: Dict) -> Dict[str, Any]:
    """Spine 스켈레톤 JSON 생성"""
    bones = rig_preset.get("bones", ["root", "body", "head"])

    skeleton = {
        "skeleton": {
            "hash": "",
            "spine": "4.1",
            "x": 0,
            "y": 0,
            "width": 512,
            "height": 512,
        },
        "bones": [{"name": bone, "parent": "root" if bone != "root" else None}
                  for bone in bones],
        "slots": [],
        "skins": {"default": {}},
        "animations": {},
    }

    # 파츠를 슬롯으로 변환
    for part in parts_metadata.get("parts", []):
        slot = {
            "name": part["name"],
            "bone": _map_part_to_bone(part["name"], bones),
            "attachment": part["name"],
        }
        skeleton["slots"].append(slot)

    return skeleton


def _map_part_to_bone(part_name: str, bones: list) -> str:
    """파츠 이름을 본에 매핑"""
    mapping = {
        "head": "head",
        "body": "body",
        "arm_L": "arm_L",
        "arm_R": "arm_R",
        "leg_L": "thigh_L",
        "leg_R": "thigh_R",
        "weapon": "hand_R",
    }
    return mapping.get(part_name, "root")


def call_spine_ai_api(parts_dir: Path, preset: str) -> Dict[str, Any]:
    """Spine2D AI API 호출 (플레이스홀더)"""
    # TODO: Spine2D AI (GodMode) API 연동
    console.print("[yellow]Spine2D AI API 연동 필요 - 로컬 생성 모드 사용[/yellow]")
    return {"success": False, "method": "api"}


def generate_local(parts_dir: Path, output_dir: Path, preset: str) -> Dict[str, Any]:
    """로컬에서 기본 Spine 프로젝트 생성"""
    try:
        config_dir = Path(__file__).parent.parent / "config"
        parts_metadata = load_parts_metadata(parts_dir)
        rig_preset = load_rig_preset(preset, config_dir)

        if not rig_preset:
            rig_preset = {"bones": ["root", "body", "head"]}

        skeleton = generate_spine_skeleton(parts_metadata, rig_preset)

        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON 저장
        json_path = output_dir / "skeleton.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(skeleton, f, indent=2)

        return {
            "success": True,
            "method": "local",
            "output": str(json_path),
            "bones": len(skeleton["bones"]),
            "slots": len(skeleton["slots"]),
        }

    except Exception as e:
        console.print(f"[red]리깅 생성 실패: {e}[/red]")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="캐릭터 리깅 생성")
    parser.add_argument("--input", type=str, required=True, help="파츠 폴더 경로")
    parser.add_argument("--output", type=str, required=True, help="출력 경로")
    parser.add_argument("--preset", type=str, default="humanoid",
                        choices=["humanoid", "monster", "simple"],
                        help="리깅 프리셋")
    parser.add_argument("--use-api", action="store_true", help="Spine AI API 사용")
    args = parser.parse_args()

    parts_dir = Path(args.input)
    output_dir = Path(args.output)

    if not parts_dir.exists():
        console.print(f"[red]폴더를 찾을 수 없습니다: {parts_dir}[/red]")
        return

    console.print(f"[blue]입력: {parts_dir}[/blue]")
    console.print(f"[blue]프리셋: {args.preset}[/blue]")

    if args.use_api:
        result = call_spine_ai_api(parts_dir, args.preset)
        if not result.get("success"):
            console.print("[yellow]API 실패, 로컬 생성으로 전환[/yellow]")
            result = generate_local(parts_dir, output_dir, args.preset)
    else:
        result = generate_local(parts_dir, output_dir, args.preset)

    if result.get("success"):
        console.print(f"[green][OK] Rigging complete: {result.get('output')}[/green]")
        console.print(f"[green]  Bones: {result.get('bones')}, Slots: {result.get('slots')}[/green]")
    else:
        console.print("[red][FAIL] Rigging failed[/red]")


if __name__ == "__main__":
    main()
