#!/usr/bin/env python3
"""
Video to Motion (Bones) Converter
Extracts keypoints from a video using YOLO-Pose and converts them into
normalized bone rotation data for Spine animation.

Usage:
    python video_to_motion.py --video input.mp4 --output motion.json
"""

import argparse
import json
import math
from pathlib import Path
import cv2
import numpy as np
from rich.console import Console
from rich.progress import Progress

console = Console()

# COCO Keypoint Indices
# 0: Nose, 1: Eye_L, 2: Eye_R, 3: Ear_L, 4: Ear_R
# 5: Shoulder_L, 6: Shoulder_R
# 7: Elbow_L, 8: Elbow_R
# 9: Wrist_L, 10: Wrist_R
# 11: Hip_L, 12: Hip_R
# 13: Knee_L, 14: Knee_R
# 15: Ankle_L, 16: Ankle_R

KP_MAP = {
    "nose": 0,
    "shdr_l": 5, "shdr_r": 6,
    "elb_l": 7, "elb_r": 8,
    "wr_l": 9, "wr_r": 10,
    "hip_l": 11, "hip_r": 12,
    "knee_l": 13, "knee_r": 14,
    "ank_l": 15, "ank_r": 16
}

def calculate_angle(p1, p2):
    """Calculate angle (degrees) between p1 and p2 relative to vertical axis?"""
    # Standard Spine: 0 degrees might be "Start Pose" (T-pose or A-pose).
    # Here we just output absolute angle in 2D plane (0 = Right, 90 = Down)
    if p1 is None or p2 is None:
        return 0.0
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))

def main():
    parser = argparse.ArgumentParser(description="Video to Motion")
    parser.add_argument("--video", type=str, required=True, help="Input video path")
    parser.add_argument("--output", type=str, default="motion.json", help="Output JSON path")
    parser.add_argument("--visualize", action="store_true", help="Show visualization")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        console.print(f"[red]Video not found: {video_path}[/red]")
        return

    try:
        from ultralytics import YOLO
    except ImportError:
        console.print("[red]ultralytics not installed.[/red]")
        return

    console.print("[cyan]Loading YOLO-Pose model...[/cyan]")
    model = YOLO("yolo11n-pose.pt")

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    frames_data = []

    with Progress() as progress:
        task = progress.add_task("[green]Processing Frames...", total=total_frames)
        
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Run Inference
            results = model.predict(frame, verbose=False, max_det=1) # Assume single person
            
            frame_info = {
                "frame": frame_idx,
                "time": frame_idx / fps,
                "bones": {}
            }
            
            if results and results[0].keypoints:
                # Keypoints (1, 17, 2)
                # We need to handle when confidence is low?
                # YOLO keypoints object handles visibility
                
                kpts = results[0].keypoints.xy[0].cpu().numpy()
                confs = results[0].keypoints.conf[0].cpu().numpy() if results[0].keypoints.conf is not None else [1.0]*17
                
                # Helper to get point if high confidence
                def get_p(name):
                    idx = KP_MAP[name]
                    if confs[idx] > 0.5 and kpts[idx][0] > 0:
                        return kpts[idx]
                    return None

                # Calculate Bone Angles
                # Root/Body: Midpoint of Hips
                hip_l = get_p("hip_l")
                hip_r = get_p("hip_r")
                shdr_l = get_p("shdr_l")
                shdr_r = get_p("shdr_r")
                
                # Torso vector? (MidHip to MidShdr)
                if hip_l is not None and hip_r is not None and shdr_l is not None and shdr_r is not None:
                    mid_hip = (hip_l + hip_r) / 2
                    mid_shdr = (shdr_l + shdr_r) / 2
                    frame_info["bones"]["body"] = calculate_angle(mid_hip, mid_shdr) # Usually -90 (Up)
                    
                    # Root Position (Normalized 0-1)
                    h, w = frame.shape[:2]
                    frame_info["root_pos"] = {
                        "x": float(mid_hip[0] / w),
                        "y": float(mid_hip[1] / h)
                    }

                # Limbs
                # Left Arm
                elb_l = get_p("elb_l")
                if shdr_l is not None and elb_l is not None:
                    frame_info["bones"]["arm_L"] = calculate_angle(shdr_l, elb_l)
                    
                    wr_l = get_p("wr_l")
                    if wr_l is not None:
                        frame_info["bones"]["forearm_L"] = calculate_angle(elb_l, wr_l)

                # Right Arm
                elb_r = get_p("elb_r")
                if shdr_r is not None and elb_r is not None:
                    frame_info["bones"]["arm_R"] = calculate_angle(shdr_r, elb_r)
                    
                    wr_r = get_p("wr_r")
                    if wr_r is not None:
                        frame_info["bones"]["forearm_R"] = calculate_angle(elb_r, wr_r)

                # Legs
                knee_l = get_p("knee_l")
                if hip_l is not None and knee_l is not None:
                    frame_info["bones"]["leg_L"] = calculate_angle(hip_l, knee_l)
                    ank_l = get_p("ank_l")
                    if ank_l is not None:
                         frame_info["bones"]["shin_L"] = calculate_angle(knee_l, ank_l)

                knee_r = get_p("knee_r")
                if hip_r is not None and knee_r is not None:
                    frame_info["bones"]["leg_R"] = calculate_angle(hip_r, knee_r)
                    ank_r = get_p("ank_r")
                    if ank_r is not None:
                         frame_info["bones"]["shin_R"] = calculate_angle(knee_r, ank_r)

            frames_data.append(frame_info)
            progress.update(task, advance=1)
            frame_idx += 1
            
            if args.visualize:
                plotted = results[0].plot()
                cv2.imshow("VideoPose", plotted)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    cap.release()
    cv2.destroyAllWindows()

    # Save
    with open(args.output, "w") as f:
        json.dump({"fps": fps, "frames": frames_data}, f, indent=2)

    console.print(f"[green]Done. Saved to {args.output}[/green]")

if __name__ == "__main__":
    main()
