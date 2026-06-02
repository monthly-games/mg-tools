#!/usr/bin/env python3
"""
Spine AI Pipeline - HTML Gallery Generator
Generates a static HTML page to visualize the processed characters and their metadata.
"""

import argparse
import json
import base64
from pathlib import Path
from rich.console import Console

console = Console()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spine AI Pipeline Gallery</title>
    <style>
        :root {
            --bg-color: #1a1a1a;
            --card-bg: #2d2d2d;
            --text-color: #e0e0e0;
            --accent: #4caf50;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }
        h1 { text-align: center; color: var(--accent); }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .card {
            background-color: var(--card-bg);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: transform 0.2s;
        }
        .card:hover { transform: translateY(-5px); }
        .card-image {
            width: 100%;
            height: 300px;
            object-fit: contain;
            background-color: #000;
            background-image: linear-gradient(45deg, #111 25%, transparent 25%), 
                              linear-gradient(-45deg, #111 25%, transparent 25%), 
                              linear-gradient(45deg, transparent 75%, #111 75%), 
                              linear-gradient(-45deg, transparent 75%, #111 75%);
            background-size: 20px 20px;
            background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
        }
        .card-content { padding: 15px; }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .mood-tag {
            background-color: #e91e63;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .preset-tag {
            background-color: #2196f3;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
        }
        .description {
            font-size: 0.9em;
            color: #aaa;
            margin-bottom: 10px;
            max-height: 80px;
            overflow-y: auto;
        }
        .stats {
            display: flex;
            gap: 10px;
            font-size: 0.8em;
            color: #888;
            border-top: 1px solid #444;
            padding-top: 10px;
        }
        .parts-list {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 5px;
        }
        .part-badge {
            background-color: #444;
            font-size: 0.7em;
            padding: 2px 6px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <h1>Spine AI Pipeline Gallery</h1>
    <div class="gallery">
        <!-- CARDS -->
    </div>
</body>
</html>
"""

CARD_TEMPLATE = """
<div class="card">
    <div class="card-image-wrapper">
        <img src="{image_src}" alt="{name}" class="card-image">
    </div>
    <div class="card-content">
        <div class="card-header">
            <h3>{name}</h3>
            <div>
                {mood_tag}
                <span class="preset-tag">{preset}</span>
            </div>
        </div>
        <div class="description">
            {description}
        </div>
        <div class="parts-list">
            {parts_badges}
        </div>
        <div class="stats">
            <span>Parts: {parts_count}</span>
            <span>Spine: {spine_status}</span>
        </div>
    </div>
</div>
"""

def get_image_as_base64(path):
    if not path.exists(): return ""
    with open(path, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

def generate_report(output_dir: Path, report_file: Path):
    cards_html = ""
    
    # Scan directories
    for char_dir in output_dir.iterdir():
        if not char_dir.is_dir(): continue
        
        name = char_dir.name
        clean_img = char_dir / "clean.png"
        analysis_file = char_dir / "analysis.json"
        
        # Metadata
        mood = "Unknown"
        preset = "Default"
        desc = "No description."
        
        if analysis_file.exists():
            try:
                with open(analysis_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    mood = data.get("mood", mood)
                    preset = data.get("preset", preset)
                    desc = data.get("description", desc)
            except: pass
            
        # Parts
        parts_dir = char_dir / "parts"
        parts = []
        if parts_dir.exists():
            parts = [p.stem for p in parts_dir.glob("*.png")]
            
        # Spine
        spine_ok = (char_dir / "spine" / "skeleton.json").exists()
        
        # Tags HTML
        mood_tag = f'<span class="mood-tag">{mood}</span>' if mood != "Unknown" else ""
        parts_badges = "".join([f'<span class="part-badge">{p}</span>' for p in parts])
        
        # Image (Use Base64 to make single-file report)
        img_src = get_image_as_base64(clean_img)
        
        cards_html += CARD_TEMPLATE.format(
            name=name,
            image_src=img_src,
            mood_tag=mood_tag,
            preset=preset,
            description=desc,
            parts_badges=parts_badges,
            parts_count=len(parts),
            spine_status="✅ Ready" if spine_ok else "❌ Missing"
        )
        
    full_html = HTML_TEMPLATE.replace("<!-- CARDS -->", cards_html)
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(full_html)
        
    console.print(f"[green]Report saved to {report_file}[/green]")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", help="Directory containing character outputs")
    parser.add_argument("--report", default="gallery.html", help="Output HTML file")
    
    args = parser.parse_args()
    generate_report(Path(args.output_dir), Path(args.report))

if __name__ == "__main__":
    main()
