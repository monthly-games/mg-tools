#!/usr/bin/env python3
"""
Regenerate Spine Binaries
Scans the output directory and re-runs the JSON -> Spine binary conversion for all characters.
Usage: python scripts/regenerate_spines.py --output_dir test/output/batch
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.progress import track

# Add scripts dir to path to import export_spine
sys.path.append(str(Path(__file__).parent))
from export_spine import convert_json_to_binary

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Regenerate .spine files from .json")
    parser.add_argument("--output_dir", type=str, default="test/output/batch", help="Batch output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        console.print(f"[red]Directory not found: {output_dir}[/red]")
        return

    # Find all character directories (dirs that contain spine/skeleton.json)
    char_dirs = []
    for d in output_dir.iterdir():
        if d.is_dir() and (d / "spine" / "skeleton.json").exists():
            char_dirs.append(d)

    console.print(f"[bold cyan]Found {len(char_dirs)} characters to process.[/bold cyan]")

    success_count = 0
    fail_count = 0

    for char_dir in track(char_dirs, description="Regenerating .spine files..."):
        spine_dir = char_dir / "spine"
        if convert_json_to_binary(spine_dir):
            success_count += 1
        else:
            fail_count += 1
            console.print(f"[red]Failed to generate binary for {char_dir.name}[/red]")

    console.print(f"[bold green]Complete![/bold green]")
    console.print(f"Success: {success_count}")
    console.print(f"Failed: {fail_count}")

if __name__ == "__main__":
    main()
