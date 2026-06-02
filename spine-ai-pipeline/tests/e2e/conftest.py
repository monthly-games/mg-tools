"""Shared fixtures for E2E pipeline tests."""

import pytest
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent  # spine-ai-pipeline/


@pytest.fixture
def pipeline_root() -> Path:
    return PIPELINE_ROOT


@pytest.fixture
def input_single_dir(pipeline_root) -> Path:
    d = pipeline_root / "test" / "input_single"
    if not d.exists():
        pytest.skip(f"Test input not found: {d}")
    return d


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent / "golden"


@pytest.fixture
def expected_skeleton_bones() -> list:
    """표준 humanoid 스켈레톤이 가져야 할 최소 bone 이름."""
    return ["root", "hip", "spine", "chest"]


@pytest.fixture
def expected_animations() -> list:
    """표준 humanoid 스켈레톤이 가져야 할 최소 animation 이름."""
    return ["idle"]


@pytest.fixture
def sample_skeleton_json():
    """테스트용 유효한 Spine 스켈레톤 dict (골든 레퍼런스와 동일 구조)."""
    return {
        "spine": "4.1",
        "bones": [
            {"name": "root"},
            {"name": "hip", "parent": "root", "length": 30},
            {"name": "spine", "parent": "hip", "length": 50},
            {"name": "chest", "parent": "spine", "length": 40},
            {"name": "head", "parent": "chest", "length": 60},
        ],
        "animations": {"idle": {}, "walk": {}},
        "skins": [{"name": "default", "attachments": {}}],
    }
