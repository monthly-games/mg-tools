
import cv2
import numpy as np
import argparse
from pathlib import Path
import json
import matplotlib.pyplot as plt
from scipy.spatial import Delaunay

def generate_mesh(image_path, epsilon_factor=0.005, edge_len=20):
    """
    Generate a mesh from an image using contour detection and Delaunay triangulation.
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Error: Could not load image {image_path}")
        return

    # Extract Alpha Channel
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        print("Image has no alpha channel. Using grayscale as mask.")
        alpha = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold
    _, binary = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)

    # Find Contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("No contours found.")
        return

    # Largest contour (in case of noise)
    cnt = max(contours, key=cv2.contourArea)

    # Simplify Contour (Douglas-Peucker)
    epsilon = epsilon_factor * cv2.arcLength(cnt, True)
    approx_contour = cv2.approxPolyDP(cnt, epsilon, True)
    hull_points = approx_contour.reshape(-1, 2)

    print(f"Original points: {len(cnt)}, Simplified points: {len(hull_points)}")

    # Triangulation (Constrained Delaunay - Simplified)
    # Ideally we want internal points (Steiner points) for better deformation.
    # For now, let's just triangulate the hull + grid/random internal points.
    
    # Generate internal points (Grid Sampling inside polygon)
    h, w = alpha.shape
    x_range = np.arange(0, w, edge_len)
    y_range = np.arange(0, h, edge_len)
    grid_x, grid_y = np.meshgrid(x_range, y_range)
    grid_points = np.vstack([grid_x.ravel(), grid_y.ravel()]).T

    # Filter points inside the contour
    inside_mask = []
    for pt in grid_points:
        dist = cv2.pointPolygonTest(approx_contour, (int(pt[0]), int(pt[1])), False)
        inside_mask.append(dist >= 0) # >= 0 means inside or on edge
    
    internal_points = grid_points[inside_mask]
    
    # Combine Hull + Internal
    all_points = np.vstack([hull_points, internal_points])
    
    # Triangulate
    tri = Delaunay(all_points)

    # Visualization
    plt.figure(figsize=(10, 10))
    plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
    plt.triplot(all_points[:, 0], all_points[:, 1], tri.simplices.copy())
    plt.plot(all_points[:, 0], all_points[:, 1], 'o', color='red', markersize=2)
    plt.title(f"Mesh: {len(all_points)} vertices, {len(tri.simplices)} triangles")
    plt.gca().invert_yaxis() # Match image coords
    
    output_img = str(image_path).replace(".png", "_mesh_debug.png")
    plt.savefig(output_img)
    print(f"Saved visualization to {output_img}")

    # Export Spine Mesh Format (Placeholder)
    # Spine meshes require: 
    # - uvs (normalized 0-1)
    # - triangles (indices)
    # - vertices (pixel coords, potentially weighted)
    
    spine_mesh = {
        "uvs": [],
        "triangles": tri.simplices.flatten().tolist(),
        "vertices": all_points.flatten().tolist(), # x, y, x, y...
        "hull": len(hull_points) # First N points are the hull
    }
    
    # Calculate UVs
    for pt in all_points:
        u = pt[0] / w
        v = 1.0 - (pt[1] / h) # Spine UV origin is bottom-left? Need to verify convention.
        # Actually standard texture coords: 0,0 top-left ?
        # Spine: y is up? UVs are 0-1.
        # Let's assume standard UV: u = x/w, v = y/h (inverted Y usually)
        spine_mesh["uvs"].extend([u, pt[1]/h]) 

    output_json = str(image_path).replace(".png", "_mesh.json")
    with open(output_json, 'w') as f:
        json.dump(spine_mesh, f, indent=2)
    print(f"Saved mesh data to {output_json}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input image part")
    args = parser.parse_args()
    
    generate_mesh(args.input)
