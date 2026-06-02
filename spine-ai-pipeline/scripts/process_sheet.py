import argparse
import sys
import shutil
from pathlib import Path
from typing import List, Dict
import json
import cv2
import numpy as np
from PIL import Image
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Imports from existing pipeline
from ultralytics import YOLO

console = Console()

def remove_background_local(input_path: Path, output_path: Path, venv_python: str) -> bool:
    """Use existing remove_background.py script"""
    import subprocess
    cmd = f'"{venv_python}" scripts/remove_background.py --input "{input_path}" --output "{output_path}"'
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Background removal failed: {e}[/red]")
        return False

def detect_objects(model, image_path: str) -> List[Dict]:
    """Detect objects in RGB image"""
    classes = [
        "person", "human", "anime character", "girl", "boy", 
        "full body", "front view", "side view", "back view", 
        "face", "head", "expression", "weapon", "sword", "gun",
        "clothing", "armor"
    ]
    model.set_classes(classes)
    
    # Run prediction
    results = model.predict(image_path, conf=0.15, verbose=False)
    
    objects = []
    for r in results:
        for i, box in enumerate(r.boxes):
            cls_id = int(box.cls[0])
            label = classes[cls_id] if cls_id < len(classes) else str(cls_id)
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            
            objects.append({
                "id": i,
                "label": label,
                "conf": conf,
                "bbox": xyxy # [x1, y1, x2, y2]
            })
            
    # Simple NMS/Filter: Remove completely contained boxes? 
    # Or keep them (e.g., Face inside Person)?
    # For extraction, we probably want the biggest distinct chunks.
    # Let's keep all for now and user can choose/filter.
    
    return objects

def crop_and_save(img_rgba: Image.Image, objects: List[Dict], output_dir: Path) -> List[Dict]:
    """Crop objects from RGBA image and save"""
    report = []
    w_img, h_img = img_rgba.size
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, obj in enumerate(objects):
        label = obj["label"]
        bbox = obj["bbox"]
        
        # Add Padding (10%)
        x1, y1, x2, y2 = bbox
        w_box = x2 - x1
        h_box = y2 - y1
        pad_w = w_box * 0.1
        pad_h = h_box * 0.1
        
        nx1 = max(0, int(x1 - pad_w))
        ny1 = max(0, int(y1 - pad_h))
        nx2 = min(w_img, int(x2 + pad_w))
        ny2 = min(h_img, int(y2 + pad_h))
        
        # Crop
        crop = img_rgba.crop((nx1, ny1, nx2, ny2))
        
        # Save
        filename = f"part_{i:02d}_{label.replace(' ', '_')}.png"
        save_path = output_dir / filename
        crop.save(save_path)
        
        # Quality Checks
        quality_issues = []
        
        # 1. Resolution
        if crop.width < 100 or crop.height < 100:
            quality_issues.append("Low Resolution")
            
        # 2. Touching Edges (of original image)
        if nx1 == 0 or ny1 == 0 or nx2 == w_img or ny2 == h_img:
            quality_issues.append("Touches Image Boundary (Might be cut off)")
            
        # 3. Alpha Content
        # Check if crop is mostly empty (transparency)
        alpha = np.array(crop)[:, :, 3]
        if np.mean(alpha) < 5: # Valid pixels < 2% approx (since 5/255 ~ 2%)
            quality_issues.append("Mostly Empty/Transparent")
            
        report.append({
            "file": filename,
            "label": label,
            "confidence": obj["conf"],
            "resolution": f"{crop.width}x{crop.height}",
            "issues": quality_issues
        })
        
    return report

def generate_report(report_data: List[Dict], output_path: Path):
    """Generate Markdown report"""
    md = "# Character Sheet Extraction Report\n\n"
    md += "| Preview | Filename | Label | Confidence | Resolution | Issues |\n"
    md += "| :---: | --- | --- | --- | --- | --- |\n"
    
    for item in report_data:
        issues_str = ", ".join(item["issues"]) if item["issues"] else "OK"
        issue_icon = "⚠️" if item["issues"] else "✅"
        # Relative path for image in markdown
        rel_img_path = item["file"]
        
        md += f"| ![{item['label']}]({rel_img_path}) | `{item['file']}` | **{item['label']}** | {item['confidence']:.2f} | {item['resolution']} | {issue_icon} {issues_str} |\n"
        
    output_path.write_text(md, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Process Character Sheet")
    parser.add_argument("input_image", help="Path to character sheet image")
    parser.add_argument("--output_dir", default="output/processed_sheet", help="Output directory")
    parser.add_argument("--venv_python", default=sys.executable, help="Python executable for subprocesses")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_image)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"[bold cyan]Processing Sheet: {input_path.name}[/bold cyan]")
    
    # 1. Remove Background (Global)
    clean_bg_path = output_dir / "clean_sheet.png"
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task1 = progress.add_task("[green]Removing Background...", total=1)
        if not clean_bg_path.exists():
            success = remove_background_local(input_path, clean_bg_path, args.venv_python)
            if not success:
               console.print("[red]Aborting due to background removal failure[/red]")
               return
        progress.update(task1, completed=1)
               
    # 2. Detect Objects (on Original RGB)
    console.print("[dim]Loading YOLO-World...[/dim]")
    model = YOLO("yolov8l-worldv2.pt")
    
    console.print("[green]Detecting Components...[/green]")
    # Use input_path (RGB) for detection
    objects = detect_objects(model, str(input_path))
    
    console.print(f"[blue]Found {len(objects)} candidates.[/blue]")
    
    if not objects:
        console.print("[yellow]No objects found. Try adjusting prompt in script?[/yellow]")
        return

    # 3. Crop & Save (from RGBA Clean Sheet)
    console.print("[green]Extracting & Validating...[/green]")
    img_rgba = Image.open(clean_bg_path)
    
    # [Quality Fix] High-Quality Upscale (x2)
    # The source sheets are often small. We upscale the clean sheet BEFORE cropping
    # so that all parts have higher resolution for inpainting and animation.
    w_orig, h_orig = img_rgba.size
    scale_factor = 2.0
    
    w_new = int(w_orig * scale_factor)
    h_new = int(h_orig * scale_factor)
    
    console.print(f"[cyan]Upscaling sheet x{scale_factor} ({w_orig}x{h_orig} -> {w_new}x{h_new})...[/cyan]")
    img_rgba = img_rgba.resize((w_new, h_new), resample=Image.LANCZOS)
    
    # Adjust detected boxes to new scale
    for obj in objects:
        obj["bbox"] = [c * scale_factor for c in obj["bbox"]]
    
    report_data = crop_and_save(img_rgba, objects, output_dir)
    
    # 4. Generate Report
    report_path = output_dir / "quality_report.md"
    generate_report(report_data, report_path)
    
    console.print(f"[bold green]✓ Done! Report saved to {report_path}[/bold green]")

if __name__ == "__main__":
    main()
