#!/usr/bin/env python3
"""
배경 제거 및 품질 검사 스크립트
사용법: python remove_background.py --input image.jpg --output image_nobg.png
"""

import argparse
from pathlib import Path
import sys
import numpy as np
import cv2
from PIL import Image

# rembg는 무거우므로 필요할 때만 임포트
try:
    from rembg import remove, new_session
    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False

from rich.console import Console
console = Console()

def validate_background_removal(image: Image.Image) -> bool:
    """배경 제거 품질 검사"""
    # PIL -> OpenCV
    img_np = np.array(image)
    
    # 1. 알파 채널 확인
    if img_np.shape[2] != 4:
        console.print("[red]QA 실패: 알파 채널이 없습니다.[/red]")
        return False
        
    alpha = img_np[:, :, 3]
    
    # 2. 내용물 비율 확인 (너무 많이 지워졌는지)
    total_pixels = alpha.size
    non_zero_pixels = np.count_nonzero(alpha)
    fill_ratio = non_zero_pixels / total_pixels
    
    console.print(f"[dim]QA: 이미지 채움 비율 {fill_ratio*100:.2f}%[/dim]")
    
    if fill_ratio < 0.05: # 5% 미만이면 거의 다 지워진 것
        console.print("[red]QA 실패: 이미지가 거의 다 지워졌습니다. (내용물 < 5%)[/red]")
        return False
        
    # 3. 덩어리(Contour) 확인 - 너무 자잘하게 깨졌는지
    # 이진화
    _, thresh = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        console.print("[red]QA 실패: 감지된 객체가 없습니다.[/red]")
        return False
        
    # 가장 큰 덩어리 찾기
    max_area = max(cv2.contourArea(c) for c in contours)
    
    # 전체 내용물 대비 가장 큰 덩어리의 비율
    # (이 비율이 낮으면 노이즈가 많거나 산산조각 난 것)
    # contourArea는 픽셀 수와 비슷하지만 정확히 같지는 않음
    
    # 간단하게: 의미있는 크기(전체의 1% 이상)의 덩어리 개수
    significant_contours = [c for c in contours if cv2.contourArea(c) > (total_pixels * 0.01)]
    
    if len(significant_contours) == 0:
        console.print("[red]QA 실패: 의미있는 크기의 객체가 없습니다.[/red]")
        return False
        
    if len(significant_contours) > 5:
        console.print(f"[yellow]QA 경고: 객체가 {len(significant_contours)}개로 조각나 있습니다. 깔끔하지 않을 수 있습니다.[/yellow]")
        
    return True

def process_image(input_path: Path, output_path: Path):
    if not HAS_REMBG:
        console.print("[red]오류: rembg 모듈이 설치되지 않았습니다.[/red]")
        sys.exit(1)
        
    console.print(f"[cyan]배경 제거 시작: {input_path.name}[/cyan]")
    
    try:
        img = Image.open(input_path)
        
        # [Optimization] Resize if too big (Max 2048px)
        max_dim = 2048
        if max(img.width, img.height) > max_dim:
            scale = max_dim / max(img.width, img.height)
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            console.print(f"[yellow]이미지가 너무 큽니다 ({img.width}x{img.height}). {max_dim}px로 리사이징합니다 -> {new_w}x{new_h}[/yellow]")
            img = img.resize((new_w, new_h), Image.LANCZOS)
        
        # 세션 생성 (isnet-anime 모델 사용 - 캐릭터에 최적화)
        session = new_session("isnet-anime")
        
        try:
            # 배경 제거 (Alpha Matting 옵션 활성화로 경계선 부드럽게)
            result = remove(
                img, 
                session=session,
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10
            )
        except Exception as e:
            console.print(f"[yellow]Alpha Matting 실패: {e}. 일반 모드로 재시도합니다.[/yellow]")
            result = remove(img, session=session, alpha_matting=False)

        # 품질 검사
        if validate_background_removal(result):
            console.print("[green]QA 통과[/green]")
            result.save(output_path)
            console.print(f"[green]저장 완료: {output_path}[/green]")
        else:
            console.print("[red]QA 실패로 인해 저장을 보류합니다. (강제 저장하려면 옵션 필요)[/red]")
            # 디버깅을 위해 _failed 접미어로 저장
            failed_path = output_path.parent / f"{output_path.stem}_failed.png"
            result.save(failed_path)
            console.print(f"[yellow]실패한 결과 저장됨: {failed_path}[/yellow]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]처리 중 오류 발생: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    process_image(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()
