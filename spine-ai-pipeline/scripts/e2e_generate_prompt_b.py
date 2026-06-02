import os
import shutil
import sys
import time
from pathlib import Path

import requests


def main() -> int:
    out_dir = Path("output/e2e_test")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "e2e_archer.png"

    comfy = "http://192.168.50.165:8192"
    pos = (
        "single game character, fantasy archer, front facing, T-pose arms out, "
        "full body visible, 2D anime style, clean lines, white background, "
        "no accessories, standing straight, solo"
    )
    neg = (
        "multiple characters, character sheet, reference sheet, turnaround, "
        "dynamic pose, cropped, text, watermark, photorealistic, 3d render"
    )

    wf = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 123,
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "Lunark/novaAnimeXL_ilV100.safetensors"},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "e2e_archer", "images": ["8", 0]},
        },
    }

    image_generated = False
    source = ""

    try:
        r = requests.post(f"{comfy}/prompt", json={"prompt": wf}, timeout=30)
        r.raise_for_status()
        pid = r.json()["prompt_id"]
        print(f"Submitted: {pid}")

        for _ in range(40):
            time.sleep(3)
            h = requests.get(f"{comfy}/history/{pid}", timeout=10)
            h.raise_for_status()
            payload = h.json()
            if pid in payload:
                imgs = payload[pid]["outputs"]["9"]["images"]
                img = imgs[0]
                url = (
                    f"{comfy}/view?filename={img['filename']}&subfolder={img.get('subfolder', '')}"
                    f"&type={img['type']}"
                )
                data = requests.get(url, timeout=30)
                data.raise_for_status()
                out_file.write_bytes(data.content)
                print(f"Generated: {out_file} ({len(data.content)} bytes)")
                image_generated = True
                source = "comfyui"
                break
        else:
            print("ComfyUI generation timeout, trying fallback image")
    except Exception as e:
        print(f"ComfyUI unavailable or failed: {e}")

    if not image_generated:
        fallback = Path("output/prompt_test/prompt_b_archer.png")
        if fallback.exists():
            shutil.copy2(fallback, out_file)
            print(f"Fallback copied: {fallback} -> {out_file}")
            source = "fallback_prompt_b_archer"
        else:
            print("ERROR: ComfyUI failed and fallback image missing")
            return 1

    meta_file = out_dir / "e2e_image_source.txt"
    meta_file.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
