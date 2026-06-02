
import os
import sys
import glob
from pathlib import Path
from PIL import Image
import numpy as np
import torch
from diffusers import StableDiffusionInpaintPipeline
import research_matting

def main():
    # Setup Paths
    input_dir = Path("images")
    output_dir = Path("test/phase5_batch_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find Images
    extensions = ["*.png", "*.jpg", "*.jpeg"]
    image_files = []
    for ext in extensions:
        image_files.extend(list(input_dir.glob(ext)))
    
    # Filter out _nobg versions if they exist to avoid duplicates
    image_files = [f for f in image_files if "_nobg" not in f.name and "_clean" not in f.name]
    
    print(f"Found {len(image_files)} test images.")
    
    # Load Models
    print("Loading MODNet...")
    matting_sess = research_matting.load_modnet_onnx("models/modnet.onnx")
    
    print("Loading Stable Diffusion Inpainting...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        "runwayml/stable-diffusion-inpainting",
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None
    ).to(device)
    
    if device == "cuda":
        pipe.enable_attention_slicing()

    prompt = "high quality, detailed background"
    steps = 15 # Keep it fast for CPU

    # Process Batch
    for i, img_path in enumerate(image_files):
        print(f"[{i+1}/{len(image_files)}] Processing {img_path.name}...")
        
        try:
            # 1. Matting
            original_img = Image.open(img_path).convert("RGB")
            matte = research_matting.infer_modnet(matting_sess, original_img)
            
            # Save Matte
            alpha = (matte * 255).astype(np.uint8)
            img_np = np.array(original_img)
            rgba = np.dstack((img_np, alpha))
            
            base_name = img_path.stem
            matte_out = output_dir / f"{base_name}_matte.png"
            Image.fromarray(rgba).save(matte_out)
            
            # 2. Inpainting Test (Fill Background)
            # Use inverted alpha as mask? 
            # SD Inpainting replaces White pixels in mask.
            # If we want to verify inpainting, let's try to 'heal' the background by masking the FOREGROUND (white) 
            # and asking it to generate 'empty background'.
            # Or simpler: Mask the background (black in alpha) -> invert -> mask is white on background.
            
            # Mask format for pipe: White pixels are inpainted.
            # Matte: White = Foreground.
            # To inpaint background: Mask = (1 - Matte).
            
            mask_np = 255 - alpha
            mask_img = Image.fromarray(mask_np).convert("L").resize((512, 512))
            input_img = original_img.resize((512, 512))
            
            # Run Inpainting
            result = pipe(
                prompt=prompt, 
                image=input_img, 
                mask_image=mask_img, 
                num_inference_steps=steps
            ).images[0]
            
            inpaint_out = output_dir / f"{base_name}_inpaint_bg.png"
            result.save(inpaint_out)
            
        except Exception as e:
            print(f"Failed to process {img_path.name}: {e}")

    print("Batch Processing Complete.")

if __name__ == "__main__":
    main()
