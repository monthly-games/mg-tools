
import os
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

class MattingEngine:
    def __init__(self, model_path="models/modnet.onnx"):
        self.session = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        if not os.path.exists(self.model_path):
            print(f"[Matting] Model not found at {self.model_path}. Please download it.")
            return

        try:
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            if 'CUDAExecutionProvider' not in ort.get_available_providers():
                providers = ['CPUExecutionProvider']
            
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            print("[Matting] MODNet loaded successfully.")
        except Exception as e:
            print(f"[Matting] Failed to load MODNet: {e}")

    def infer(self, img_pil):
        """
        Infer alpha matte from PIL Image.
        Returns: normalized alpha numpy array (H, W) float32 [0, 1]
        """
        if self.session is None:
            return None

        # Preprocess
        # MODNet expects (1, 3, 512, 512) normalized [-1, 1]
        w, h = img_pil.size
        target_size = 512
        
        im = np.asarray(img_pil)
        if len(im.shape) == 2:
            im = im[:, :, None]
        if im.shape[2] == 1:
            im = np.repeat(im, 3, axis=2)
        elif im.shape[2] == 4:
            im = im[:, :, 0:3]
            
        im_resized = cv2.resize(im, (target_size, target_size), interpolation=cv2.INTER_AREA)
        im_normalized = (im_resized.astype(np.float32) / 127.5) - 1.0
        im_transposed = np.transpose(im_normalized, (2, 0, 1))
        im_batch = im_transposed[None, :, :, :]
        
        # Inference
        input_name = self.session.get_inputs()[0].name
        output = self.session.run(None, {input_name: im_batch})
        matte = output[0][0, 0, :, :] # (512, 512)
        
        # Postprocess
        matte = cv2.resize(matte, (w, h), interpolation=cv2.INTER_LINEAR)
        matte = np.clip(matte, 0, 1)
        
        return matte

    def _filter_largest_component(self, alpha_uint8):
        """
        Keep only the largest connected component in the alpha channel
        to remove floating noise (islands).
        """
        # Binarize
        _, thresh = cv2.threshold(alpha_uint8, 10, 255, cv2.THRESH_BINARY)
        
        # Connected Components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        
        if num_labels <= 1:
            return alpha_uint8
            
        # Find largest component (excluding background at 0)
        largest_label = 1
        max_area = 0
        
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area > max_area:
                max_area = area
                largest_label = i
                
        # Create mask for largest component
        mask = (labels == largest_label).astype(np.uint8) * 255
        
        # Apply mask to original alpha (preserve soft edges of the main component)
        filtered_alpha = cv2.bitwise_and(alpha_uint8, alpha_uint8, mask=mask)
        
        # Optional: Dilate the mask slightly to recover soft edges that might have been cut off?
        # For now, bitwise_and ensures we keep the original soft scale within the mask.
        # But if the soft edge was part of the component, it is kept.
        # If it was a separate island, it is removed.
        
        return filtered_alpha

    def extract_alpha(self, img_pil):
        """
        Returns the alpha channel as a PIL Image (L mode).
        """
        matte = self.infer(img_pil)
        if matte is None:
            return None
            
        alpha_uint8 = (matte * 255).astype(np.uint8)
        
        # [Improvement] Filter Noise
        alpha_uint8 = self._filter_largest_component(alpha_uint8)
        
        return Image.fromarray(alpha_uint8, mode='L')
