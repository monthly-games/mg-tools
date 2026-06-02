#!/usr/bin/env python3
"""
Repair Pipeline Outputs
Scans for missing .spine files and repairs them by:
1. Re-running animate_character.py (to fix invalid bone references in JSON)
2. Re-running export_spine.py (to generate the binary)
"""

import sys
import argparse
import subprocess
from pathlib import Path
from rich.console import Console
from rich.progress import track

# Add scripts dir to path to import export_spine
sys.path.append(str(Path(__file__).parent))
from export_spine import convert_json_to_binary

console = Console()

def run_animation_fix(spine_dir: Path, preset: str = "allure"):
    """Re-runs animation generation to fix JSON data."""
    script_path = Path(__file__).parent / "animate_character.py"
    cmd = [sys.executable, str(script_path), "--input", str(spine_dir), "--preset", preset]
    
    try:
        # console.print(f"[dim]Re-running animation for {spine_dir.parent.name}...[/dim]")
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Animation fix failed for {spine_dir.parent.name}: {e.stderr.decode()}[/red]")
        return False

def main():
    parser = argparse.ArgumentParser(description="Repair missing .spine files")
    parser.add_argument("--output_dir", type=str, default="test/output/batch", help="Batch output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        console.print(f"[red]Directory not found: {output_dir}[/red]")
        return

    # Find chars missing .spine
    missing_chars = []
    for d in output_dir.iterdir():
        if d.is_dir():
            spine_file = d / "spine" / "skeleton.spine"
            if not spine_file.exists():
                missing_chars.append(d)

    console.print(f"[bold cyan]Found {len(missing_chars)} characters missing .spine files.[/bold cyan]")

    fixed_count = 0
    
    for char_dir in track(missing_chars, description="Repairing..."):
        spine_dir = char_dir / "spine"
        
        # 0. Check for Rig (skeleton.json)
        if not (spine_dir / "skeleton.json").exists():
            console.print(f"[yellow]Missing rig for {char_dir.name}. Running rig_character.py...[/yellow]")
            # Assume parts dir exists
            parts_dir = char_dir / "parts"
            if not parts_dir.exists():
                console.print(f"[red]Cannot rig {char_dir.name}: parts dir missing[/red]")
                continue
                
            rig_script = Path(__file__).parent / "rig_character.py"
            # Default to humanoid template for robustness, or detect?
            # batch_process uses --template humanoid usually.
            cmd = [sys.executable, str(rig_script), "--input", str(parts_dir), "--output", str(spine_dir), "--template", "humanoid"]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                console.print(f"[green]Rigged {char_dir.name}[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Rigging failed for {char_dir.name}: {e.stderr.decode()}[/red]")
                continue
        
        # 1. Fix JSON (Animation)
        # Determine preset...
        preset = "allure"
        if run_animation_fix(spine_dir, preset=preset):
            # 2. Export Binary
            if convert_json_to_binary(spine_dir):
                fixed_count += 1
                console.print(f"[green]Fixed {char_dir.name}[/green]")
            else:
                console.print(f"[red]Binary export failed for {char_dir.name}[/red]")
        else:
            console.print(f"[red]Animation gen failed for {char_dir.name}[/red]")

    console.print(f"[bold green]Repair Complete! Fixed {fixed_count}/{len(missing_chars)}[/bold green]")

if __name__ == "__main__":
    main()
