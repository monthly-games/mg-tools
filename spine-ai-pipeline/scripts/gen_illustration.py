#!/usr/bin/env python3
"""
Stable Diffusion을 활용한 캐릭터 일러스트 생성 스크립트

사용법:
    python gen_illustration.py --config config.json
    python gen_illustration.py --prompt "pixel anime warrior"
"""

import argparse
import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import io
from PIL import Image
import requests
from rich.console import Console
from rich.progress import Progress

remove_bg = None

try:
    from rembg import remove as rembg_remove

    remove_bg = rembg_remove
    has_rembg = True
except ImportError:
    has_rembg = False

console = Console()

# Stable Diffusion WebUI API 기본 설정
SD_API_URL = os.getenv("SD_API_URL", "http://localhost:7860")
COMFY_API_URL = os.getenv("COMFY_API_URL", "http://192.168.50.165:8190")


def load_config(config_path: str) -> dict[str, Any]:
    """설정 파일 로드"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_prompt(config: Mapping[str, Any]) -> str:
    """설정에서 프롬프트 생성"""
    style = config.get("style", "anime")
    description = config.get("description", "")
    emotion = config.get("emotion", "")

    prompt_parts = [
        f"{style} style",
        description,
        f"expression: {emotion}" if emotion else "",
        "high quality, detailed, game character",
        "white background, simple background, full body, standing",
    ]

    return ", ".join(filter(None, prompt_parts))


def call_sd_api(
    prompt: str,
    output_path: Path,
    config: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Stable Diffusion API 호출 및 배경 제거"""
    payload = {
        "prompt": prompt,
        "negative_prompt": "low quality, blurry, distorted, extra limbs, cropped, worst quality, lowres, text, watermark, signature, background elements",
        "steps": config.get("steps", 30) if config else 30,
        "width": config.get("width", 1024) if config else 1024,
        "height": config.get("height", 1024) if config else 1024,
        "cfg_scale": config.get("cfg_scale", 7) if config else 7,
        "sampler_name": config.get("sampler", "DPM++ 2M Karras") if config else "DPM++ 2M Karras",
    }

    try:
        response = requests.post(
            f"{SD_API_URL}/sdapi/v1/txt2img",
            json=payload,
            timeout=120
        )
        response.raise_for_status()

        result = response.json()
        if "images" in result and result["images"]:
            image_data = base64.b64decode(result["images"][0])
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 1. 배경 제거 (rembg)
            if has_rembg and remove_bg is not None:
                console.print("[cyan]배경 제거 중... (rembg)[/cyan]")
                try:
                    img = Image.open(io.BytesIO(image_data))
                    img_no_bg = remove_bg(img)
                    if isinstance(img_no_bg, bytes):
                        output_path.write_bytes(img_no_bg)
                    else:
                        if not isinstance(img_no_bg, Image.Image):
                            img_no_bg = Image.fromarray(img_no_bg)
                        img_no_bg.save(output_path, "PNG")
                    console.print("[green]배경 제거 완료[/green]")
                except Exception as e:
                    console.print(f"[yellow]배경 제거 실패 (원본 저장): {e}[/yellow]")
                    with open(output_path, "wb") as f:
                        f.write(image_data)
            else:
                console.print("[yellow]rembg 모듈 없음: 원본 저장[/yellow]")
                with open(output_path, "wb") as f:
                    f.write(image_data)
                    
            return True
        return False

    except requests.exceptions.RequestException as e:
        console.print(f"[red]API 호출 실패: {e}[/red]")
        return False


def call_comfyui_api(
    prompt: str,
    output_path: Path,
    config: Optional[Mapping[str, Any]] = None,
) -> bool:
    """ComfyUI API 호출 및 배경 제거"""
    neg_prompt = "low quality, blurry, distorted, extra limbs, cropped, worst quality, lowres, text, watermark, signature, background elements"
    steps = config.get("steps", 30) if config else 30
    width = config.get("width", 1024) if config else 1024
    height = config.get("height", 1024) if config else 1024
    cfg_scale = config.get("cfg_scale", 7.0) if config else 7.0
    seed = config.get("seed", 777) if config else 777
    sampler = config.get("sampler", "euler_ancestral") if config else "euler_ancestral"
    comfy_model = (
        config.get("comfy_model", "Lunark/novaAnimeXL_ilV100.safetensors")
        if config
        else "Lunark/novaAnimeXL_ilV100.safetensors"
    )

    workflow = {
        "prompt": {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": comfy_model},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": neg_prompt, "clip": ["4", 1]},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg_scale,
                    "sampler_name": sampler,
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"images": ["8", 0], "filename_prefix": "comfy_gen"},
            },
        }
    }

    try:
        console.print("[cyan]ComfyUI 워크플로우 전송 중...[/cyan]")
        resp = requests.post(
            f"{COMFY_API_URL}/prompt",
            json=workflow,
            timeout=30,
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]
        console.print(f"[cyan]프롬프트 ID: {prompt_id} - 생성 대기 중...[/cyan]")

        # 폴링: 최대 300초
        timeout_sec = 300
        poll_interval = 3
        elapsed = 0
        result_data = None

        while elapsed < timeout_sec:
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                hist_resp = requests.get(
                    f"{COMFY_API_URL}/history/{prompt_id}",
                    timeout=15,
                )
                hist_resp.raise_for_status()
                history = hist_resp.json()
            except requests.exceptions.RequestException:
                continue

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                if "9" in outputs and "images" in outputs["9"]:
                    result_data = outputs["9"]["images"][0]
                    break

        if result_data is None:
            console.print("[red]ComfyUI 타임아웃: 이미지 생성 실패[/red]")
            return False

        # 이미지 다운로드
        filename = result_data["filename"]
        subfolder = result_data.get("subfolder", "")
        img_type = result_data.get("type", "output")

        view_url = f"{COMFY_API_URL}/view?filename={filename}&type={img_type}"
        if subfolder:
            view_url += f"&subfolder={subfolder}"

        console.print(f"[cyan]이미지 다운로드 중: {filename}[/cyan]")
        img_resp = requests.get(view_url, timeout=60)
        img_resp.raise_for_status()
        image_data = img_resp.content

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 배경 제거 (rembg) — call_sd_api와 동일 로직
        if has_rembg and remove_bg is not None:
            console.print("[cyan]배경 제거 중... (rembg)[/cyan]")
            try:
                img = Image.open(io.BytesIO(image_data))
                img_no_bg = remove_bg(img)
                if isinstance(img_no_bg, bytes):
                    output_path.write_bytes(img_no_bg)
                else:
                    if not isinstance(img_no_bg, Image.Image):
                        img_no_bg = Image.fromarray(img_no_bg)
                    img_no_bg.save(output_path, "PNG")
                console.print("[green]배경 제거 완료[/green]")
            except Exception as e:
                console.print(f"[yellow]배경 제거 실패 (원본 저장): {e}[/yellow]")
                with open(output_path, "wb") as f:
                    f.write(image_data)
        else:
            console.print("[yellow]rembg 모듈 없음: 원본 저장[/yellow]")
            with open(output_path, "wb") as f:
                f.write(image_data)

        return True

    except requests.exceptions.ConnectionError as e:
        console.print(f"[red]ComfyUI 연결 실패: {e}[/red]")
        return False
    except requests.exceptions.Timeout as e:
        console.print(f"[red]ComfyUI 요청 타임아웃: {e}[/red]")
        return False
    except requests.exceptions.RequestException as e:
        console.print(f"[red]ComfyUI API 호출 실패: {e}[/red]")
        return False
    except (KeyError, IndexError) as e:
        console.print(f"[red]ComfyUI 응답 파싱 실패: {e}[/red]")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="캐릭터 일러스트 생성")
    parser.add_argument("--config", type=str, help="설정 파일 경로")
    parser.add_argument("--prompt", type=str, help="직접 프롬프트 입력")
    parser.add_argument("--output", type=str, default="output", help="출력 경로")
    parser.add_argument(
        "--backend",
        type=str,
        choices=["sd", "comfy"],
        default="comfy",
        help="이미지 생성 백엔드 (기본: comfy)",
    )
    args = parser.parse_args()

    if not args.config and not args.prompt:
        console.print("[red]--config 또는 --prompt 중 하나를 지정하세요[/red]")
        return 1

    if args.config:
        config = load_config(args.config)
        character_id = config.get("character_id", "char_unknown")
        prompt = generate_prompt(config)
    else:
        config = None
        character_id = "char_manual"
        prompt = args.prompt

    output_path = Path(args.output) / character_id / "illustration.png"

    console.print(f"[blue]캐릭터: {character_id}[/blue]")
    console.print(f"[blue]프롬프트: {prompt}[/blue]")

    with Progress() as progress:
        task = progress.add_task("[green]생성 중...", total=100)

        if args.backend == "comfy":
            success = call_comfyui_api(prompt, output_path, config)
        else:
            success = call_sd_api(prompt, output_path, config)
        progress.update(task, completed=100)

    if success:
        console.print(f"[green]OK generated: {output_path}[/green]")
        return 0
    else:
        console.print("[red]FAILED image generation[/red]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
