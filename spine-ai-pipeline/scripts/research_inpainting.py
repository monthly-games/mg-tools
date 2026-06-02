
import sys
import torch
from pathlib import Path
from diffusers import StableDiffusionInpaintPipeline
from PIL import Image

def main():
    if len(sys.argv) < 3:
        print("Usage: python research_inpainting.py <image_path> <mask_path> [prompt]")
        sys.exit(1)

    img_path = sys.argv[1]
    mask_path = sys.argv[2]
    prompt = sys.argv[3] if len(sys.argv) > 3 else "high quality, realistic, seamless"

    print(f"Loading SD Inpainting model...")
    
    # Use float16 for GPU memory efficiency if available
    # Check CUDA availability
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    try:
        pipe = StableDiffusionInpaintPipeline.from_pretrained(
            "runwayml/stable-diffusion-inpainting",
            torch_dtype=dtype,
            variant="fp16" if dtype == torch.float16 else None
        )
        pipe = pipe.to(device)
        
        # Enable some optimizations
        if device == "cuda":
            pipe.enable_attention_slicing()
            # pipe.enable_xformers_memory_efficient_attention() # Requires xformers installed

        image = Image.open(img_path).convert("RGB").resize((512, 512))
        mask = Image.open(mask_path).convert("L").resize((512, 512))

        steps = 20 # Default faster for testing
        if len(sys.argv) > 4:
            steps = int(sys.argv[4])

        print(f"Inpainting on {device} with prompt: '{prompt}' (Steps: {steps})...")
        output = pipe(prompt=prompt, image=image, mask_image=mask, num_inference_steps=steps).images[0]

        output_path = Path("test/inpainting_result.png")
        output.save(output_path)
        print(f"Saved to {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
