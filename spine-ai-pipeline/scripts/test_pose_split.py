import argparse
import sys
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from ultralytics import YOLO
from rich.console import Console

console = Console()

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

def get_cut_line(p_start, p_joint, p_end, width_scale=1.5):
    """
    Calculate a cut line passing through p_joint, roughly perpendicular to the limb vector.
    Returns ((x1, y1), (x2, y2)) for the line segment to draw/mask.
    """
    # Vector from Start to End (General Limb Direction)
    vx = p_end[0] - p_start[0]
    vy = p_end[1] - p_start[1]
    
    # Perpendicular Vector
    px = -vy
    py = vx
    
    # Normalize
    norm = np.sqrt(px*px + py*py)
    if norm < 0.001: return None
    
    px /= norm
    py /= norm
    
    # Joint Radius / Width estimation
    # We don't know the exact width, so we pick a reasonable size (e.g. 100px or relative to Limb Length)
    limb_len = np.sqrt(vx*vx + vy*vy)
    cut_len = limb_len * 0.5 # Heuristic
    
    x1 = int(p_joint[0] - px * cut_len)
    y1 = int(p_joint[1] - py * cut_len)
    x2 = int(p_joint[0] + px * cut_len)
    y2 = int(p_joint[1] + py * cut_len)
    
    return ((x1, y1), (x2, y2))

def split_limb(img_rgba, joint_name, p_start, p_joint, p_end, output_prefix, output_dir):
    """
    Splits the image into Upper and Lower parts at the joint.
    """
    w, h = img_rgba.size
    
    # Create Mask
    # Method: Draw a wide line at the cut? 
    # Or better: Define a half-plane?
    # Simple approach: Rotate image so limb is vertical, cut horizontally, rotate back? No, too lossy.
    
    # Gradient Mask approach? 
    # Or Polygon Mask: 4 corners.
    # We want to separate the "Distal" part (Lower arm) from "Proximal" part (Upper arm).
    
    # Let's use the Cut Line to divide the space.
    # Line eq: ax + by + c = 0
    # The normal (px, py) points towards one side.
    
    # Vector S->E
    vx = p_end[0] - p_start[0]
    vy = p_end[1] - p_start[1]
    
    # Construct a polygon for the "Lower" part (End side).
    # Since we can't easily guess the full shape, let's try to assume the limb is relatively localized.
    # But wait, we are operating on `part_00_person.png` which is a FULL BODY image.
    # We ONLY want to cut the specific arm, not the whole body.
    
    # Correct Approach:
    # 1. We need a mask for the *limb itself* first (e.g. from SAM or previous coarse split).
    #    Since we don't have that here (we are testing on full body), this test might be messy.
    #    BUT, `split_parts.py` already extracted `arm_L` as a separate file in previous steps!
    #    We should run this logic on the *extracted arm file*, e.g., `final_parts_00/arm_L.png`!
    
    #    Checking verified files... `output/sheet_70f_processed/final_parts_00/arm_L.png` exists.
    
    #    Wait, YOLO-Pose needs the context of the body to detect Left/Right correctly?
    #    Or can it detect on a detached arm? Probably not reliably.
    
    #    Strategy:
    #    1. Detect Pose on the FULL BODY (`part_00_person.png`).
    #    2. Get Keypoints.
    #    3. Map Keypoints to the `arm_L.png` coordinate space?
    #       - `split_parts.py` crops, so coordinates shift.
    #       - We don't easily have the crop offset unless we saved metadata.
    
    #    Alternative Strategy (Self-Contained):
    #    Run YOLO-Pose on `part_00_person.png`.
    #    Use the keypoints to generate a mask for "Lower Left Arm" and "Upper Left Arm" within the full image context.
    #    Then crop those regions using the alpha of the original image?
    
    #    Let's try to split `part_00_person.png` directly into sub-parts for testing.
    pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_image", help="Full body image")
    parser.add_argument("--output_dir", default="output/pose_test")
    args = parser.parse_args()
    
    img_path = Path(args.input_image)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Load Model
    console.print("[cyan]Loading YOLO-Pose...[/cyan]")
    model = YOLO("yolo11n-pose.pt")
    
    # Load and Preprocess for Detection
    img_rgba = Image.open(img_path).convert("RGBA")
    
    # Composite on White Background
    bg_color = (255, 255, 255)
    img_rgb = Image.new("RGB", img_rgba.size, bg_color)
    img_rgb.paste(img_rgba, mask=img_rgba.split()[3])
    
    # Save temp for debugging/inference
    # Add padding to ensure not too close to edge
    pad = 50
    img_padded = Image.new("RGB", (img_rgb.width + pad*2, img_rgb.height + pad*2), bg_color)
    img_padded.paste(img_rgb, (pad, pad))
    
    temp_path = out_dir / "temp_pose_input.jpg"
    img_padded.save(temp_path)
    
    # Predict on padded image
    results = model.predict(str(temp_path), conf=0.3) # lowered conf
    
    if not results or not results[0].keypoints:
        console.print("[red]No pose detected.[/red]")
        return
        
    kpts = results[0].keypoints.xy[0].cpu().numpy()
    confs = results[0].keypoints.conf[0].cpu().numpy()
    
    # Adjust keypoints back to original space
    kpts[:, 0] -= pad
    kpts[:, 1] -= pad
    
    img_np = np.array(img_rgba)
    w, h = img_rgba.size
    
    # Helper
    def valid(idx): return confs[idx] > 0.5
    
    # Draw Viz on Copy
    viz = img_np.copy()
    
    # Process Limbs
    limbs = [
        ("arm_L", KP["shdr_l"], KP["elb_l"], KP["wr_l"]),
        ("arm_R", KP["shdr_r"], KP["elb_r"], KP["wr_r"]),
        ("leg_L", KP["hip_l"], KP["knee_l"], KP["ank_l"]),
        ("leg_R", KP["hip_r"], KP["knee_r"], KP["ank_r"]),
    ]
    
    for name, i_s, i_j, i_e in limbs:
        if valid(i_s) and valid(i_j) and valid(i_e):
            p_s = kpts[i_s]
            p_j = kpts[i_j]
            p_e = kpts[i_e]
            
            console.print(f"[green]Found {name} joint![/green]")
            
            # Mask for Lower Part (from Joint to End)
            # We construct a mask using the Cut Line.
            line = get_cut_line(p_s, p_j, p_e)
            if not line: continue
            
            (x1, y1), (x2, y2) = line
            
            # Draw cut line for debug
            cv2.line(viz, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.circle(viz, (int(p_j[0]), int(p_j[1])), 5, (255, 0, 0), -1)
            
            # Create a mask that splits the image based on this line
            # The "Lower" side is where the p_end is.
            # Using Vector math: (P - P_line_point) dot Normal > 0
            
            mask_lower = np.zeros((h, w), dtype=np.uint8)
            y_i, x_i = np.indices((h, w))
            
            # Vector along cut line
            vx_line = x2 - x1
            vy_line = y2 - y1
            
            # Normal to cut line (pointing towards Lower arm)
            # Check p_end side
            nx = -vy_line
            ny = vx_line
            
            # Check sign with p_end (p_e)
            dot_end = nx * (p_e[0] - x1) + ny * (p_e[1] - y1)
            if dot_end < 0:
                nx, ny = -nx, -ny
                
            # Line equation check
            val = nx * (x_i - x1) + ny * (y_i - y1)
            mask_lower[val > 0] = 255
            
            # Additional Distance Constraint?
            # Improve: Only include pixels close to the bone segment?
            # For now, let's just save the masked image.
            
            # Extract Lower
            lower_part = img_np.copy()
            lower_part[:, :, 3] = np.minimum(lower_part[:, :, 3], mask_lower)
            
            Image.fromarray(lower_part).save(out_dir / f"{name}_lower_test.png")
            
            # Extract Upper (Inverse Mask)
            upper_part = img_np.copy()
            upper_part[:, :, 3] = np.minimum(upper_part[:, :, 3], 255 - mask_lower)
            Image.fromarray(upper_part).save(out_dir / f"{name}_upper_test.png")
            
    # Save Viz
    Image.fromarray(viz).save(out_dir / "pose_debug.png")
    console.print(f"[blue]Saved debug viz to {out_dir / 'pose_debug.png'}[/blue]")

if __name__ == "__main__":
    main()
