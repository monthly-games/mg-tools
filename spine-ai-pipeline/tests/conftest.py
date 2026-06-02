"""Shared fixtures for spine-ai-pipeline test suite."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# Ensure scripts/ is importable
PIPELINE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PIPELINE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def sample_parts_metadata():
    """Valid 7-part humanoid metadata with confidence scores."""
    return {
        "parts": [
            {"name": "head", "bbox": [10, 5, 50, 55], "alpha_coverage": 0.92, "confidence": 0.90},
            {"name": "body", "bbox": [15, 55, 45, 130], "alpha_coverage": 0.95, "confidence": 0.93},
            {"name": "arm_L", "bbox": [5, 60, 20, 110], "alpha_coverage": 0.88, "confidence": 0.85},
            {"name": "arm_R", "bbox": [45, 60, 60, 110], "alpha_coverage": 0.87, "confidence": 0.84},
            {"name": "leg_L", "bbox": [18, 130, 35, 200], "alpha_coverage": 0.91, "confidence": 0.88},
            {"name": "leg_R", "bbox": [30, 130, 47, 200], "alpha_coverage": 0.90, "confidence": 0.87},
            {"name": "weapon", "bbox": [50, 70, 75, 120], "alpha_coverage": 0.85, "confidence": 0.80},
        ],
        "image_size": [200, 256],
    }


@pytest.fixture
def sample_skeleton():
    """Valid Spine skeleton JSON with symmetric bones and animations with keyframes."""
    return {
        "bones": [
            {"name": "root", "length": 0},
            {"name": "body", "parent": "root", "length": 30, "x": 0, "y": 0},
            {"name": "hip", "parent": "body", "length": 30, "x": 0, "y": 30},
            {"name": "spine", "parent": "hip", "length": 50, "x": 0, "y": 30},
            {"name": "chest", "parent": "spine", "length": 40, "x": 0, "y": 80},
            {"name": "head", "parent": "chest", "length": 60, "x": 0, "y": 120},
            {"name": "arm_L", "parent": "chest", "length": 40, "x": -25, "y": 120},
            {"name": "arm_R", "parent": "chest", "length": 40, "x": 25, "y": 120},
            {"name": "leg_L", "parent": "hip", "length": 70, "x": -15, "y": 0},
            {"name": "leg_R", "parent": "hip", "length": 70, "x": 15, "y": 0},
        ],
        "slots": [{"name": "body_slot"}],
        "ik": [{"name": "leg_ik"}],
        "animations": {
            "idle": {
                "bones": {
                    "body": {"rotate": [{"time": 0, "angle": 0}, {"time": 1, "angle": 5}]},
                    "head": {"rotate": [{"time": 0, "angle": 0}, {"time": 0.5, "angle": -3}]},
                },
            },
            "walk": {
                "bones": {
                    "leg_L": {"rotate": [{"time": 0, "angle": 0}, {"time": 0.5, "angle": 30}]},
                    "leg_R": {"rotate": [{"time": 0, "angle": 0}, {"time": 0.5, "angle": -30}]},
                },
            },
        },
        "skins": [{"name": "default", "attachments": {}}],
    }


@pytest.fixture
def small_rgba_image():
    """64x64 RGBA test image (NumPy array) with orange rectangle."""
    img = np.zeros((64, 64, 4), dtype=np.uint8)
    img[20:44, 20:44] = [255, 128, 0, 255]
    return img


@pytest.fixture
def small_rgb_image():
    """64x64 RGB test image (NumPy array)."""
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[20:44, 20:44] = [255, 128, 0]
    return img


@pytest.fixture
def small_mask():
    """64x64 binary mask with central rectangle."""
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[20:44, 20:44] = 255
    return mask


@pytest.fixture
def mock_onnx_session():
    """Mock onnxruntime.InferenceSession returning a plausible output."""
    session = MagicMock()
    output = np.zeros((1, 3, 512, 512), dtype=np.float32)
    output[0, :, 100:400, 100:400] = 0.8
    session.run.return_value = [output]

    input_img = MagicMock()
    input_img.name = "image"
    input_mask = MagicMock()
    input_mask.name = "mask"
    session.get_inputs.return_value = [input_img, input_mask]

    output_node = MagicMock()
    output_node.name = "output"
    session.get_outputs.return_value = [output_node]
    return session
