#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from PIL import Image

def pack_textures(input_dir, output_dir, output_name, size=2048):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    images = []
    for f in input_path.glob("*.png"):
        img = Image.open(f)
        images.append((f.stem, img))
        
    # Sort by height desc
    images.sort(key=lambda x: x[1].height, reverse=True)
    
    atlas_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    atlas_data = [] # (name, x, y, w, h)
    
    # Simple Shelf Packing
    current_x = 0
    current_y = 0
    row_h = 0
    
    for name, img in images:
        w, h = img.size
        if current_x + w > size:
            current_x = 0
            current_y += row_h + 2 # padding
            row_h = 0
            
        if current_y + h > size:
            print(f"[Error] Atlas full! Skipping {name}")
            continue
            
        atlas_img.paste(img, (current_x, current_y))
        atlas_data.append((name, current_x, current_y, w, h))
        
        current_x += w + 2 # padding
        row_h = max(row_h, h)
        
    # Save Image
    png_filename = f"{output_name}.png"
    atlas_img.save(output_path / png_filename)
    
    # Save Atlas
    atlas_filename = f"{output_name}.atlas"
    with open(output_path / atlas_filename, "w", encoding="utf-8") as f:
        f.write(f"\n{png_filename}\n")
        f.write(f"size: {size},{size}\n")
        f.write("format: RGBA8888\n")
        f.write("filter: Linear,Linear\n")
        f.write("repeat: none\n")
        
        for name, x, y, w, h in atlas_data:
            f.write(f"{name}\n")
            f.write("  rotate: false\n")
            f.write(f"  xy: {x}, {y}\n")
            f.write(f"  size: {w}, {h}\n")
            f.write(f"  orig: {w}, {h}\n")
            f.write("  offset: 0, 0\n")
            f.write("  index: -1\n")
            
    print(f"Packed {len(images)} images to {output_path / atlas_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    
    pack_textures(args.input, args.output, args.name)
