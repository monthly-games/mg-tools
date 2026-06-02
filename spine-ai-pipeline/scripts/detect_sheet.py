import cv2
from ultralytics import YOLO
import sys
from pathlib import Path
from rich.console import Console

console = Console()

def main():
    if len(sys.argv) < 2:
        print("Usage: python detect_sheet.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    model = YOLO("yolov8s-world.pt")
    
    # Define classes relevant to a character sheet
    classes = [
        "person", "human", "anime character", "girl", "boy", 
        "full body", "front view", "side view", "back view", 
        "face", "head", "expression", "facial expression",
        "weapon", "sword", "gun", "staff",
        "clothing", "armor", "shoes", "hair" 
    ]
    model.set_classes(classes)
    
    console.print(f"[cyan]Analyzing {image_path}...[/cyan]")
    results = model.predict(image_path, conf=0.1) # Low conf to see candidates
    
    found_objects = []
    
    for r in results:
        # r.save(filename="output/sheet_debug.png") # Save debug visual
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = classes[cls_id] if cls_id < len(classes) else str(cls_id)
            conf = float(box.conf[0])
            found_objects.append(f"{label} ({conf:.2f})")
            
    if found_objects:
        console.print(f"[green]Found {len(found_objects)} objects:[/green]")
        for obj in found_objects:
             console.print(f" - {obj}")
        
        # Save a visualized copy
        output_path = Path("output/sheet_analysis.jpg")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results[0].save(filename=str(output_path))
        console.print(f"[blue]Saved visualization to {output_path}[/blue]")
    else:
        console.print("[red]No objects found with current prompts.[/red]")

if __name__ == "__main__":
    main()
