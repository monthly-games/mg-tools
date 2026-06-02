
import os
import json
import cv2
import numpy as np
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def evaluate_matting_connectivity(image_path):
    """
    Check for disconnected 'islands' in the alpha channel.
    High integrity matting should typically have 1 main blob per part (or very few).
    Returns: number of islands, max_island_area_ratio
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None or img.shape[2] != 4:
        return 0, 1.0 # Not an alpha image
        
    alpha = img[:, :, 3]
    # Binarize
    _, thresh = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    
    # Connected Components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    
    # index 0 is background
    if num_labels <= 1:
        return 0, 0.0
        
    # stats: [x, y, w, h, area]
    areas = stats[1:, cv2.CC_STAT_AREA] # Exclude background
    max_area = np.max(areas)
    total_area = np.sum(areas)
    
    # Islands are components smaller than e.g. 10% of main blob (heuristic)
    # Or just count total components.
    
    # We want to detect "noise". Small islands.
    n_islands = num_labels - 1
    
    return n_islands, max_area / total_area

def evaluate_rig_integrity(skeleton_path):
    """
    Check for structural issues in the exported spine json.
    - Overlapping joints (bones with 0 length or child at same loc as parent without purpose)
    """
    try:
        with open(skeleton_path, "r") as f:
            data = json.load(f)
            
        bones = data.get("bones", [])
        issues = []
        
        # Simple check: duplicate positions or very short bones for limbs
        # Not easy to check absolute position without traversing parent hierarchy.
        # But we can check "length" property for major limbs.
        
        limbs = ["arm_L", "arm_R", "leg_L", "leg_R", "thigh_L", "thigh_R"]
        for b in bones:
            if b.get("name") in limbs:
                length = b.get("length", 0)
                if length < 10:
                    issues.append(f"Short limb bone: {b['name']} (len={length})")
                    
        return len(issues), issues
    except Exception as e:
        return -1, [str(e)]

def main():
    parser = argparse.ArgumentParser(description="Advanced Asset Evaluation")
    parser.add_argument("--input_dir", type=str, required=True, help="Batch output directory to evaluate")
    parser.add_argument("--output", type=str, help="Optional path to save markdown report")
    args = parser.parse_args()
    
    base_dir = Path(args.input_dir)
    
    # Data collection
    results = []
    
    characters = [d for d in base_dir.iterdir() if d.is_dir()]
    
    for char_dir in characters:
        char_name = char_dir.name
        parts_dir = char_dir / "parts"
        spine_path = char_dir / "spine" / "skeleton.json"
        
        # 1. Matting Check
        total_islands = 0
        n_parts = 0
        if parts_dir.exists():
            for p_file in parts_dir.glob("*.png"):
                islands, ratio = evaluate_matting_connectivity(p_file)
                total_islands += islands
                n_parts += 1
        
        avg_islands = total_islands / n_parts if n_parts > 0 else 0
        
        # 2. Rigging Check
        rig_issues_count = 0
        if spine_path.exists():
            count, details = evaluate_rig_integrity(spine_path)
            rig_issues_count = count
            
        results.append({
            "name": char_name,
            "matting": avg_islands,
            "rigging": rig_issues_count
        })

    # Console Output
    table = Table(title="Asset Quality Report")
    table.add_column("Character", style="cyan")
    table.add_column("Matting (Islands/Avg)", style="magenta")
    table.add_column("Rigging (Issues)", style="green")
    table.add_column("Status", style="bold")
    
    for r in results:
        matting_str = f"{r['matting']:.1f}"
        if r['matting'] > 5.0: matting_str = f"[red]{matting_str}[/red]"
        elif r['matting'] > 2.0: matting_str = f"[yellow]{matting_str}[/yellow]"
        
        rig_str = f"{r['rigging']}"
        if r['rigging'] > 0: rig_str = f"[yellow]{rig_str}[/yellow]"
        
        status = "[green]PASS[/green]"
        if r['matting'] > 5.0 or r['rigging'] > 0: status = "[yellow]WARN[/yellow]"
        
        table.add_row(r['name'], matting_str, rig_str, status)
        
    console.print(table)
    
    # Markdown Export
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("# Asset Quality Evaluation Report\n\n")
            f.write("| Character | Matting Noise (Islands) | Rigging Issues | Status |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for r in results:
                status = "PASS"
                if r['matting'] > 5.0 or r['rigging'] > 0: status = "WARN"
                f.write(f"| `{r['name']}` | {r['matting']:.1f} | {r['rigging']} | {status} |\n")
            
            f.write("\n\n## Metric Definitions\n")
            f.write("- **Matting Noise**: Average number of disconnected 'islands' in alpha channel per part. (> 5.0 is High Noise)\n")
            f.write("- **Rigging Issues**: Count of structural anomalies (e.g. very short bones).\n")


if __name__ == "__main__":
    main()
