import os
import json
import argparse
import google.generativeai as genai
from pathlib import Path
from PIL import Image
from rich.console import Console

console = Console()

def audit_parts(batch_dir: str, api_key: str):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    base_path = Path(batch_dir)
    
    for char_dir in base_path.iterdir():
        if not char_dir.is_dir(): continue
        
        parts_dir = char_dir / "parts"
        if not parts_dir.exists(): continue
        
        console.print(f"\n[bold cyan]Auditing {char_dir.name}...[/bold cyan]")
        
        for part_img_path in parts_dir.glob("*.png"):
            # Skip preview images if any
            if "preview" in part_img_path.name: continue
            
            try:
                img = Image.open(part_img_path)
                
                # Check basic metrics first
                w, h = img.size
                if w < 10 or h < 10:
                    console.print(f"[red]  FAILED (Too Small): {part_img_path.name} ({w}x{h})[/red]")
                    continue
                    
                # Ask Gemini
                prompt = """
                Analyze this image. It is supposed to be a cutout part of a 2D game character (e.g., arm, leg, head, weapon, torso).
                
                Is this a valid, recognizable body part or weapon?
                Or is it unrecognizable noise, a random blob, or background debris?
                
                Respond in JSON:
                {
                    "valid": true/false,
                    "type": "arm" | "leg" | "head" | "body" | "weapon" | "noise" | "unknown",
                    "confidence": 0.0 to 1.0,
                    "reason": "short explanation"
                }
                """
                
                response = model.generate_content([prompt, img])
                text = response.text.strip()
                if text.startswith("```json"):
                    text = text[7:-3]
                result = json.loads(text)
                
                color = "green" if result.get("valid") else "red"
                console.print(f"[{color}]  {part_img_path.name}: {result.get('type')} ({result.get('confidence')}) - {result.get('reason')}[/{color}]")
                
                # If invalid, verify if we should delete or mark it
                if not result.get("valid"):
                    # Rename to .junk to exclude from Spine
                    pass 

            except Exception as e:
                console.print(f"[yellow]  Error analyzing {part_img_path.name}: {e}[/yellow]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="test/output/batch_run_final")
    parser.add_argument("--key_file", default="config/gemini_key.txt")
    args = parser.parse_args()
    
    if os.path.exists(args.key_file):
        with open(args.key_file, "r") as f:
            key = f.read().strip()
        audit_parts(args.dir, key)
    else:
        print("API Key not found")
