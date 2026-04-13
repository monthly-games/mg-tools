#!/usr/bin/env python3
"""
캐릭터 일러스트 파츠 자동 분리 스크립트

사용법:
    python split_parts.py --input illustration.png --output parts/
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from rich.console import Console

console = Console()

# 기본 파츠 정의
DEFAULT_PARTS = [
    "head",
    "body",
    "arm_L",
    "arm_R",
    "leg_L",
    "leg_R",
    "weapon",
]



# Keypoint Indices (COCO)
KP = {
    "nose": 0, "eye_l": 1, "eye_r": 2, "ear_l": 3, "ear_r": 4,
    "shdr_l": 5, "shdr_r": 6,
    "elb_l": 7, "elb_r": 8,
    "wr_l": 9, "wr_r": 10,
    "hip_l": 11, "hip_r": 12,
    "knee_l": 13, "knee_r": 14,
    "ank_l": 15, "ank_r": 16
}

def get_cut_line(p_start, p_joint, p_end):
    """Calculate a cut line passing through p_joint, perpendicular to limb vector."""
    vx = p_end[0] - p_start[0]
    vy = p_end[1] - p_start[1]
    
    px = -vy
    py = vx
    
    norm = (px*px + py*py)**0.5
    if norm < 0.001: return None
    
    px /= norm
    py /= norm
    
    limb_len = (vx*vx + vy*vy)**0.5
    cut_len = limb_len * 0.8 # Wide enough to cover the limb width
    
    x1 = int(p_joint[0] - px * cut_len)
    y1 = int(p_joint[1] - py * cut_len)
    x2 = int(p_joint[0] + px * cut_len)
    y2 = int(p_joint[1] + py * cut_len)
    
    return ((x1, y1), (x2, y2))

def split_limb_using_pose(part_img_bgra, part_name, output_dir, global_kpts, part_box_xyxy, scale_factor=1.0):
    """
    Sub-split a limb part into Upper/Lower segments using GLOBAL pose keypoints.
    """
    try:
        from PIL import Image
        import numpy as np
        import cv2
        
        h, w = part_img_bgra.shape[:2]
        
        # Part Box (Global Coords on original image scale)
        # Note: global_kpts are also on original image scale.
        x1_box, y1_box, x2_box, y2_box = part_box_xyxy
        
        # Keypoints are already available
        if global_kpts is None:
            return []
            
        def get_p(idx):
             # kpts is (17, 3) [x, y, conf] or (17, 2)?
             # Check shape in main
             if idx < len(global_kpts):
                 p = global_kpts[idx]
                 if len(p) >= 3 and p[2] < 0.3: return None # Low conf
                 if p[0] <= 0 or p[1] <= 0: return None
                 return p[:2] # x, y
             return None
        
        # Define joints based on part name
        target_joints = None
        if part_name == "arm_L": target_joints = (KP["shdr_l"], KP["elb_l"], KP["wr_l"])
        elif part_name == "arm_R": target_joints = (KP["shdr_r"], KP["elb_r"], KP["wr_r"])
        elif part_name == "leg_L": target_joints = (KP["hip_l"], KP["knee_l"], KP["ank_l"])
        elif part_name == "leg_R": target_joints = (KP["hip_r"], KP["knee_r"], KP["ank_r"])
        
        if not target_joints: return []
        
        i_s, i_j, i_e = target_joints
        
        p_s = get_p(i_s)
        p_j = get_p(i_j)
        p_e = get_p(i_e)
        
        if p_s is not None and p_j is not None and p_e is not None:
             # Calculate cut line in GLOBAL space
             line_global = get_cut_line(p_s, p_j, p_e)
             if not line_global: return []
             
             (gx1, gy1), (gx2, gy2) = line_global
             
             # Convert Line Global -> Local Part Space
             lx1 = gx1 - x1_box
             ly1 = gy1 - y1_box
             lx2 = gx2 - x1_box
             ly2 = gy2 - y1_box
             
             # Local Joint
             ljx = p_j[0] - x1_box
             ljy = p_j[1] - y1_box
             
             # Validation: Joint must be effectively inside the part box
             # Relaxed margin (e.g. -50 to w+50) to allow cutting near edges
             if not (-50 <= ljx <= w + 50 and -50 <= ljy <= h + 50):
                 console.print(f"[yellow]    > 관절 위치 불일치 (Joint outside box): ({ljx:.1f}, {ljy:.1f}) in {w}x{h}[/yellow]")
                 return []
             
             console.print(f"[dim]    Debug: Joint Inside logic passed.[/dim]")

             
             # Local End for signing
             lex = p_e[0] - x1_box
             ley = p_e[1] - y1_box
             
             # Create Cut Mask
             mask_lower = np.zeros((h, w), dtype=np.uint8)
             y_grid, x_grid = np.indices((h, w))
             
             vx_line = lx2 - lx1
             vy_line = ly2 - ly1
             nx, ny = -vy_line, vx_line
             
             # Check sign with Local End point
             dot_end = nx * (lex - lx1) + ny * (ley - ly1)
             if dot_end < 0: nx, ny = -nx, -ny
             
             val = nx * (x_grid - lx1) + ny * (y_grid - ly1)
             mask_lower[val > 0] = 255
             
             # Split
             lower_img = part_img_bgra.copy()
             lower_img[:, :, 3] = np.minimum(lower_img[:, :, 3], mask_lower)
             
             upper_img = part_img_bgra.copy()
             upper_img[:, :, 3] = np.minimum(upper_img[:, :, 3], 255 - mask_lower)
             
             lower_name = f"{part_name}_lower"
             upper_name = f"{part_name}_upper"
             
             Image.fromarray(lower_img).save(output_dir / f"{lower_name}.png")
             Image.fromarray(upper_img).save(output_dir / f"{upper_name}.png")
             
             console.print(f"[green]    > 관절 분리 성공: {upper_name}, {lower_name}[/green]")
             
             return [
                 {"name": lower_name, "file": f"{lower_name}.png"},
                 {"name": upper_name, "file": f"{upper_name}.png"}
             ]
             
        return []
            
    except Exception as e:
        console.print(f"[yellow]    > 관절 분리 중 오류: {e}[/yellow]")
        return []


def generate_trimap(mask_image, dilate=10, erode=5):
    """Generate trimap from binary mask (0:BG, 128:Unknown, 255:FG)."""
    import numpy as np
    import cv2

    mask_uint8 = np.asarray(mask_image)
    if mask_uint8.ndim == 3:
        mask_uint8 = mask_uint8[:, :, 0]
    if mask_uint8.dtype != np.uint8:
        mask_uint8 = np.clip(mask_uint8, 0, 255).astype(np.uint8)

    binary_mask = (mask_uint8 > 0).astype(np.uint8) * 255

    dilate_kernel = np.ones((dilate, dilate), np.uint8)
    erode_kernel = np.ones((erode, erode), np.uint8)

    sure_fg = cv2.erode(binary_mask, erode_kernel, iterations=1)
    expanded_fg = cv2.dilate(binary_mask, dilate_kernel, iterations=1)

    trimap = np.full(binary_mask.shape, 128, dtype=np.uint8)
    trimap[expanded_fg == 0] = 0
    trimap[sure_fg > 0] = 255
    return trimap


def closed_form_matting(image_rgb, trimap, beta=90.0):
    """Closed-form style alpha estimation with sparse linear solve."""
    import numpy as np
    from scipy import sparse
    from scipy.sparse import linalg as sparse_linalg

    image = np.asarray(image_rgb)
    if image.dtype != np.float32:
        image = image.astype(np.float32) / 255.0

    known_fg = trimap == 255
    known_bg = trimap == 0
    unknown = ~(known_fg | known_bg)

    alpha = known_fg.astype(np.float32)
    unknown_count = int(np.count_nonzero(unknown))
    if unknown_count == 0:
        return alpha

    h, w = trimap.shape
    unknown_indices = -np.ones((h, w), dtype=np.int32)
    unknown_positions = np.argwhere(unknown)
    unknown_indices[unknown] = np.arange(unknown_count)

    rows = []
    cols = []
    vals = []
    rhs = np.zeros(unknown_count, dtype=np.float32)

    eps = 1e-6
    neighbors = ((-1, 0), (1, 0), (0, -1), (0, 1))

    for idx, (y, x) in enumerate(unknown_positions):
        color_p = image[y, x]
        diag = eps

        for dy, dx in neighbors:
            ny = y + dy
            nx = x + dx
            if ny < 0 or ny >= h or nx < 0 or nx >= w:
                continue

            color_q = image[ny, nx]
            color_dist = float(np.dot(color_p - color_q, color_p - color_q))
            weight = float(np.exp(-beta * color_dist)) + eps

            diag += weight
            if unknown[ny, nx]:
                neighbor_idx = unknown_indices[ny, nx]
                rows.append(idx)
                cols.append(neighbor_idx)
                vals.append(-weight)
            elif known_fg[ny, nx]:
                rhs[idx] += weight

        rows.append(idx)
        cols.append(idx)
        vals.append(diag)

    system = sparse.csr_matrix((vals, (rows, cols)), shape=(unknown_count, unknown_count))

    alpha_unknown, info = sparse_linalg.cg(system, rhs, maxiter=300, atol=1e-5)
    if info != 0 or np.any(np.isnan(alpha_unknown)):
        alpha_unknown = sparse_linalg.spsolve(system, rhs)

    alpha[unknown] = np.clip(alpha_unknown, 0.0, 1.0)
    return alpha


def remove_small_islands(alpha, min_size=100, keep_largest_only=False):
    """Remove tiny disconnected components from alpha mask."""
    import numpy as np
    import cv2

    alpha_float = np.asarray(alpha).astype(np.float32)
    binary = (alpha_float > 0.45).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num_labels <= 1:
        return alpha_float

    areas = stats[1:, cv2.CC_STAT_AREA]
    if areas.size == 0:
        return alpha_float

    largest_label = int(np.argmax(areas)) + 1
    largest_area = int(stats[largest_label, cv2.CC_STAT_AREA])
    adaptive_min_size = max(min_size, int(largest_area * 0.02))

    keep = np.zeros_like(binary, dtype=np.uint8)

    for label_id in range(1, num_labels):
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if label_id == largest_label:
            keep[labels == label_id] = 1
        elif not keep_largest_only and area >= adaptive_min_size:
            keep[labels == label_id] = 1

    return alpha_float * keep.astype(np.float32)


def guided_filter(image_rgb, alpha, radius=5, eps=1e-4):
    """Fast guided filter for edge-aware alpha smoothing."""
    import numpy as np
    import cv2

    image = np.asarray(image_rgb)
    if image.ndim == 2:
        guide = image.astype(np.float32) / 255.0
    else:
        guide = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0

    p = np.asarray(alpha).astype(np.float32)

    ksize = (radius * 2 + 1, radius * 2 + 1)
    mean_guide = cv2.boxFilter(guide, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
    mean_p = cv2.boxFilter(p, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
    corr_guide = cv2.boxFilter(guide * guide, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
    corr_guide_p = cv2.boxFilter(guide * p, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)

    var_guide = corr_guide - mean_guide * mean_guide
    cov_guide_p = corr_guide_p - mean_guide * mean_p

    a = cov_guide_p / (var_guide + eps)
    b = mean_p - a * mean_guide

    mean_a = cv2.boxFilter(a, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)
    mean_b = cv2.boxFilter(b, cv2.CV_32F, ksize, borderType=cv2.BORDER_REFLECT)

    q = mean_a * guide + mean_b
    return np.clip(q, 0.0, 1.0)


def count_mask_islands(mask_image, min_size=8):
    """Count disconnected islands excluding the largest component."""
    import numpy as np
    import cv2

    mask_uint8 = np.asarray(mask_image)
    if mask_uint8.ndim == 3:
        mask_uint8 = mask_uint8[:, :, 0]
    binary = (mask_uint8 > 0).astype(np.uint8)

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num_labels <= 1:
        return 0

    areas = stats[1:, cv2.CC_STAT_AREA]
    if areas.size == 0:
        return 0

    largest_label = int(np.argmax(areas)) + 1
    islands = 0

    for label_id in range(1, num_labels):
        if label_id == largest_label:
            continue
        if int(stats[label_id, cv2.CC_STAT_AREA]) >= min_size:
            islands += 1

    return islands


def refine_alpha_channel(mask_image, guide_image, trimap_dilate=10, trimap_erode=5, min_size=100):
    """Apply trimap + closed-form matting + island cleanup + guided filtering."""
    import numpy as np
    import cv2

    mask_uint8 = np.asarray(mask_image)
    if mask_uint8.ndim == 3:
        mask_uint8 = mask_uint8[:, :, 0]
    if mask_uint8.dtype != np.uint8:
        mask_uint8 = np.clip(mask_uint8, 0, 255).astype(np.uint8)

    if mask_uint8.max() <= 1:
        mask_uint8 = (mask_uint8 * 255).astype(np.uint8)

    binary_mask = (mask_uint8 > 0).astype(np.uint8) * 255
    if not np.any(binary_mask):
        return binary_mask

    guide_rgb = np.asarray(guide_image)
    if guide_rgb.ndim == 2:
        guide_rgb = cv2.cvtColor(guide_rgb, cv2.COLOR_GRAY2RGB)
    elif guide_rgb.shape[2] == 4:
        guide_rgb = guide_rgb[:, :, :3]

    points = cv2.findNonZero(binary_mask)
    x, y, w, h = cv2.boundingRect(points)
    pad = max(trimap_dilate * 2, trimap_erode * 2, 8)

    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(binary_mask.shape[1], x + w + pad)
    y2 = min(binary_mask.shape[0], y + h + pad)

    mask_roi = binary_mask[y1:y2, x1:x2]
    guide_roi = guide_rgb[y1:y2, x1:x2]

    trimap = generate_trimap(mask_roi, dilate=trimap_dilate, erode=trimap_erode)

    try:
        alpha_roi = closed_form_matting(guide_roi, trimap)
    except Exception as error:
        console.print(f"[yellow]Alpha Matting fallback: {error}[/yellow]")
        alpha_roi = mask_roi.astype(np.float32) / 255.0

    alpha_roi = remove_small_islands(alpha_roi, min_size=min_size)
    alpha_roi = guided_filter(guide_roi, alpha_roi, radius=5, eps=1e-4)

    alpha_roi[trimap == 255] = 1.0
    alpha_roi[trimap == 0] = 0.0

    alpha_full = np.zeros_like(binary_mask, dtype=np.float32)
    alpha_full[y1:y2, x1:x2] = alpha_roi
    return (np.clip(alpha_full, 0.0, 1.0) * 255).astype(np.uint8)

def split_with_komiko(image_path: Path, output_dir: Path, matting_engine=None, inpainting_engine=None, post_process=True) -> Dict[str, Any]:
    """KomikoAI API를 사용한 파츠 분리 (플레이스홀더)"""
    # TODO: KomikoAI API 연동
    console.print("[yellow]KomikoAI API 연동 필요[/yellow]")
    return {"success": False, "method": "komiko"}


def split_with_sam(image_path: Path, output_dir: Path, matting_engine=None, inpainting_engine=None, post_process=True) -> Dict[str, Any]:
    """YOLO-World + SAM을 사용한 지능형 파츠 분리"""
    try:
        from ultralytics import YOLO, SAM
        from PIL import Image
        import numpy as np
        import cv2

        console.print("[cyan]모델 로딩 중... (YOLO-World + SAM)[/cyan]")
        
        # 1. YOLO-World 로드
        console.print("[cyan]Loading YOLO-World Large...[/cyan]")
        det_model = YOLO("yolov8l-worldv2.pt") 
        
        # 2. SAM 모델 로드
        console.print("[cyan]Loading SAM 2.1 Large...[/cyan]")
        sam_model = SAM("sam2.1_l.pt")

        img_pil = Image.open(image_path)
        
        # [Refinement] Background Removal (MODNet)
        global_alpha = None
        if matting_engine:
            engine_name = matting_engine.__class__.__name__.replace("Engine", "")
            console.print(f"[cyan]정밀 배경 제거 ({engine_name}) 처리 중...[/cyan]")
            try:
                # MODNet extraction
                alpha_pil = matting_engine.extract_alpha(img_pil)
                if alpha_pil:
                    global_alpha = np.array(alpha_pil) # (H, W) uint8
                    
                    # Apply alpha to img_pil for internal use if needed, 
                    # but we keep img_pil as original RGBA or convert later.
                    # Actually, if we want to "remove background", we should apply it.
                    
                    # If original was RGB, add alpha. If RGBA, replace alpha?
                    # Generally we trust MODNet more than original alpha if present.
                    img_np = np.array(img_pil.convert("RGB"))
                    img_rgba = np.dstack((img_np, global_alpha))
                    img_pil = Image.fromarray(img_rgba)
            except Exception as e:
                 console.print(f"[yellow]Matting 오작동: {e}[/yellow]")
        else:
            # Fallback to rembg or keep original
            try:
                from rembg import remove
                console.print("[cyan]배경 제거 (rembg) 처리 중... (Fallback)[/cyan]")
                img_pil = remove(img_pil)
                img_temp = np.array(img_pil)
                if img_temp.shape[2] == 4:
                    global_alpha = img_temp[:, :, 3]
            except:
                pass

        width, height = img_pil.size
        
        # [Refinement] Handle RGBA -> RGB Composite
        # We always process on a solid RGB canvas for robust Detection & Inpainting.
        # If we have transparency, we composite onto a neutral color (Grey) to avoid detection issues.
        # But we keep 'global_alpha' to ensure the final parts have clean backgrounds.
        
        BACKGROUND_COLOR = (128, 128, 128) # Neutral Grey
        
        if img_pil.mode == "RGBA":
            # Composite onto Grey
            background = Image.new("RGB", img_pil.size, BACKGROUND_COLOR)
            background.paste(img_pil, mask=img_pil.split()[3]) # 3 is alpha
            img = background
            img_rgba = img_pil # Keep original
        else:
            img = img_pil.convert("RGB")
            img_rgba = img_pil.convert("RGBA")
            
        # [Refinement] Denoise Image (Reduce JPEG/Upscale Artifacts)
        # 2x upscale can amplify noise. Light denoising helps.
        console.print("[cyan]노이즈 제거(Denoising) 처리 중...[/cyan]")
        processed_img_np = np.array(img)
            
        # h=3 (strength) is subtle but effective for preserving texture
        processed_img_np = cv2.fastNlMeansDenoisingColored(processed_img_np, None, 3, 3, 7, 21)
        
        img = Image.fromarray(processed_img_np)
        
        # Sync current_canvas with the processed (denoised) RGB image
        # This ensuring detection and inpainting work on the same clean RGB data.
        current_canvas = np.array(img)
            
        output_dir.mkdir(parents=True, exist_ok=True)


        # 파츠 정의
        # 간단한 단어 위주로 검색
        parts_def = {
            "head": ["head", "face"],
            "hair": ["hair", "long hair", "bangs", "twintails"],
            "body": ["body", "armor", "torso", "outfit"],
            "chest": ["chest", "breasts", "bust", "cleavage"],
            "hips": ["hips", "buttocks", "pelvis", "thighs"],
            "arm_L": ["left arm", "left hand"],
            "arm_R": ["right arm", "right hand"],
            "leg_L": ["left leg", "foot"],
            "leg_R": ["right leg", "foot"],
            "weapon": ["weapon", "sword", "shield", "gun"]
        }
        
        # YOLO-World 클래스 설정
        # 모든 프롬프트를 평탄화하여 설정
        all_prompts = []
        prompt_map = {} # prompt -> part_name
        for p_name, keywords in parts_def.items():
            for kw in keywords:
                all_prompts.append(kw)
                prompt_map[kw] = p_name
        
        # 0. 전처리: 픽셀 아트 업스케일링 (감지율 향상용)
        # 원본이 작으면 2~4배 확대하여 감지 후, 좌표를 다시 축소
        scale_factor = 1.0
        if min(width, height) < 512:
            scale_factor = 2.0
            console.print(f"[cyan]이미지 확대 (x{scale_factor}) - 감지율 향상[/cyan]")
            img_resized = img.resize((int(width * scale_factor), int(height * scale_factor)), Image.NEAREST)
            # 임시 파일 저장 (YOLO-World는 파일 경로 필요?)
            # YOLO는 PIL 이미지 직접 지원함
            detect_source = img_resized
        else:
            detect_source = img

        # CLIP 모델 로드 (검증용)
        try:
            import clip
            import torch
            device = "cpu" # "cuda" if torch.cuda.is_available() else "cpu"
            console.print(f"[cyan]CLIP 로딩 중... ({device})[/cyan]")
            clip_model, clip_preprocess = clip.load("ViT-B/32", device=device)
            
            # 파츠 텍스트 임베딩 미리 계산
            part_texts = list(parts_def.keys()) + ["noise", "background", "unknown"]
            text_tokens = clip.tokenize([f"a picture of {p}" for p in part_texts]).to(device)
            with torch.no_grad():
                text_features = clip_model.encode_text(text_tokens)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
            use_clip = True
        except ImportError:
            console.print("[yellow]CLIP을 불러올 수 없어 검증 단계를 생략합니다.[/yellow]")
            use_clip = False

        # 1단계: 감지 (Detection)
        console.print("[cyan]파츠 감지 중...[/cyan]")
        # conf를 매우 낮게 잡고 CLIP으로 필터링
        det_results = det_model.predict(detect_source, conf=0.005, iou=0.1, verbose=False)
        
        if not det_results or not det_results[0].boxes:
            console.print("[yellow]파츠 감지 실패[/yellow]")
            return {"success": False, "error": "No objects detected"}
            
        boxes = det_results[0].boxes
        console.print(f"[cyan]감지된 후보 박스 수: {len(boxes)}[/cyan]")
        
        parts_info = []
        found_parts = set()

        # 2단계: CLIP 검증 및 필터링
        # 박스를 잘라내어 CLIP에 넣고, 가장 확률 높은 파츠 이름 찾기
        
        verified_boxes = {} # part_name -> (box, score)
        
        for box in boxes:
            # 좌표 스케일 복원
            if isinstance(box.xyxy[0], torch.Tensor):
                xyxy = box.xyxy[0].cpu().numpy()
            else:
                xyxy = box.xyxy[0]
                
            # Crop Image for CLIP
            l, t, r, b = map(int, xyxy)
            crop = detect_source.crop((l, t, r, b))
            
            if use_clip:
                # CLIP Classification
                input_tensor = clip_preprocess(crop).unsqueeze(0).to(device)
                with torch.no_grad():
                    image_features = clip_model.encode_image(input_tensor)
                    image_features /= image_features.norm(dim=-1, keepdim=True)
                    
                    similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                    values, indices = similarity[0].topk(1)
                    
                    best_idx = int(indices[0])
                    best_part = part_texts[best_idx]
                    score = float(values[0])
                    
                    # 노이즈나 배경이면 스킵
                    if best_part in ["noise", "background", "unknown"]:
                        continue
                        
                    if score < 0.2: # 신뢰도 컷오프
                        continue
                        
                    # 기존 감지된 것보다 좋으면 교체
                    if best_part not in verified_boxes or score > verified_boxes[best_part][1]:
                         # 좌표를 원본 스케일로 변환
                         orig_box = [coord / scale_factor for coord in xyxy]
                         verified_boxes[best_part] = (orig_box, score)
            else:
                 # CLIP 없으면 YOLO Class 신뢰
                 cls_id = int(box.cls[0])
                 # ... 기존 로직 ...
                 # 여기서는 CLIP 위주로 재작성했으므로 CLIP 없을때의 폴백은 생략 또는 단순화
                 pass

        console.print(f"[cyan]CLIP 검증 후 파츠: {list(verified_boxes.keys())}[/cyan]")

        # 1-1. Pose Estimation (YOLO-Pose) - 자세 기반 위치 추정
        console.print("[cyan]자세 추정 중... (Pose Hints)[/cyan]")
        global_pose_kpts = None
        try:
             pose_model = YOLO("yolo11n-pose.pt")
             pose_results = pose_model(detect_source, verbose=False)
             
             if pose_results and pose_results[0].keypoints:
                 # Store full [x, y, conf]
                 # keypoints.data gives (1, 17, 3)
                 if pose_results[0].keypoints.data is not None:
                      global_pose_kpts = pose_results[0].keypoints.data[0].cpu().numpy()
                 else:
                      # fallback if data not available directly
                       xy = pose_results[0].keypoints.xy[0].cpu().numpy()
                       conf = pose_results[0].keypoints.conf[0].cpu().numpy()
                       global_pose_kpts = np.hstack([xy, conf[:, None]])

                 kpts = pose_results[0].keypoints.xy[0].cpu().numpy() # (17, 2)
                 # COCO: 0:Nose, 5:Shdr_L, 6:Shdr_R, 7:Elbow_L, 8:Elbow_R, 9:Wrist_L, 10:Wrist_R
                 # 11:Hip_L, 12:Hip_R, 13:Knee_L, 14:Knee_R, 15:Ankle_L, 16:Ankle_R
                 
                 def make_bbox(indices, padding=20):
                     xs = [kpts[i][0] for i in indices if kpts[i][0] > 0]
                     ys = [kpts[i][1] for i in indices if kpts[i][1] > 0]
                     if not xs: return None
                     return [min(xs)-padding, min(ys)-padding, max(xs)+padding, max(ys)+padding]

                 pose_boxes = {}
                 # Head
                 pose_boxes["head"] = make_bbox([0, 1, 2, 3, 4], 30)
                 # Body (Torso)
                 pose_boxes["body"] = make_bbox([5, 6, 11, 12], 40)
                 # Arm L
                 pose_boxes["arm_L"] = make_bbox([5, 7, 9], 30)
                 # Arm R
                 pose_boxes["arm_R"] = make_bbox([6, 8, 10], 30)
                 # Leg L
                 pose_boxes["leg_L"] = make_bbox([11, 13, 15], 30)
                 # Leg R
                 pose_boxes["leg_R"] = make_bbox([12, 14, 16], 30)
                 
                 for p_name, box in pose_boxes.items():
                     if box:
                         # Merge into verified_boxes if not present or low score
                         # We assign a high heuristic score for Pose findings
                         if p_name not in verified_boxes: # 우선순위: Text > Pose (Text가 더 정교할 수 있음)
                             # 스케일 복원
                             orig_box = [coord / scale_factor for coord in box]
                             verified_boxes[p_name] = (orig_box, 0.85) # High confidence for pose
                             console.print(f"[green]  + {p_name} 발견 (Pose 기반)[/green]")
        except Exception as e:
            console.print(f"[yellow]Pose Estimation 실패 (건너뜀): {e}[/yellow]")

        # 3단계: SAM 분할 + AI 검증 (Gemini)
        verified_final_parts = {}
        
        # Lazy load Gemini key - Removed per user request
        gemini_model = None

        for part_name, (xyxy, score) in verified_boxes.items():
            # SAM에 박스 전달
            sam_results = sam_model(img, bboxes=[[list(xyxy)]], verbose=False)
            
            if not sam_results or not sam_results[0].masks:
                continue

            masks_data = sam_results[0].masks.data.cpu().numpy()
            mask = masks_data[0] # Assuming single mask per box
            
            if mask.shape != (height, width):
                mask = cv2.resize(mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST).astype(bool)
            
            # 필터링 1: 크기가 너무 작으면 무시 (노이즈)
            area = np.sum(mask)
            if area < (width * height * 0.005): # 전체의 0.5% 미만
                console.print(f"[dim]  - {part_name} 무시 (너무 작음)[/dim]")
                continue
                
            # 필터링 2: AI 검증 (Gemini) - 폐기됨 (사용자 요청)
            # 대신 점수 기반 필터링 강화
            if score < 0.25: # 기존 0.2에서 상향 조정
                 console.print(f"[dim]  - {part_name} 무시 (점수 낮음: {score:.2f})[/dim]")
                 continue
                 
            console.print(f"[green]  + {part_name} 확인 ({score:.2f})[/green]")
            
            verified_final_parts[part_name] = mask

        # Z-Order 정렬 (뒤에서 앞으로)
        # 순서: weapon -> body -> head -> arm -> leg (기본)
        # 하지만 Inpainting을 위해서는 '앞에 있는 것'을 먼저 떼어내고 채워야 함 (sequential extraction)
        # 즉, [무기, 팔, 다리, 머리, 몸통] 순서로 떼어내는게 유리 (Inpainting Context)
        
        # 정렬 기준 우선순위 (높을수록 먼저 처리 = 가장 앞쪽 레이어)
        z_priority = {
            "weapon": 100,
            "hair": 95,      # Hair covers face/shoulders
            "head": 90,      # Head covers body
            "chest": 85,     # Chest covers body
            "hips": 85,      # Hips cover body/legs
            "hand_L": 80, "hand_R": 80,
            "arm_L": 75, "arm_R": 75,
            "leg_L": 70, "leg_R": 70,
            "body": 50
        }
        
        sorted_parts_keys = sorted(verified_final_parts.keys(), key=lambda k: z_priority.get(k, 0), reverse=True)

        # LamaClient 초기화 (Local High-Quality Inpainting)
        try:
            from lib.lama_client import LamaClient
            lama_client = LamaClient()
        except ImportError:
            lama_client = None
            console.print("[yellow]LamaClient 로드 실패: CV2를 사용합니다.[/yellow]")
            # 디버깅: 왜 실패했는지 확인
            import traceback
            traceback.print_exc()

        current_canvas = np.array(img) # RGB (Black background)
        
        processed_count = 0
        islands_before_per_part = []
        islands_after_per_part = []
        
        for part_name in sorted_parts_keys:
            xyxy, score = verified_boxes[part_name]
            # 아니면 마스크는 원본에서 따고, 이미지는 현재 캔버스에서 따나?
            # 마스크 위치는 변하지 않음. 이미지 เนื้อหา(content)가 변함(인페인팅됨).
            
            # 1. 마스크 생성 (원본 이미지 기준 - SAM은 형태를 잘 따므로 원본 사용 권장하지만, 
            #    이미 가려진 부분이 채워졌다면 헷갈릴 수 있음. 일단 원본 좌표/Prompt 사용)
            
            # SAM Model needs filepath or array. We pass 'img' (original PIL) to keep detection stable.
            sam_results = sam_model(img, bboxes=[[list(xyxy)]], verbose=False) # Always prompt on original structure
            
            if not sam_results or not sam_results[0].masks:
                continue

            masks = sam_results[0].masks.data.cpu().numpy()
            mask = masks[0]
            if mask.shape != (height, width):
                mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
            
            raw_mask_uint8 = (mask > 0).astype(np.uint8) * 255
            before_islands = count_mask_islands(raw_mask_uint8)

            alpha_channel = refine_alpha_channel(raw_mask_uint8, current_canvas)

            # [Refinement] Intersect with Global Alpha (from rembg)
            # This ensures we don't include background noise/grey pixels that are outside the character.
            if global_alpha is not None:
                # global_alpha is (H, W). We intersect directly.
                alpha_channel = np.minimum(alpha_channel, global_alpha)

            keep_largest_only = part_name in {"body", "chest", "hips"}
            alpha_channel = (
                remove_small_islands(
                    alpha_channel.astype(np.float32) / 255.0,
                    min_size=120,
                    keep_largest_only=keep_largest_only,
                )
                * 255
            ).astype(np.uint8)

            mask_uint8 = (alpha_channel > 8).astype(np.uint8) * 255

            after_islands = count_mask_islands(mask_uint8)
            islands_before_per_part.append(before_islands)
            islands_after_per_part.append(after_islands)
            console.print(f"[dim]    - islands {part_name}: {before_islands} -> {after_islands}[/dim]")

            # Extract RGB from Current Canvas
            # We use the FULL canvas color so that the semi-transparent pixels 
            # pick up the correct border color (not black).
            b_channel, g_channel, r_channel = cv2.split(current_canvas)
            final_part_bgra = cv2.merge([b_channel, g_channel, r_channel, alpha_channel])
            
            # BBox Crop & Save
            part_pil = Image.fromarray(final_part_bgra)
            bbox = part_pil.getbbox()

            
            if bbox:
                 part_pil_cropped = part_pil.crop(bbox)
                 final_path = output_dir / f"{part_name}.png"
                 part_pil_cropped.save(final_path, "PNG")
                 
                 parts_info.append({
                     "name": part_name,
                     "file": final_path.name,
                     "region": list(bbox),
                     "confidence": score
                 })
                 found_parts.add(part_name)
                 processed_count += 1
                 console.print(f"[green]  + {part_name} 분리 및 저장[/green]")
            
            # 3. 인페인팅 (Fill the hole in Current Canvas)
            console.print(f"[dim]    - {part_name} 영역 복원(Inpainting) 중...[/dim]")
            
            # 마스크 팽창 (Dilate) - 경계선 제거용
            # Refinement: 10x10 is too big. Reduced to 5x5.
            kernel = np.ones((5, 5), np.uint8) 
            mask_dilated = cv2.dilate(mask_uint8, kernel, iterations=3) # 5x5 x 3 = 15px radius (approx)
            
            inpainted_success = False
            
            # [Integration] Stable Diffusion Inpainting
            if inpainting_engine:
                try:
                    # Convert to PIL for Diffusers
                    # current_canvas is RGB numpy array
                    canvas_pil = Image.fromarray(current_canvas)
                    mask_pil = Image.fromarray(mask_dilated, mode="L")
                    
                    # Prompt: Generic prompt for anime body filling
                    prompt = "anime character body, skin, clothing texture, high quality, seamless"
                    
                    # Run Inpainting
                    # steps=15 is a balance between speed and quality for CPU/GPU
                    result_pil = inpainting_engine.inpaint(canvas_pil, mask_pil, prompt=prompt, steps=15)
                    
                    current_canvas = np.array(result_pil)
                    inpainted_success = True
                    console.print(f"[cyan]    > SD Inpainting 완료[/cyan]")
                    
                except Exception as e:
                    console.print(f"[yellow]    > SD Inpainting 실패 ({e})[/yellow]")
                    inpainted_success = False
            
            # Fallback: CV2 Telea
            if not inpainted_success:
                if lama_client:
                    try:
                        result_img = lama_client.inpaint(current_canvas, mask_dilated)
                        if result_img is not None:
                            current_canvas = result_img
                            console.print(f"[cyan]    > LaMa Inpainting 완료[/cyan]")
                        else:
                             raise Exception("LaMa returned None")
                    except:
                        current_canvas = cv2.inpaint(current_canvas, mask_dilated, 5, cv2.INPAINT_TELEA)
                        console.print(f"[dim]    > CV2 Inpainting 완료 (Fallback)[/dim]")
                else:
                    current_canvas = cv2.inpaint(current_canvas, mask_dilated, 5, cv2.INPAINT_TELEA)
                    console.print(f"[dim]    > CV2 Inpainting 완료 (Fallback)[/dim]")

            # 4. 관절 정밀 분리 (Granular Split)
            if part_name in ["arm_L", "arm_R", "leg_L", "leg_R"]:
                # xyxy is the box used for extraction.
                # If scale_factor used (upscale for detection), we need to handle that?
                # The 'verified_boxes' contains ORIG_BOX (scaled back).
                # But 'detect_source' (where pose ran) might have been scaled.
                # global_pose_kpts are in 'detect_source' coords.
                # We need to ensure coords match the 'final_part_bgra' cropping.
                
                # final_part_bgra was cropped from 'img' (Original PIL).
                # 'verified_boxes' has coords for 'img'.
                # 'detect_source' logic: 
                # if scale_factor > 1: detect_source = img.resize(...)
                # So Pose Kpts are scaled up.
                # We need to de-scale pose kpts to match 'img'.(and verified_boxes)
                
                current_box = xyxy
                current_kpts = None
                
                if global_pose_kpts is not None:
                     current_kpts = global_pose_kpts.copy()
                     if scale_factor != 1.0:
                         current_kpts[:, :2] /= scale_factor
                
                # [Fix] Pass the CROPPED image, not the full canvas
                # part_pil_cropped is available from above
                part_cropped_np = np.array(part_pil_cropped) # RGBA
                # Convert to BGRA for cv2 compatibility (if needed by logic) or just keep as is?
                # split_limb_using_pose uses PIL internaly mostly, but expects BGRA/RGBA numpy input
                # current logic: Image.fromarray(part_img_bgra). 
                # part_pil_cropped is correct.
                
                sub_parts = split_limb_using_pose(part_cropped_np, part_name, output_dir, current_kpts, current_box)
                
                if sub_parts:
                    parts_info.extend(sub_parts)
                    found_parts.update(p["name"] for p in sub_parts)

            
            # 디버깅용: 중간 과정 저장
            # Image.fromarray(current_canvas).save(output_dir / f"debug_{part_name}_removed.png")

        if islands_before_per_part:
            avg_before = sum(islands_before_per_part) / len(islands_before_per_part)
            avg_after = sum(islands_after_per_part) / len(islands_after_per_part)
            console.print(f"[cyan]Alpha Matting islands/part: {avg_before:.2f} -> {avg_after:.2f}[/cyan]")

        metadata = {
            "source": str(image_path),
            "method": "yoloworld+sam+inpainting",
            "parts": parts_info,
        }
        
        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return {"success": True, "method": "yoloworld+sam+inpainting", "parts": parts_info}

    except ImportError:
        console.print("[red]Utils: ultralytics 패키지가 필요합니다.[/red]")
        return {"success": False, "error": "ImportError"}
    except Exception as e:
        console.print(f"[red]처리 중 오류: {e}[/red]")
        # 상세 오류 출력을 위해 traceback 사용 가능
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def split_manual_template(image_path: Path, output_dir: Path) -> Dict[str, Any]:
    """템플릿 기반 수동 분리 (폴백)"""
    try:
        from PIL import Image

        img = Image.open(image_path)
        width, height = img.size

        # 간단한 그리드 기반 분리 (예시)
        parts_regions = {
            "head": (width * 0.3, 0, width * 0.7, height * 0.25),
            "body": (width * 0.2, height * 0.2, width * 0.8, height * 0.5),
            "arm_L": (0, height * 0.2, width * 0.3, height * 0.5),
            "arm_R": (width * 0.7, height * 0.2, width, height * 0.5),
            "leg_L": (width * 0.2, height * 0.5, width * 0.5, height),
            "leg_R": (width * 0.5, height * 0.5, width * 0.8, height),
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        parts_info = []

        for part_name, region in parts_regions.items():
            part_img = img.crop(tuple(int(x) for x in region))
            part_path = output_dir / f"{part_name}.png"
            part_img.save(part_path, "PNG")

            parts_info.append({
                "name": part_name,
                "file": f"{part_name}.png",
                "region": list(region),
            })

        # 메타데이터 저장
        metadata = {
            "source": str(image_path),
            "method": "template",
            "parts": parts_info,
        }

        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return {"success": True, "method": "template", "parts": parts_info}

    except Exception as e:
        console.print(f"[red]분리 실패: {e}[/red]")
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="캐릭터 파츠 분리")
    parser.add_argument("--input", type=str, required=True, help="입력 이미지 경로")
    parser.add_argument("--output", type=str, default="parts", help="출력 경로")
    parser.add_argument("--method", type=str, choices=["komiko", "sam", "template"],
                        default="sam", help="분리 방법")
    parser.add_argument("--matting", default="modnet", choices=["modnet", "birefnet"], help="매팅 엔진 선택")
    parser.add_argument("--post_process", action="store_true", help="매팅 후처리(노이즈 제거) 활성화", default=True)

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    
    # Initialize Engines
    # Matting
    if args.matting == "birefnet":
        try:
            from utils.birefnet_matting import BiRefNetEngine
            matting_engine = BiRefNetEngine()
            print("[System] Using BiRefNet (Ultra-Fidelity)")
        except Exception as e:
            print(f"[Warning] Failed to load BiRefNet: {e}. Fallback to MODNet.")
            from utils.matting import MattingEngine
            matting_engine = MattingEngine()
    else:
        from utils.matting import MattingEngine
        matting_engine = MattingEngine()

    from utils.inpainting import InpaintingEngine
    inpainting_engine = InpaintingEngine() # Initialize once

    if not input_path.exists():
        console.print(f"[red]파일을 찾을 수 없습니다: {input_path}[/red]")
        return

    console.print(f"[blue]입력: {input_path}[/blue]")
    console.print(f"[blue]방법: {args.method}[/blue]")

    if input_path.is_file():
        if args.method == "komiko":
            result = split_with_komiko(input_path, output_dir, matting_engine, inpainting_engine, post_process=args.post_process)
        elif args.method == "sam":
            result = split_with_sam(input_path, output_dir, matting_engine, inpainting_engine, post_process=args.post_process)
        else:
            result = split_manual_template(input_path, output_dir)
    elif input_path.is_dir():
        # Batch Mode
        images = list(input_path.glob("*.png")) + list(input_path.glob("*.jpg")) + list(input_path.glob("*.jpeg"))
        print(f"Found {len(images)} images in {input_path}")
        
        for img_path in images:
            # Create subfolder for each image
            img_output_dir = output_dir / img_path.stem
            if args.method == "komiko":
                result = split_with_komiko(img_path, img_output_dir, matting_engine, inpainting_engine, post_process=args.post_process)
            elif args.method == "sam":
                result = split_with_sam(img_path, img_output_dir, matting_engine, inpainting_engine, post_process=args.post_process)
            else:
                result = split_manual_template(img_path, img_output_dir)
    else:
        print(f"Error: {input_path} is not a valid file or directory")

    if result.get("success"):
        console.print(f"[green]✓ 분리 완료: {output_dir}[/green]")
        console.print(f"[green]  파츠 수: {len(result.get('parts', []))}[/green]")
    else:
        console.print("[red]✗ 분리 실패[/red]")


if __name__ == "__main__":
    main()
