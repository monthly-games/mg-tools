#!/usr/bin/env python3
"""
Stable Diffusion을 활용한 캐릭터 일러스트 생성 스크립트

사용법:
    python gen_illustration.py --config config.json
    python gen_illustration.py --prompt "pixel anime warrior"
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.progress import Progress

console = Console()

# Stable Diffusion WebUI API 기본 설정
SD_API_URL = os.getenv("SD_API_URL", "http://localhost:7860")


def load_config(config_path: str) -> dict:
    """설정 파일 로드"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_prompt(config: dict) -> str:
    """설정에서 프롬프트 생성"""
    style = config.get("style", "anime")
    description = config.get("description", "")
    emotion = config.get("emotion", "")

    prompt_parts = [
        f"{style} style",
        description,
        f"expression: {emotion}" if emotion else "",
        "high quality, detailed, game character",
    ]

    return ", ".join(filter(None, prompt_parts))


def call_sd_api(prompt: str, output_path: Path, config: Optional[dict] = None) -> bool:
    """Stable Diffusion API 호출"""
    payload = {
        "prompt": prompt,
        "negative_prompt": "low quality, blurry, distorted, extra limbs",
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
            import base64
            image_data = base64.b64decode(result["images"][0])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_data)
            return True
        return False

    except requests.exceptions.RequestException as e:
        console.print(f"[red]API 호출 실패: {e}[/red]")
        return False


def main():
    parser = argparse.ArgumentParser(description="캐릭터 일러스트 생성")
    parser.add_argument("--config", type=str, help="설정 파일 경로")
    parser.add_argument("--prompt", type=str, help="직접 프롬프트 입력")
    parser.add_argument("--output", type=str, default="output", help="출력 경로")
    args = parser.parse_args()

    if not args.config and not args.prompt:
        console.print("[red]--config 또는 --prompt 중 하나를 지정하세요[/red]")
        return

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

        success = call_sd_api(prompt, output_path, config)
        progress.update(task, completed=100)

    if success:
        console.print(f"[green]✓ 생성 완료: {output_path}[/green]")
    else:
        console.print("[red]✗ 생성 실패[/red]")


if __name__ == "__main__":
    main()
