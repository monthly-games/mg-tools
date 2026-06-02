
import cv2
import numpy as np
import onnxruntime as ort
import argparse
from pathlib import Path
from PIL import Image

def load_modnet_onnx(model_path):
    """Load MODNet ONNX model."""
    if not Path(model_path).exists():
        download_modnet(model_path)
    
    session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    return session

def download_modnet(path):
    """Download MODNet ONNX model (placeholder logic)."""
    print(f"Downloading MODNet to {path}...")
    import requests
    # Official or reliable source for MODNet ONNX
    url = "https://huggingface.co/gradio/Modnet/resolve/main/modnet.onnx"
    # Note: We need a generic matting model, portrait might be biased but good restart point.
    
    print(f"Downloading from {url}...")
    r = requests.get(url, allow_redirects=True)
    if r.status_code != 200:
        raise Exception(f"Download failed: {r.status_code}")
    with open(path, 'wb') as f:
        f.write(r.content)

def infer_modnet(session, img_pil):
    """
    Run MODNet inference.
    img_pil: PIL Image (RGB)
    """
    # Preprocess
    # MODNet expects 512x512 usually, or dynamic? 
    # Standard is 512x512 resize for inference, then upscale alpha.
    
    ref_size = 512
    img = np.array(img_pil)
    h, w, c = img.shape
    if c == 4: img = img[:,:,:3] # Drop alpha if exists

    # Resize to modnet input
    im_resized = cv2.resize(img, (ref_size, ref_size), interpolation=cv2.INTER_AREA)
    
    # Normalize [0, 1] and (N,C,H,W)
    im_tensor = im_resized.astype(np.float32) / 255.0
    im_tensor = (im_tensor - 0.5) / 0.5 # Normalization if required? 
    # MODNet paper: image / 127.5 - 1.0 (which is (img/255 - 0.5)/0.5)
    
    im_tensor = np.transpose(im_tensor, (2, 0, 1))
    im_tensor = im_tensor[None, :, :, :]
    
    # Inference
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    
    matte = session.run([output_name], {input_name: im_tensor})[0]
    
    # matte is (N, 1, H, W)
    matte = matte[0, 0, :, :]
    
    # Post-process
    # Resize matte back to original size
    matte_resized = cv2.resize(matte, (w, h), interpolation=cv2.INTER_LINEAR)
    
    # Matte is sigmoid output? usually raw values. Clip 0..1
    matte_resized = np.clip(matte_resized, 0, 1)
    
    return matte_resized

def process_image(img_path, output_path, session):
    img = Image.open(img_path).convert('RGB')
    matte = infer_modnet(session, img)
    
    # Apply Alpha
    img_np = np.array(img)
    alpha = (matte * 255).astype(np.uint8)
    
    # Create RGBA
    result = np.dstack((img_np, alpha))
    Image.fromarray(result).save(output_path)
    print(f"Saved to {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="models/modnet.onnx")
    args = parser.parse_args()
    
    Path("models").mkdir(exist_ok=True)
    
    sess = load_modnet_onnx(args.model)
    process_image(args.input, args.output, sess)

if __name__ == "__main__":
    main()
