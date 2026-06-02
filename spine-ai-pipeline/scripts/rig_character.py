#!/usr/bin/env python3
"""
Spine2D AI를 활용한 리깅 자동 생성 스크립트

사용법:
    python rig_character.py --input char_001/parts --output char_001/spine
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

from rich.console import Console

console = Console()

try:
    from lib.spine_templates import get_template
except ImportError:
    # Fallback if running from root without package structure
    import sys
    sys.path.append(str(Path(__file__).parent))
    from lib.spine_templates import get_template


def load_parts_metadata(parts_dir: Path) -> Dict[str, Any]:
    """파츠 메타데이터 로드"""
    metadata_path = parts_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_rig_preset(preset_name: str, config_dir: Path) -> Dict[str, Any]:
    """리깅 프리셋 로드"""
    presets_path = config_dir / "presets.json"
    if presets_path.exists():
        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)
            return presets.get("rig_types", {}).get(preset_name, {})
    return {}


def generate_spine_skeleton(parts_metadata: Dict, rig_preset: Dict) -> Dict[str, Any]:
    """Spine 스켈레톤 JSON 생성"""
    bones = rig_preset.get("bones", ["root", "body", "head"])

    skeleton = {
        "skeleton": {
            "hash": "",
            "spine": "4.2.0",
            "x": 0,
            "y": 0,
            "width": 512,
            "height": 512,
        },
        "bones": [{"name": bone, "parent": "head" if bone == "eye_ctrl" else ("root" if bone != "root" else None)} for bone in bones + (["eye_ctrl"] if "head" in bones and "eye_ctrl" not in bones else [])],
        "physics": [], # TODO: add dynamic physics loop
        "slots": [],
        "skins": {"default": {}},
        "animations": {},
    }

    # 파츠를 슬롯으로 변환
    for part in parts_metadata.get("parts", []):
        slot = {
            "name": part["name"],
            "bone": _map_part_to_bone(part["name"], bones),
            "attachment": part["name"],
        }
        skeleton["slots"].append(slot)

    return skeleton


def _map_part_to_bone(part_name: str, bones: List[Dict[str, Any]]) -> str:
    """파츠 이름을 본에 매핑 (존재하는 본 우선)"""
    # 선호 매핑
    mapping = {
        "head": ["head", "neck", "body"],
        "body": ["body", "root"],
        "arm_L": ["arm_L", "shdr_L", "body"],
        "arm_R": ["arm_R", "shdr_R", "body"],
        "leg_L": ["thigh_L", "leg_L", "body"],
        "leg_R": ["thigh_R", "leg_R", "body"],
        "weapon": ["hand_R", "arm_R", "body"],
        "shield": ["hand_L", "arm_L", "body"],
        "cape": ["body", "root"],
    }
    
    candidates = mapping.get(part_name, ["root"])
    
    # 생성된 본 목록에 있는지 확인
    existing_bone_names = {b["name"] for b in bones}
    
    for candidate in candidates:
        if candidate in existing_bone_names:
            return candidate
            
    # 매핑 실패시 가장 가까운 부위 찾기 (단순화)
    if "leg" in part_name: return "body"
    if "arm" in part_name: return "body"
    
    return "root"


def generate_with_pose_estimation(parts_dir: Path, output_dir: Path, preset: str) -> Dict[str, Any]:
    """YOLO-Pose를 활용한 지능형 리깅 생성"""
    try:
        from ultralytics import YOLO
        import numpy as np
        
        # 메타데이터 로드
        parts_metadata = load_parts_metadata(parts_dir)
        source_image_path = parts_metadata.get("source")
        
        if not source_image_path or not Path(source_image_path).exists():
            console.print("[yellow]원본 이미지를 찾을 수 없어 기본 모드로 전환합니다.[/yellow]")
            return generate_local(parts_dir, output_dir, preset)

        # YOLO Pose 모델 로드
        model = YOLO("yolo11n-pose.pt") # 최신 11n-pose 또는 8n-pose 사용
        console.print(f"[cyan]Pose 모델 로딩 완료: {model.task}[/cyan]")
        
        # 추론 실행
        results = model(source_image_path, verbose=False)
        
        if not results or not results[0].keypoints:
             console.print("[yellow]포즈 감지 실패, 기본 모드로 전환합니다.[/yellow]")
             return generate_local(parts_dir, output_dir, preset)
             
        # Keypoints 추출 (x, y, conf)
        # COCO Format: 0:Nose, 5:Shoulder_L, 6:Shoulder_R, 11:Hip_L, 12:Hip_R ...
        kpts = results[0].keypoints.data[0].cpu().numpy() # (17, 3)
        
        # 좌표 변환 (Spine은 Y축이 위로 갈수록 +일 수 있으나, JSON 포맷은 화면 좌표계 따름)
        # Spine Editor: (0,0) is usually at the feet.
        # But for JSON import, it often matches the image coordinates if root is 0,0 top-left?
        # Standard Spine JSON export usually sets root at the center of feet, and Y is up.
        # However, to keep it simple for auto-generated, we can set root at image center or valid pivot.
        
        image_height = results[0].orig_shape[0] # H
        
        # 헬퍼 함수: Y축 반전 (Spine은 좌하단이 0,0, 이미지는 좌상단이 0,0)
        def to_spine_coord(x, y):
             return x, image_height - y

        # 본 구조 정의 및 좌표 계산
        bones = []
        
        # 1. Root (두 발의 중앙)
        # 15: Ankle_L, 16: Ankle_R
        ankle_l = kpts[15]
        ankle_r = kpts[16]
        root_x = (ankle_l[0] + ankle_r[0]) / 2
        root_y = (ankle_l[1] + ankle_r[1]) / 2
        # 1. 모든 본의 절대 좌표(Absolute Position) 계산 및 저장
        abs_bones = {} # name -> (x, y)
        
        # Root (Anchor)
        root_x = (kpts[15][0] + kpts[16][0]) / 2
        root_y = (kpts[15][1] + kpts[16][1]) / 2
        spine_root_x, spine_root_y = to_spine_coord(root_x, root_y)
        abs_bones["root"] = (spine_root_x, spine_root_y)
        
        # Body (Hips center)
        # 11: Hip_L, 12: Hip_R
        hip_x = (kpts[11][0] + kpts[12][0]) / 2
        hip_y = (kpts[11][1] + kpts[12][1]) / 2
        s_hip_x, s_hip_y = to_spine_coord(hip_x, hip_y)
        abs_bones["body"] = (s_hip_x, s_hip_y)
        
        # Head (Nose)
        kp0 = kpts[0]
        hx, hy = to_spine_coord(kp0[0], kp0[1])
        abs_bones["head"] = (hx, hy)
        
        # Detailed Limbs
        # Mapping: bone_name -> kp_idx
        # Note: If confidence is low, we might need inference or fallback.
        # But for now, we assume simple mapping.
        
        key_map = {
            "thigh_L": 11, "shin_L": 13, "foot_L": 15,
            "thigh_R": 12, "shin_R": 14, "foot_R": 16,
            "arm_L": 5, "forearm_L": 7, "hand_L": 9,
            "arm_R": 6, "forearm_R": 8, "hand_R": 10,
        }
        
        for b_name, kp_idx in key_map.items():
            kp = kpts[kp_idx]
            # if kp[2] < 0.2: ... # Low conf handling?
            bx, by = to_spine_coord(kp[0], kp[1])
            abs_bones[b_name] = (bx, by)
            
        # 2. 계층 구조 정의 및 Local 좌표 계산
        # (Bone Name, Parent Name)
        hierarchy = [
            ("root", None),
            ("body", "root"),
            ("head", "body"),
            # Left Leg
            ("thigh_L", "body"),
            ("shin_L", "thigh_L"),
            ("foot_L", "shin_L"),
            # Right Leg
            ("thigh_R", "body"),
            ("shin_R", "thigh_R"),
            ("foot_R", "shin_R"),
            # Left Arm
            ("arm_L", "body"),
            ("forearm_L", "arm_L"),
            ("hand_L", "forearm_L"),
            # Right Arm
            ("arm_R", "body"),
            ("forearm_R", "arm_R"),
            ("hand_R", "forearm_R"),
        ]
        
        for b_name, p_name in hierarchy:
            if b_name not in abs_bones:
                continue

            current_abs = abs_bones[b_name]
            
            if p_name is None:
                # Root bone itself (relative to world origin 0,0 usually inside Spine? 
                # No, Spine Root is usually at 0,0 locally. 
                # Our "root" bone will serve as the main anchor.
                # Let's verify: Spine `x,y` for root is relative to setup origin.
                # We want the character to be centered? 
                # Let's assume Spine Origin (0,0) is at the feet (root).
                # So we calculate offset from `spine_root_x/y` (which implies root is at 0,0).
                
                # Wait, `abs_bones["root"]` IS `spine_root_x`.
                # So `root` bone local pos should be 0,0 relative to "Character Origin".
                local_x = 0.0
                local_y = 0.0
            else:
                # Normal bone relative to parent
                if p_name not in abs_bones:
                    # Parent missing? Link to root?
                     p_name = "root"
                
                parent_abs = abs_bones[p_name]
                local_x = current_abs[0] - parent_abs[0]
                local_y = current_abs[1] - parent_abs[1]
            
            bone_def = {
                "name": b_name,
                "x": float(local_x),
                "y": float(local_y),
                "length": 50.0 # Cosmetic length
            }
            if p_name:
                bone_def["parent"] = p_name
            
            # 각도 계산 (Optional but good for visuals)
            # 만약 자식 본이 있다면, 그 쪽을 향하게 회전하면 좋음.
            # 하지만 setup pose에서 회전을 넣으면 animation 작성시 헷갈릴 수 있음.
            # 일단 회전 0으로 유지 (Straight hierarchy).
            
            bones.append(bone_def)

        # IK Constraints 추가
        # IK Constraints 정의
        ik_constraints = []
        
        # Left Leg IK
        ik_constraints.append({
            "name": "leg_L_ik",
            "target": "foot_L",
            "bones": ["thigh_L", "shin_L"],
            "mix": 1.0,
            "bendPositive": True
        })
        
        # Right Leg IK
        ik_constraints.append({
            "name": "leg_R_ik",
            "target": "foot_R",
            "bones": ["thigh_R", "shin_R"],
            "mix": 1.0,
            "bendPositive": True
        })

        # Spine Skeleton JSON 구성
        skeleton = {
            "skeleton": {
                "hash": "", 
                "spine": "4.2.0", 
                "x": 0, 
                "y": 0, 
                "width": image_height, 
                "height": image_height,
                "images": "./"
            },
            "bones": bones,
            "ik": ik_constraints,
            "slots": [],
            "skins": {"default": {}}
        }
        
        # 슬롯 및 스킨(Attachment) 구성
        parts_list = parts_metadata.get("parts", [])
        if not parts_list and parts_dir.exists():
            pass

        for part in parts_list:
            p_name = part["name"]
            part_bbox = part.get("region", [0, 0, 0, 0]) # l, u, r, d
            
            # 뼈 매핑 logic
            target_bone = _map_part_to_bone(p_name, bones)
            
            # Slot 생성
            skeleton["slots"].append({
                "name": p_name,
                "bone": target_bone,
                "attachment": p_name
            })
            
            # Skin (Image) 좌표 계산
            part_cx = (part_bbox[0] + part_bbox[2]) / 2
            part_cy = (part_bbox[1] + part_bbox[3]) / 2
            p_cx_spine, p_cy_spine = to_spine_coord(part_cx, part_cy)
            
            # Bone Absolute Position
            if target_bone in abs_bones:
                bx, by = abs_bones[target_bone]
            else:
                bx, by = 0, 0
                
            # Attachment Offset
            att_x = p_cx_spine - bx
            att_y = p_cy_spine - by
            
            if "default" not in skeleton["skins"]:
                skeleton["skins"]["default"] = {}
            if p_name not in skeleton["skins"]["default"]:
                skeleton["skins"]["default"][p_name] = {}
                
            skeleton["skins"]["default"][p_name][p_name] = {
                "x": float(att_x),
                "y": float(att_y),
                "width": float(part_bbox[2] - part_bbox[0]),
                "height": float(part_bbox[3] - part_bbox[1]),
                "path": p_name # Explicit path
            }

        # 저장
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "skeleton.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(skeleton, f, indent=2)
            
        return {
            "success": True,
            "method": "pose_estimation",
            "output": str(json_path),
            "bones": len(bones),
            "slots": len(skeleton["slots"])
        }

    except ImportError:
        console.print("[red]Ultralytics 패키지가 필요합니다.[/red]")
        return {"success": False, "error": "ImportError"}
    except Exception as e:
        console.print(f"[red]Pose Estimation 실패: {e}[/red]")
        return generate_local(parts_dir, output_dir, preset)


def generate_local(parts_dir: Path, output_dir: Path, preset: str) -> Dict[str, Any]:
    """로컬에서 기본 Spine 프로젝트 생성"""
    try:
        config_dir = Path(__file__).parent.parent / "config"
        parts_metadata = load_parts_metadata(parts_dir)
        rig_preset = load_rig_preset(preset, config_dir)

        if not rig_preset:
            rig_preset = {"bones": ["root", "body", "head"]}

        skeleton = generate_spine_skeleton(parts_metadata, rig_preset)

        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON 저장
        json_path = output_dir / "skeleton.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(skeleton, f, indent=2)

        return {
            "success": True,
            "method": "local",
            "output": str(json_path),
            "bones": len(skeleton["bones"]),
            "slots": len(skeleton["slots"]),
        }

    except Exception as e:
        console.print(f"[red]리깅 생성 실패: {e}[/red]")
        return {"success": False, "error": str(e)}



def _generate_mesh_data(image_path: Path, epsilon_factor=0.005, edge_len=30) -> Dict[str, Any]:
    """Generate Spine Mesh Attachment data from image alpha channel"""
    try:
        import cv2
        import numpy as np
        from scipy.spatial import Delaunay
    except ImportError:
        console.print("[red]Mesh generation requires: opencv-python, numpy, scipy[/red]")
        return None

    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None: return None
    
    h, w = img.shape[:2]
    
    # Alpha Check
    if img.shape[2] == 4: alpha = img[:, :, 3]
    else: 
        # If no alpha, treat as full rect? No, auto-mesh needs shape.
        return None
    
    # Threshold
    _, binary = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    
    cnt = max(contours, key=cv2.contourArea)
    epsilon = epsilon_factor * cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon, True)
    hull = approx.reshape(-1, 2)
    
    if len(hull) < 3: return None
    
    # Internal Points (Grid)
    min_x, min_y = np.min(hull, axis=0)
    max_x, max_y = np.max(hull, axis=0)
    
    x_range = np.arange(min_x, max_x, edge_len)
    y_range = np.arange(min_y, max_y, edge_len)
    grid_x, grid_y = np.meshgrid(x_range, y_range)
    grid_pts = np.vstack([grid_x.ravel(), grid_y.ravel()]).T
    
    inside = []
    for pt in grid_pts:
        if cv2.pointPolygonTest(approx, (int(pt[0]), int(pt[1])), False) >= 5: # Buffer from edge
            inside.append(pt)
            
    if inside:
        internal = np.array(inside)
        all_pts = np.vstack([hull, internal])
    else:
        all_pts = hull
        
    tri = Delaunay(all_pts)
    
    # Check Spine JSON format requirements
    # Vertices relative to attachment center?
    cx, cy = w / 2, h / 2
    spine_vertices = []
    uvs = []
    
    for px, py in all_pts:
        uvs.extend([px / w, py / h]) # UVs are Y-down in 0-1? Spine usually expects 1-v if Y-up texture coordinates
        # However, typical engines flip it. Let's stick to standard 0-1 matches image.
        
        # Spine vertices: +Y is Up in editor. +X Right.
        # Image: +Y is Down.
        # Center is (0,0).
        vx = px - cx
        vy = -(py - cy) # Flip Y
        spine_vertices.extend([vx, vy])
        
    return {
        "type": "mesh",
        "uvs": uvs,
        "triangles": tri.simplices.flatten().tolist(),
        "vertices": spine_vertices,
        "hull": len(hull),
        "width": float(w),
        "height": float(h)
    }


def generate_with_template(parts_dir: Path, output_dir: Path, template_name: str, use_mesh: bool = False) -> Dict[str, Any]:
    """템플릿 기반 리깅 생성 (자동 스케일링 적용)"""
    try:
        # 1. 템플릿 로드
        skeleton_template = get_template(template_name)
        if not skeleton_template:
            console.print(f"[red]템플릿을 찾을 수 없습니다: {template_name}[/red]")
            return {"success": False, "error": "TemplateNotFound"}
            
        # Deep copy to avoid mutating source
        import copy
        skeleton = copy.deepcopy(skeleton_template)
        
        # 기본 Spine 구조 추가
        if "skeleton" not in skeleton:
            skeleton["skeleton"] = {
                "hash": "", "spine": "4.2.0", 
                "x": 0, "y": 0, "width": 1000, "height": 1000
            }
        if "slots" not in skeleton: skeleton["slots"] = []
        if "skins" not in skeleton: skeleton["skins"] = {"default": {}}

        # 2. 메타데이터 로드 & 파츠 분석
        parts_metadata = load_parts_metadata(parts_dir)
        parts_list = parts_metadata.get("parts", [])
        part_map = {p["name"]: p for p in parts_list}

        # 3. 글로벌 스케일 계산 (Global Scale Adaptation)
        # 이미지의 Head~Body 거리를 템플릿의 Head~Body 거리와 비교하여 스케일 조정
        
        scale_factor = 1.0
        
        if "head" in part_map and "body" in part_map:
            p_head = part_map["head"]["region"] # [l, t, r, b]
            p_body = part_map["body"]["region"]
            
            # Y Centroids (Image coordinate system: Y down)
            cy_head = (p_head[1] + p_head[3]) / 2
            cy_body = (p_body[1] + p_body[3]) / 2
            
            h_head = p_head[3] - p_head[1]
            h_body = p_body[3] - p_body[1]
            
            # [Improvement] Adaptive Template Switching
            # Check Head-to-Body Ratio
            # Humanoid: Head is small (< 0.5 of body length usually)
            # Chibi: Head is large (> 0.8 of body length)
            ratio = h_head / h_body if h_body > 0 else 0
            
            if ratio > 0.8 and template_name == "humanoid":
                 console.print(f"[yellow]  Detected Chibi Proportions (Head/Body={ratio:.2f}). Switching to 'chibi' template.[/yellow]")
                 template_name = "chibi"
                 skeleton_template = get_template("chibi")
                 # Re-initialize skeleton from new template
                 skeleton = copy.deepcopy(skeleton_template)
                 if "skeleton" not in skeleton:
                    skeleton["skeleton"] = {
                        "hash": "", "spine": "4.2.0", 
                        "x": 0, "y": 0, "width": 1000, "height": 1000
                    }
                 if "slots" not in skeleton: skeleton["slots"] = []
                 if "skins" not in skeleton: skeleton["skins"] = {"default": {}}
            
            # Calculate Scale Factor
            # Ref Head Size: Humanoid=90, Chibi=150 (from spine_templates.py)
            ref_head_size = 150.0 if template_name == "chibi" else 90.0
            
            if h_head > 0:
                scale_factor = h_head / ref_head_size
                
            console.print(f"[cyan]  Scale Factor (based on Head): {scale_factor:.2f} (Template: {template_name})[/cyan]")

        # 4. 뼈대 스케일링 적용
        for bone in skeleton.get("bones", []):
            if "x" in bone: bone["x"] *= scale_factor
            if "y" in bone: bone["y"] *= scale_factor
            if "length" in bone: bone["length"] *= scale_factor

        # 5. 슬롯 및 Attachments 매핑
        skin_default = skeleton["skins"]["default"]
        
        # 템플릿의 뼈 이름들에 대해 매핑되는 파츠 찾기
        # Bone Name -> Part Name Mapping Strategy
        # Explicit mapping or Name matching
        
        # We iterate through the BONES to ensure we create SLOTS for them if parts exist.
        # Check template conventions. Usually Slot Name = Bone Name for simple setups.
        
        bone_names = [b["name"] for b in skeleton["bones"]]
        
        # Defined Slots in Template?
        # If template returned logic is just Bones+IK, we generate Slots dynamically.
        if not skeleton["slots"]:
            # Auto-generate slots for bones that have matching parts
            
            # Common Mappings
            mappings = {
                "head": ["head"],
                "body": ["body", "torso", "armor"],
                "arm_L": ["arm_L", "arm_l_upper", "blue_arm_l"],
                "arm_R": ["arm_R", "right_arm"],
                "leg_L": ["leg_L", "left_leg"],
                "leg_R": ["leg_R"],
                "hand_L": ["hand_L", "weapon"], # Weapon often attached to hand
                "hand_R": ["hand_R", "weapon"],
                "root": ["cape", "wings", "eff"] # Back effects
            }
            
            # Create slots for found parts
            created_slots = set()
            
            # Priority Z-Order List (Back to Front)
            z_order = ["root", "leg_R", "leg_L", "body", "head", "arm_R", "arm_L", "hand_R", "hand_L"]
            
            for bone_ref in z_order:
                # Find matching bones in skeleton (could be exact or fuzzy)
                target_bones = [b for b in bone_names if bone_ref in b] # e.g. 'thigh_L' matches 'leg_L' logic? No.
                
                # Better: Iterate our defined Z-list and pick logical bones
                # If template has 'thigh_L', 'shin_L', 'foot_L'...
                # And we have part 'leg_L' (entire leg).
                # We map 'leg_L' part to 'thigh_L' bone? Or create a specific slot?
                pass
                
            # Simplified Logic: Iterate Parts and find best Bone
            for part in parts_list:
                p_name = part["name"]
                
                # Find best bone
                target_bone = "root"
                best_score = 0
                
                for b_name in bone_names:
                    score = 0
                    if b_name == p_name: score = 100
                    elif b_name in p_name or p_name in b_name: score = 50
                    
                    # Manual Override
                    if p_name == "weapon" and "hand" in b_name: score = 80
                    
                    if score > best_score:
                        best_score = score
                        target_bone = b_name
                
                # Special cases for 'leg_L' to 'thigh_L' etc if template uses semantic naming
                if target_bone == "root" and "leg" in p_name:
                    # Try to find thigh or shin
                    for sub in ["thigh", "shin", "foot"]:
                        cand = p_name.replace("leg", sub) # leg_L -> thigh_L
                        if cand in bone_names:
                            target_bone = cand
                            break

                # Create Slot
                slot_name = p_name
                skeleton["slots"].append({
                    "name": slot_name,
                    "bone": target_bone,
                    "attachment": p_name
                })
                
                # Update Skin
                if slot_name not in skin_default:
                    skin_default[slot_name] = {}
                    
                # Calculate Attachment Transform
                # We simply place the image centered on the bone.
                
                w, h = 100.0, 100.0
                img_path = parts_dir / part["file"]
                
                if "region" in part:
                    part_region = part["region"]
                    w = float(part_region[2] - part_region[0])
                    h = float(part_region[3] - part_region[1])
                else:
                    # Fallback: Read image size
                    try:
                        from PIL import Image
                        if img_path.exists():
                            with Image.open(img_path) as img:
                                w, h = float(img.width), float(img.height)
                    except Exception:
                        console.print(f"[yellow]Warning: Could not determine size for {p_name}[/yellow]")
                
                # Default Region Attachment
                attachment_data = {
                    "x": 0, "y": 0, "rotation": 0,
                    "width": w, "height": h,
                    "path": p_name
                }
                
                # [Auto-Mesh Logic]
                if use_mesh and img_path.exists():
                    mesh_data = _generate_mesh_data(img_path, edge_len=30) # consistent edge_len
                    if mesh_data:
                        # Override attachment data
                        # Mesh attachment does not have rotation/x/y in the same simple sense?
                        # It has vertices which incorporate the position.
                        # But wait, vertices generated were relative to center.
                        # So we can keep attachment at 0,0 (bone center).
                        attachment_data = mesh_data
                        attachment_data["path"] = p_name
                        console.print(f"  [Mesh] Generated for {p_name}: {len(mesh_data['triangles'])//3} tris")

                skin_default[slot_name][p_name] = attachment_data
                
                # If we detected a weapon, maybe offset it?
                if "weapon" in p_name and "region" not in attachment_data: 
                     # Only offset if region? Or mesh too? 
                     # Mesh vertices are centered. Weapon might need offset.
                     # For now, skip specific weapon offset logic for mesh to avoid complexity.
                     pass
                elif "weapon" in p_name:
                     skin_default[slot_name][p_name]["y"] = -h/2
                     
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "skeleton.json"
        
        # Write Result
        with open(json_path, "w", encoding="utf-8") as f:
             json.dump(skeleton, f, indent=2)

        return {
            "success": True,
            "method": "template_smart",
            "output": str(json_path),
            "scale_factor": scale_factor,
            "template": template_name
        }

    except Exception as e:
        console.print(f"[red]템플릿 생성 실패: {e}[/red]")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="캐릭터 리깅 생성")
    parser.add_argument("--input", type=str, required=True, help="파츠 폴더 경로")
    parser.add_argument("--output", type=str, required=True, help="출력 경로")
    parser.add_argument("--preset", type=str, default="humanoid",
                        choices=["humanoid", "monster", "simple"],
                        help="리깅 프리셋 (로컬/Pose 모드용)")
    parser.add_argument("--template", type=str, help="사용할 템플릿 이름 (예: humanoid)")
    parser.add_argument("--mesh", action="store_true", help="자동 메쉬 생성 (Auto-Mesh)")
    parser.add_argument("--use-api", action="store_true", help="Spine AI API 사용 (Pose Estimation)")
    args = parser.parse_args()

    parts_dir = Path(args.input)
    output_dir = Path(args.output)

    if not parts_dir.exists():
        console.print(f"[red]폴더를 찾을 수 없습니다: {parts_dir}[/red]")
        return

    console.print(f"[blue]입력: {parts_dir}[/blue]")

    if args.template:
        console.print(f"[blue]모드: 템플릿 매핑 ({args.template})[/blue]")
        if args.mesh: console.print(f"[magenta]기능: Auto-Mesh 활성화[/magenta]")
        result = generate_with_template(parts_dir, output_dir, args.template, use_mesh=args.mesh)
    elif args.use_api:
        console.print(f"[blue]모드: Pose Estimation[/blue]")
        result = generate_with_pose_estimation(parts_dir, output_dir, args.preset)
    else:
        console.print(f"[blue]모드: Pose Estimation (Auto)[/blue]")
        result = generate_with_pose_estimation(parts_dir, output_dir, args.preset)

    if result.get("success"):
        console.print(f"[green][OK] Rigging complete: {result.get('output')}[/green]")
    else:
        console.print("[red][FAIL] Rigging failed[/red]")


if __name__ == "__main__":
    main()
