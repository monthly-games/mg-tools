#!/usr/bin/env python3
"""
Spine JSON Verification Script
Validates the structure of generated skeleton.json files to ensure compatibility with Spine Runtimes.
"""

import json
import argparse
from pathlib import Path
from rich.console import Console

console = Console()

def verify_skeleton_json(json_path: Path):
    if not json_path.exists():
        console.print(f"[red] फाइल 찾을 수 없음: {json_path}[/red]")
        return False

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        errors = []
        warnings = []

        # 1. Essential Sections
        if "skeleton" not in data: errors.append("Missing 'skeleton' section")
        if "bones" not in data: errors.append("Missing 'bones' section")
        if "slots" not in data: errors.append("Missing 'slots' section")

        # 2. Bone Hierarchy Check
        bone_names = {b["name"] for b in data.get("bones", [])}
        if "root" not in bone_names:
            errors.append("No 'root' bone found")
        
        for i, bone in enumerate(data.get("bones", [])):
            if i == 0: continue # Root has no parent
            parent = bone.get("parent")
            if not parent:
                warnings.append(f"Bone '{bone['name']}' has no parent (detached?)")
            elif parent not in bone_names:
                errors.append(f"Bone '{bone['name']}' references unknown parent '{parent}'")

        # 3. Slot & Attachment Check
        slot_names = set()
        for slot in data.get("slots", []):
            slot_names.add(slot["name"])
            bone_ref = slot.get("bone")
            if bone_ref and bone_ref not in bone_names:
                errors.append(f"Slot '{slot['name']}' references unknown bone '{bone_ref}'")

        # 4. Skin/Attachment Logic
        # Skins -> "default" -> slot_name -> attachment_name -> { path, x, y ... }
        if "skins" in data:
            for skin_name, skin_data in data["skins"].items():
                for slot_key, attachments in skin_data.items():
                    if slot_key not in slot_names:
                        warnings.append(f"Skin '{skin_name}' references unused slot '{slot_key}'")
                    
                    # Check attachment files (if paths provided)
                    # We can't verify actual PNG existence here easily unless we know relative path context,
                    # but we can check the path string validity.
                    pass

        # 5. Animation Check
        if "animations" in data:
            for anim_name, timelines in data["animations"].items():
                if "bones" in timelines:
                    for bone_key in timelines["bones"]:
                        if bone_key not in bone_names:
                            warnings.append(f"Animation '{anim_name}' targets unknown bone '{bone_key}'")

        # Report
        if errors:
            console.print(f"[red]❌ Check Failed: {json_path.name}[/red]")
            for e in errors: console.print(f"  - [red]{e}[/red]")
            return False
        
        if warnings:
            console.print(f"[yellow]⚠️  Warnings: {json_path.name}[/yellow]")
            for w in warnings: console.print(f"  - {w}")
            return True # Warnings don't fail

        console.print(f"[green]✅ Valid Spine JSON: {json_path.name}[/green]")
        return True

    except json.JSONDecodeError:
        console.print(f"[red]❌ Invalid JSON syntax: {json_path}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        return False

def main():
    parser = argparse.ArgumentParser(description="Verify Spine JSON integrity")
    parser.add_argument("--input", type=str, required=True, help="Path to skeleton.json or directory containing it")
    args = parser.parse_args()

    target = Path(args.input)
    if target.is_dir():
        target = target / "skeleton.json"

    verify_skeleton_json(target)

if __name__ == "__main__":
    main()
