
import torch
import numpy as np
from PIL import Image
from diffusers import StableDiffusionInpaintPipeline

class InpaintingEngine:
    def __init__(self, model_id="runwayml/stable-diffusion-inpainting"):
        self.pipe = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_id = model_id
        self._load_model()

    def _load_model(self):
        try:
            print(f"[Inpainting] Loading {self.model_id} on {self.device}...")
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            
            self.pipe = StableDiffusionInpaintPipeline.from_pretrained(
                self.model_id,
                torch_dtype=dtype,
                variant="fp16" if dtype == torch.float16 else None,
                safety_checker=None # Optional: Disable if causing too many false positives on fantasy art
            ).to(self.device)
            
            if self.device == "cuda":
                self.pipe.enable_attention_slicing()
                
            print("[Inpainting] Model loaded.")
        except Exception as e:
            print(f"[Inpainting] Failed to load model: {e}")

    def inpaint(self, image_pil, mask_pil, prompt="background, texture", steps=20):
        """
        Inpaint the masked area of the image.
        Args:
            image_pil: Source image (PIL RGB)
            mask_pil: Mask image (PIL L), White = Inpaint Area
            prompt: Guidance prompt
            steps: Inference steps
        Returns:
            PIL Image result
        """
        if self.pipe is None:
            return image_pil

        # Resize for SD (must be multiple of 8, usually 512x512)
        w, h = image_pil.size
        # Simple resize to 512 for speed/consistency, or keep aspect ratio?
        # SD 1.5 trained on 512x512.
        
        input_img = image_pil.resize((512, 512))
        input_mask = mask_pil.resize((512, 512))
        
        try:
            result = self.pipe(
                prompt=prompt,
                image=input_img,
                mask_image=input_mask,
                num_inference_steps=steps
            ).images[0]
            
            # Check for Black Output (Safety Filter or NaN)
            if self._is_black(result):
                print(f"[Inpainting] Detected black output for prompt '{prompt}'. Retrying with safe prompt...")
                # Retry 1: Safe Prompt
                result = self.pipe(
                    prompt="pattern, texture",
                    image=input_img,
                    mask_image=input_mask,
                    num_inference_steps=steps
                ).images[0]
                
                if self._is_black(result):
                    print("[Inpainting] Retry failed. Falling back to simple CV2 inpainting.")
                    return self._fallback_cv2(image_pil, mask_pil)

            # Resize back
            return result.resize((w, h))
        except Exception as e:
            print(f"[Inpainting] inference failed: {e}")
            return image_pil

    def _is_black(self, img_pil):
        extrema = img_pil.convert("L").getextrema()
        return extrema == (0, 0)
        
    def _fallback_cv2(self, img_pil, mask_pil):
        """Standard OpenCV Telea Inpainting"""
        import cv2
        img_np = np.array(img_pil)
        mask_np = np.array(mask_pil)
        
        # Ensure mask is single channel uint8
        if len(mask_np.shape) == 3: mask_np = mask_np[:, :, 0]
        
        # Inpaint
        # cv2.inpaint expects BGR usually, but RGB works if consistent.
        # radius=3, flags=cv2.INPAINT_TELEA
        res_np = cv2.inpaint(img_np, mask_np, 3, cv2.INPAINT_TELEA)
        
        return Image.fromarray(res_np)
