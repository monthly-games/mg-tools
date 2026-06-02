
import gradio as gr
import numpy as np
from PIL import Image
from diffusers import StableDiffusionInpaintPipeline
import torch
import research_matting # Reuse our matting logic
# import research_inpainting # Reuse inpainting

# Globals
pipe = None
matting_session = None

def load_models():
    global pipe, matting_session
    if pipe is None:
        print("Loading SD...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipe = StableDiffusionInpaintPipeline.from_pretrained(
            "runwayml/stable-diffusion-inpainting",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32
        ).to(device)
    
    if matting_session is None:
        print("Loading MODNet...")
        matting_session = research_matting.load_modnet_onnx("models/modnet.onnx")

def process_segmentation(input_img):
    load_models()
    # Run matting
    matte = research_matting.infer_modnet(matting_session, input_img)
    # Convert to RGBA
    img_np = np.array(input_img)
    alpha = (matte * 255).astype(np.uint8)
    rgba = np.dstack((img_np, alpha))
    return Image.fromarray(rgba), matte # Return RGBA and Mask

def run_inpainting(input_img, mask_img, prompt):
    load_models()
    # input_img is the background/original?
    # mask_img from gradio sketch is usually the mask.
    
    # Resize
    image = input_img.convert("RGB").resize((512, 512))
    mask = mask_img.convert("L").resize((512, 512))
    
    output = pipe(prompt=prompt, image=image, mask_image=mask).images[0]
    return output

with gr.Blocks() as demo:
    gr.Markdown("# Spine AI Pipeline - Verification Tool")
    
    with gr.Tab("Matting Refinement"):
        with gr.Row():
            in_img = gr.Image(type="pil", label="Input Image")
            out_img = gr.Image(type="pil", label="Matting Result")
        btn_mat = gr.Button("Auto-Segment")
        btn_mat.click(process_segmentation, inputs=in_img, outputs=[out_img])
        
    with gr.Tab("Inpainting Correction"):
        with gr.Row():
            in_paint_img = gr.Image(source="upload", tool="sketch", type="pil", label="Draw Mask")
            prompt = gr.Textbox(label="Prompt", value="detailed texture, high quality")
            out_paint = gr.Image(label="Result")
        btn_paint = gr.Button("Inpaint")
        btn_paint.click(run_inpainting, inputs=[in_paint_img, in_paint_img], outputs=out_paint) 
        # Note: Gradio Image(sketch) returns structured data or image? 
        # Need to handle mask extraction from sketch properly.

if __name__ == "__main__":
    demo.launch()
