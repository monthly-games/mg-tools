#!/usr/bin/env python3
"""
Spine 캐릭터 애니메이션 자동 생성 스크립트

사용법:
    python animate_character.py --input char_001/spine --preset combat
"""

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Any, List

from rich.console import Console

console = Console()

# --- Physics Helpers ---
def apply_physics_sway(anim_data, bone, time_offset, intensity=1.0, duration=2.0):
    """
    Simulate secondary motion (sway) like hair/clothing. (Pendulum)
    """
    if bone not in anim_data["bones"]:
        anim_data["bones"][bone] = {}
    if "rotate" not in anim_data["bones"][bone]:
        anim_data["bones"][bone]["rotate"] = []
        
    steps = 10
    interval = duration / steps
    
    for i in range(steps + 1):
        t = i * interval
        # Sine wave with phase shift
        angle = math.sin((t / duration) * math.pi * 2 - time_offset) * (5 * intensity)
        
        curve = "bezier" # Simplified curve definition for Spine JSON
        c1, c2, c3, c4 = 0.25, 0, 0.75, 1
        
        frame = {"time": t, "angle": angle, "curve": curve, "c1": c1, "c2": c2, "c3": c3, "c4": c4}
        if i == steps: del frame["curve"] # Last frame no curve
        
        anim_data["bones"][bone]["rotate"].append(frame)

        anim_data["bones"][bone]["rotate"].append(frame)

def apply_harmonic_sway(anim_data, bone, time_offset, intensity=1.0, duration=2.0, freq=1.0):
    """
    Simulate complex secondary motion using harmonics (Dual Sine Waves).
    Good for long hair, dress tails.
    """
    if bone not in anim_data["bones"]:
        anim_data["bones"][bone] = {}
    if "rotate" not in anim_data["bones"][bone]:
        anim_data["bones"][bone]["rotate"] = []
        
    steps = 16 # Higher sampling for quality
    interval = duration / steps
    
    for i in range(steps + 1):
        t = i * interval
        # Base wave (Pendulum)
        theta1 = (t / duration) * math.pi * 2 * freq - time_offset
        # Secondary wave (Flutter/Drag) - 2x freq
        theta2 = (t / duration) * math.pi * 4 * freq - time_offset - 0.5
        
        # Combine: Main sway + detailed flutter
        angle = (math.sin(theta1) * 5 * intensity) + (math.sin(theta2) * 1.5 * intensity)
        
        # Damping at ends? No, loop needs to be seamless.
        # Ensure start and end match roughly? Sin(0) = 0, Sin(2pi) = 0. Clean loop.
        
        curve = "bezier"
        c1, c2, c3, c4 = 0.25, 0, 0.75, 1
        
        frame = {"time": t, "angle": angle, "curve": curve, "c1": c1, "c2": c2, "c3": c3, "c4": c4}
        if i == steps: del frame["curve"]
        
        anim_data["bones"][bone]["rotate"].append(frame)

def apply_soft_bounce(anim_data, bone, time_offset, intensity=1.0, duration=2.0):
    """
    Simulate soft body physics (breathing/bounce).
    Scale Y (Stretch) + Translate Y (Bounce).
    """
    if bone not in anim_data["bones"]:
        anim_data["bones"][bone] = {}
        
    # Translate
    if "translate" not in anim_data["bones"][bone]: anim_data["bones"][bone]["translate"] = []
    # Scale
    if "scale" not in anim_data["bones"][bone]: anim_data["bones"][bone]["scale"] = []
    
    steps = 10
    interval = duration / steps
    
    for i in range(steps + 1):
        t = i * interval
        phase = (t / duration) * math.pi * 2 - time_offset
        
        # Breathe: Scale Y
        scale_y = 1.0 + (math.sin(phase) + 1) * 0.02 * intensity
        scale_x = 1.0 - (math.sin(phase) + 1) * 0.01 * intensity
        
        # Bounce: Translate Y
        trans_y = math.sin(phase) * 2 * intensity
        
        c1, c2, c3, c4 = 0.25, 0, 0.75, 1
        
        kf_trans = {"time": t, "x": 0, "y": trans_y, "curve": "bezier", "c1": c1, "c2": c2, "c3": c3, "c4": c4}
        kf_scale = {"time": t, "x": scale_x, "y": scale_y, "curve": "bezier", "c1": c1, "c2": c2, "c3": c3, "c4": c4}
        
        if i == steps:
            del kf_trans["curve"]
            del kf_scale["curve"]
            
        anim_data["bones"][bone]["translate"].append(kf_trans)
        anim_data["bones"][bone]["scale"].append(kf_scale)

# --- Generators ---

def generate_idle_animation(duration: float = 2.0) -> Dict[str, Any]:
    return {
        "bones": {
            "body": {
                "translate": [ 
                    {"time": 0, "y": 0, "curve": "bezier", "c1": 0.25, "c2": 0, "c3": 0.75, "c4": 1},
                    {"time": duration * 0.5, "y": 5}, 
                    {"time": duration, "y": 0},
                ]
            }
        }
    }

def generate_allure_animation(duration: float = 4.0) -> Dict[str, Any]:
    """니케 스타일: 매혹적인 움직임 (Goddess of Victory Style)"""
    anim_data = {"bones": {}}
    
    # 1. Body Base (Center of Mass) - Slower, deeper breath
    apply_soft_bounce(anim_data, "body", time_offset=0, intensity=1.8, duration=duration)
    
    # 2. Hips / Legs (Cross-Sway)
    # Use harmonic sway for more fluid hip movement
    apply_harmonic_sway(anim_data, "hip", time_offset=0.2, intensity=0.6, duration=duration, freq=1.0)
    
    # 3. Arms (Breathing Follow-through)
    apply_harmonic_sway(anim_data, "arm_L", time_offset=0.5, intensity=0.9, duration=duration, freq=1.0)
    apply_harmonic_sway(anim_data, "arm_R", time_offset=0.5, intensity=0.9, duration=duration, freq=1.0)
    
    # 4. Head (Subtle tilt)
    apply_harmonic_sway(anim_data, "head", time_offset=0.1, intensity=0.4, duration=duration, freq=0.5)
    
    # 5. Hair (Flow - High intensity, offset)
    if "hair" not in anim_data["bones"]: anim_data["bones"]["hair"] = {}
    apply_harmonic_sway(anim_data, "hair", time_offset=0.8, intensity=1.5, duration=duration, freq=1.0)
    
    return anim_data

def generate_run_animation(duration: float = 0.6) -> Dict[str, Any]:
    return {
        "bones": {
            "body": {
                "translate": [
                    {"time": 0, "x": 0, "y": 0},
                    {"time": duration * 0.25, "x": 0, "y": 15},
                    {"time": duration * 0.5, "x": 0, "y": 0},
                    {"time": duration * 0.75, "x": 0, "y": 15},
                    {"time": duration, "x": 0, "y": 0},
                ],
                "rotate": [{"time": 0, "angle": 15}]
            },
            "arm_L": {"rotate": [{"time":0, "angle": 60}, {"time": duration/2, "angle": -60}, {"time": duration, "angle": 60}]},
            "arm_R": {"rotate": [{"time":0, "angle": -60}, {"time": duration/2, "angle": 60}, {"time": duration, "angle": -60}]},
            "thigh_L": {"rotate": [{"time":0, "angle": -45}, {"time": duration/2, "angle": 80}, {"time": duration, "angle": -45}]},
            "thigh_R": {"rotate": [{"time":0, "angle": 80}, {"time": duration/2, "angle": -45}, {"time": duration, "angle": 80}]},
        }
    }

def generate_attack_animation(duration: float = 0.8) -> Dict[str, Any]:
    return {
        "bones": {
             "body": {
                 "rotate": [
                      {"time": 0, "angle": 0},
                      {"time": duration * 0.3, "angle": -20}, 
                      {"time": duration * 0.4, "angle": 30}, 
                      {"time": duration, "angle": 0}
                 ]
             },
             "arm_R": {
                 "rotate": [
                     {"time": 0, "angle": 0},
                     {"time": duration * 0.3, "angle": -120},
                     {"time": duration * 0.4, "angle": 60},
                     {"time": duration, "angle": 0},
                 ]
             }
        }
    }

def generate_die_animation(duration: float = 1.0) -> Dict[str, Any]:
    return {
        "bones": {
            "root": {
                "rotate": [{"time": 0, "angle": 0}, {"time": duration, "angle": 90}],
                "translate": [{"time": 0, "x": 0, "y": 0}, {"time": duration, "x": -20, "y": -50}]
            }
        }
    }

def generate_walk_animation(duration: float = 1.0) -> Dict[str, Any]:
    """Slower walk cycle with subtle body bounce and arm swing"""
    return {
        "bones": {
            "body": {
                "translate": [
                    {"time": 0, "x": 0, "y": 0},
                    {"time": duration * 0.25, "x": 0, "y": 3},
                    {"time": duration * 0.5, "x": 0, "y": 0},
                    {"time": duration * 0.75, "x": 0, "y": 3},
                    {"time": duration, "x": 0, "y": 0},
                ]
            },
            "head": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.5, "angle": 2},
                    {"time": duration, "angle": 0},
                ]
            },
            "arm_L": {
                "rotate": [
                    {"time": 0, "angle": 30},
                    {"time": duration * 0.5, "angle": -30},
                    {"time": duration, "angle": 30},
                ]
            },
            "arm_R": {
                "rotate": [
                    {"time": 0, "angle": -30},
                    {"time": duration * 0.5, "angle": 30},
                    {"time": duration, "angle": -30},
                ]
            },
            "thigh_L": {
                "rotate": [
                    {"time": 0, "angle": -25},
                    {"time": duration * 0.5, "angle": 40},
                    {"time": duration, "angle": -25},
                ]
            },
            "thigh_R": {
                "rotate": [
                    {"time": 0, "angle": 40},
                    {"time": duration * 0.5, "angle": -25},
                    {"time": duration, "angle": 40},
                ]
            },
            "shin_L": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.5, "angle": -30},
                    {"time": duration, "angle": 0},
                ]
            },
            "shin_R": {
                "rotate": [
                    {"time": 0, "angle": -30},
                    {"time": duration * 0.5, "angle": 0},
                    {"time": duration, "angle": -30},
                ]
            },
        }
    }

def generate_hit_animation(duration: float = 0.4) -> Dict[str, Any]:
    """Taking damage - body recoil and head snap"""
    return {
        "bones": {
            "body": {
                "translate": [
                    {"time": 0, "x": -10, "y": 0},
                    {"time": duration * 0.5, "x": -5, "y": 0},
                    {"time": duration, "x": 0, "y": 0},
                ]
            },
            "head": {
                "rotate": [
                    {"time": 0, "angle": -15},
                    {"time": duration * 0.5, "angle": -8},
                    {"time": duration, "angle": 0},
                ]
            },
            "arm_L": {
                "rotate": [
                    {"time": 0, "angle": 30},
                    {"time": duration * 0.5, "angle": 15},
                    {"time": duration, "angle": 0},
                ]
            },
            "arm_R": {
                "rotate": [
                    {"time": 0, "angle": -30},
                    {"time": duration * 0.5, "angle": -15},
                    {"time": duration, "angle": 0},
                ]
            },
        }
    }

# Alias for death animation
generate_death_animation = generate_die_animation

def generate_jump_animation(duration: float = 0.6) -> Dict[str, Any]:
    """Platformer jump - crouch, launch, land"""
    return {
        "bones": {
            "body": {
                "translate": [
                    {"time": 0, "x": 0, "y": -5},
                    {"time": duration * 0.3, "x": 0, "y": 20},
                    {"time": duration, "x": 0, "y": 0},
                ]
            },
            "thigh_L": {
                "rotate": [
                    {"time": 0, "angle": 45},
                    {"time": duration * 0.3, "angle": -60},
                    {"time": duration, "angle": 0},
                ]
            },
            "thigh_R": {
                "rotate": [
                    {"time": 0, "angle": 45},
                    {"time": duration * 0.3, "angle": -60},
                    {"time": duration, "angle": 0},
                ]
            },
            "shin_L": {
                "rotate": [
                    {"time": 0, "angle": -45},
                    {"time": duration * 0.3, "angle": 60},
                    {"time": duration, "angle": 0},
                ]
            },
            "shin_R": {
                "rotate": [
                    {"time": 0, "angle": -45},
                    {"time": duration * 0.3, "angle": 60},
                    {"time": duration, "angle": 0},
                ]
            },
            "arm_L": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.3, "angle": -90},
                    {"time": duration, "angle": 0},
                ]
            },
            "arm_R": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.3, "angle": -90},
                    {"time": duration, "angle": 0},
                ]
            },
        }
    }

def generate_fall_animation(duration: float = 0.5) -> Dict[str, Any]:
    """Falling - body descends and leans forward"""
    return {
        "bones": {
            "body": {
                "translate": [
                    {"time": 0, "x": 0, "y": 0},
                    {"time": duration, "x": 0, "y": -15},
                ],
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration, "angle": 10},
                ]
            },
            "arm_L": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.5, "angle": -45},
                    {"time": duration, "angle": -45},
                ]
            },
            "arm_R": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration * 0.5, "angle": 45},
                    {"time": duration, "angle": 45},
                ]
            },
            "thigh_L": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration, "angle": -20},
                ]
            },
            "thigh_R": {
                "rotate": [
                    {"time": 0, "angle": 0},
                    {"time": duration, "angle": -20},
                ]
            },
        }
    }

def generate_flap_animation(duration: float = 0.3) -> Dict[str, Any]:
    """Wing flap - rapid arm rotation (loopable)"""
    return {
        "bones": {
            "body": {
                "translate": [
                    {"time": 0, "x": 0, "y": 0},
                    {"time": duration * 0.5, "x": 0, "y": 5},
                    {"time": duration, "x": 0, "y": 0},
                ]
            },
            "arm_L": {
                "rotate": [
                    {"time": 0, "angle": -60},
                    {"time": duration * 0.5, "angle": 40},
                    {"time": duration, "angle": -60},
                ]
            },
            "arm_R": {
                "rotate": [
                    {"time": 0, "angle": 60},
                    {"time": duration * 0.5, "angle": -40},
                    {"time": duration, "angle": 60},
                ]
            },
        }
    }

# Generator Map
ANIMATION_GENERATORS = {
    "idle": generate_idle_animation,
    "run": generate_run_animation,
    "attack": generate_attack_animation,
    "attack1": generate_attack_animation,
    "die": generate_die_animation,
    "allure": generate_allure_animation, # Register Allure
    "combat": lambda: generate_idle_animation(2.0), # Placeholder if combat selected but map needed
    "walk": generate_walk_animation,
    "hit": generate_hit_animation,
    "death": generate_death_animation,
    "jump": generate_jump_animation,
    "fall": generate_fall_animation,
    "flap": generate_flap_animation,
}

def load_animation_preset(preset_name: str, config_dir: Path) -> List[str]:
    """애니메이션 프리셋 로드"""
    if preset_name == "allure":
        return ["allure"] # Explicit return for allure
        
    presets_path = config_dir / "presets.json"
    if presets_path.exists():
        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)
            return presets.get("animations", {}).get(preset_name, ["idle"])
    return ["idle"]

def add_animations_to_spine(spine_path: Path, animations: List[str]) -> Dict[str, Any]:
    try:
        with open(spine_path, "r", encoding="utf-8") as f:
            spine_data = json.load(f)

        if "animations" not in spine_data:
            spine_data["animations"] = {}

        # Get existing bone names for validation
        existing_bones = set(b["name"] for b in spine_data.get("bones", []))

        added = []
        for anim_name in animations:
            generator = ANIMATION_GENERATORS.get(anim_name)
            if generator:
                anim_data = generator()
                
                # Filter out bones that don't exist in the skeleton
                valid_bones_data = {}
                for bone_name, tracks in anim_data.get("bones", {}).items():
                    if bone_name in existing_bones:
                        valid_bones_data[bone_name] = tracks
                    else:
                        console.print(f"[yellow]  Warning: Skipping animation for missing bone '{bone_name}'[/yellow]")
                
                anim_data["bones"] = valid_bones_data
                
                spine_data["animations"][anim_name] = anim_data
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
                        choices=["combat", "npc", "monster", "ui_character", "allure", "idle"],
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
