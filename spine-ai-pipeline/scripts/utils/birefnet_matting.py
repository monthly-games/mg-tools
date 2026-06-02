
import torch
import numpy as np
from PIL import Image
from transformers import AutoModelForImageSegmentation
from torchvision import transforms

class BiRefNetEngine:
    def __init__(self, model_vis="ZhengPeng7/BiRefNet", device=None):
        self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model_vis = model_vis
        self.model = None
        self.transform_image = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        self._load_model()

    def _load_model(self):
        try:
            print(f"[BiRefNet] Loading model: {self.model_vis} on {self.device}...")
            self.model = AutoModelForImageSegmentation.from_pretrained(self.model_vis, trust_remote_code=True)
            self.model.to(self.device)
            self.model.eval()
            print("[BiRefNet] Model loaded successfully.")
        except Exception as e:
            print(f"[BiRefNet] Failed to load model: {e}")
            self.model = None

    def extract_alpha(self, img_pil):
        """
        Extract alpha matte from PIL image using BiRefNet.
        Returns: PIL Image (L mode)
        """
        if self.model is None:
            return None

        w, h = img_pil.size
        
        # Prepare input
        input_images = self.transform_image(img_pil).unsqueeze(0).to(self.device)

        # Inference
        with torch.no_grad():
            preds = self.model(input_images)[-1].sigmoid().cpu()
        
        # Post-process
        pred = preds[0].squeeze()
        pred_pil = transforms.ToPILImage()(pred)
        matte = pred_pil.resize((w, h), Image.BILINEAR)
        
        return matte

    def _filter_largest_component(self, alpha_uint8):
        """
        Reuse the noise filtering logic if needed, or import from utils.matting
        For now, let's keep it self-contained or simple.
        BiRefNet usually produces cleaner masks, but filtering is still good safety.
        """
        import cv2
        _, thresh = cv2.threshold(alpha_uint8, 10, 255, cv2.THRESH_BINARY)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        if num_labels <= 1: return alpha_uint8
        
        largest_label = 1
        max_area = 0
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area > max_area:
                max_area = area
                largest_label = i
        
        mask = (labels == largest_label).astype(np.uint8) * 255
        filtered_alpha = cv2.bitwise_and(alpha_uint8, alpha_uint8, mask=mask)
        return filtered_alpha
