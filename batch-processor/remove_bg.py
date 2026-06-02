import os
import argparse
from pathlib import Path
from rembg import remove
from PIL import Image
import io

def process_directory(input_dir, output_dir):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    extensions = ['*.png', '*.jpg', '*.jpeg']
    files = []
    for ext in extensions:
        files.extend(input_path.glob(ext))

    processed_count = 0
    print(f"Found {len(files)} images in {input_dir}")

    for file_path in files:
        if '_nobg' in file_path.name: # Skip already processed files if they are in same dir
            continue
            
        try:
            print(f"Processing: {file_path.name}...")
            
            with open(file_path, 'rb') as i:
                input_data = i.read()
                output_data = remove(input_data)
                
            img = Image.open(io.BytesIO(output_data))
            
            # Save as PNG with same name
            out_file = output_path / f"{file_path.stem}.png"
            img.save(out_file)
            
            processed_count += 1
            print(f"Saved to: {out_file}")
            
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")

    print(f"Done. Processed {processed_count} images.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Batch remove background from images using rembg.')
    parser.add_argument('--input', '-i', required=True, help='Input directory containing images')
    parser.add_argument('--output', '-o', required=True, help='Output directory for transparent images')
    
    args = parser.parse_args()
    
    process_directory(args.input, args.output)
