#!/usr/bin/env python3
"""
Spine 캐릭터 애니메이션 자동 생성 스크립트

사용법:
    python animate_character.py --input char_001/spine --preset combat
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

from rich.console import Console

console = Console()


def load_animation_preset(preset_name: str, config_dir: Path) -> List[str]:
    """애니메이션 프리셋 로드"""
    presets_path = config_dir / "presets.json"
    if presets_path.exists():
        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)
            return presets.get("animations", {}).get(preset_name, ["idle"])
    return ["idle"]


def generate_idle_animation(duration: float = 1.0, fps: int = 30) -> Dict[str, Any]:
    """기본 idle 애니메이션 생성"""
    frames = int(duration * fps)
    return {
        "bones": {
            "body": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration / 2, "angle": 2},
                    {"time": duration, "angle": 0},
                ],
            },
        },
    }


def generate_run_animation(duration: float = 0.6, fps: int = 30) -> Dict[str, Any]:
    """기본 run 애니메이션 생성"""
    return {
        "bones": {
            "leg_L": {
                "rotate": [
                    {"time": 0, "angle": -30},
                    {"time": duration / 2, "angle": 30},
                    {"time": duration, "angle": -30},
                ],
            },
            "leg_R": {
                "rotate": [
                    {"time": 0, "angle": 30},
                    {"time": duration / 2, "angle": -30},
                    {"time": duration, "angle": 30},
                ],
            },
        },
    }


def generate_attack_animation(duration: float = 0.5, fps: int = 30) -> Dict[str, Any]:
    """기본 attack 애니메이션 생성"""
    return {
        "bones": {
            "arm_R": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.3, "angle": -90},
                    {"time": duration * 0.5, "angle": 45},
                    {"time": duration, "angle": 0},
                ],
            },
        },
    }


def generate_die_animation(duration: float = 1.0, fps: int = 30) -> Dict[str, Any]:
    """기본 die 애니메이션 생성"""
    return {
        "bones": {
            "root": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration, "angle": 90},
                ],
            },
        },
    }


ANIMATION_GENERATORS = {
    "idle": generate_idle_animation,
    "run": generate_run_animation,
    "attack": generate_attack_animation,
    "attack1": generate_attack_animation,
    "attack2": generate_attack_animation,
    "hit": lambda: generate_idle_animation(0.3),
    "die": generate_die_animation,
    "walk": lambda: generate_run_animation(0.8),
    "talk": lambda: generate_idle_animation(0.5),
    "gesture": lambda: generate_attack_animation(0.8),
    "move": lambda: generate_run_animation(0.5),
    "happy": generate_idle_animation,
    "sad": generate_idle_animation,
    "surprised": lambda: generate_idle_animation(0.3),
}


def add_animations_to_spine(spine_path: Path, animations: List[str]) -> Dict[str, Any]:
    """Spine 프로젝트에 애니메이션 추가"""
    try:
        with open(spine_path, "r", encoding="utf-8") as f:
            spine_data = json.load(f)

        if "animations" not in spine_data:
            spine_data["animations"] = {}

        added = []
        for anim_name in animations:
            generator = ANIMATION_GENERATORS.get(anim_name)
            if generator:
                spine_data["animations"][anim_name] = generator()
                added.append(anim_name)
            else:
                console.print(f"[yellow]알 수 없는 애니메이션: {anim_name}[/yellow]")

        with open(spine_path, "w", encoding="utf-8") as f:
            json.dump(spine_data, f, indent=2)

        return {"success": True, "added": added}

    except Exception as e:
        console.print(f"[red]애니메이션 추가 실패: {e}[/red]")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="캐릭터 애니메이션 생성")
    parser.add_argument("--input", type=str, required=True, help="Spine 프로젝트 경로")
    parser.add_argument("--preset", type=str, default="combat",
                        choices=["combat", "npc", "monster", "ui_character"],
                        help="애니메이션 프리셋")
    parser.add_argument("--animations", type=str, nargs="+",
                        help="개별 애니메이션 지정")
    args = parser.parse_args()

    spine_dir = Path(args.input)
    spine_json = spine_dir / "skeleton.json"

    if not spine_json.exists():
        console.print(f"[red]Spine 프로젝트를 찾을 수 없습니다: {spine_json}[/red]")
        return

    config_dir = Path(__file__).parent.parent / "config"

    if args.animations:
        animations = args.animations
    else:
        animations = load_animation_preset(args.preset, config_dir)

    console.print(f"[blue]입력: {spine_json}[/blue]")
    console.print(f"[blue]애니메이션: {', '.join(animations)}[/blue]")

    result = add_animations_to_spine(spine_json, animations)

    if result.get("success"):
        console.print(f"[green][OK] Animations added[/green]")
        console.print(f"[green]  Added: {', '.join(result.get('added', []))}[/green]")
    else:
        console.print("[red][FAIL] Animation failed[/red]")


if __name__ == "__main__":
    main()
