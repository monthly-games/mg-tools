"""Tests for adaptive chibi skeleton generation from YOLO pose keypoints."""

# pyright: reportPrivateUsage=false

import math
from collections.abc import Sequence
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import numpy as np
import pytest

from lib.spine_templates import (
    BodyProportions,
    _apply_chibi_transform,
    _calculate_body_proportions,
    _extract_keypoint,
    _CHIBI_BONE_DEFAULTS,
    _REQUIRED_CHIBI_BONES,
    get_adaptive_chibi_template,
    get_template,
)


# ---------------------------------------------------------------------------
# Helpers — COCO-format keypoints (for legacy / internal-function tests)
# ---------------------------------------------------------------------------

def _valid_keypoints(with_conf=True):
    # type: (bool) -> List[List[float]]
    """Return minimal valid COCO keypoints for torso + legs."""
    if with_conf:
        kpts = [[0.0, 0.0, 0.0] for _ in range(17)]  # type: List[List[float]]
        kpts[5] = [80.0, 120.0, 0.9]   # left_shoulder
        kpts[6] = [120.0, 120.0, 0.9]  # right_shoulder
        kpts[11] = [85.0, 220.0, 0.9]  # left_hip
        kpts[12] = [115.0, 220.0, 0.9]  # right_hip
        kpts[15] = [85.0, 380.0, 0.9]  # left_ankle
        kpts[16] = [115.0, 380.0, 0.9]  # right_ankle
        return kpts

    kpts = [[0.0, 0.0] for _ in range(17)]
    kpts[5] = [80.0, 120.0]
    kpts[6] = [120.0, 120.0]
    kpts[11] = [85.0, 220.0]
    kpts[12] = [115.0, 220.0]
    kpts[15] = [85.0, 380.0]
    kpts[16] = [115.0, 380.0]
    return kpts


def _sample_proportions(
    head_height,    # type: float
    torso_height,   # type: float
    leg_height,     # type: float
    shoulder_width,  # type: float
    total_height,   # type: float
):
    # type: (...) -> BodyProportions
    return {
        "head_height": head_height,
        "torso_height": torso_height,
        "leg_height": leg_height,
        "shoulder_width": shoulder_width,
        "total_height": total_height,
        "valid": False,
    }


def _adaptive_coco():
    # type: () -> Dict[str, Any]
    return cast(Dict[str, Any], get_adaptive_chibi_template(_valid_keypoints()))


def _bones_coco(template):
    # type: (Dict[str, Any]) -> List[Dict[str, Any]]
    return cast(List[Dict[str, Any]], template["bones"])


def _template_dict(name):
    # type: (str) -> Dict[str, Any]
    return cast(Dict[str, Any], get_template(name))


# ---------------------------------------------------------------------------
# Helpers — Dict-format keypoints (for new confidence-aware interface)
# ---------------------------------------------------------------------------

def _kp_dict(confidence=0.9):
    # type: (float) -> Dict[str, Any]
    """Return valid keypoints in Dict[str, Any] format with given confidence."""
    return {
        "nose": {"x": 100.0, "y": 50.0, "confidence": confidence},
        "left_shoulder": {"x": 80.0, "y": 120.0, "confidence": confidence},
        "right_shoulder": {"x": 120.0, "y": 120.0, "confidence": confidence},
        "left_elbow": {"x": 60.0, "y": 170.0, "confidence": confidence},
        "right_elbow": {"x": 140.0, "y": 170.0, "confidence": confidence},
        "left_hip": {"x": 85.0, "y": 220.0, "confidence": confidence},
        "right_hip": {"x": 115.0, "y": 220.0, "confidence": confidence},
        "left_knee": {"x": 85.0, "y": 300.0, "confidence": confidence},
        "right_knee": {"x": 115.0, "y": 300.0, "confidence": confidence},
        "left_ankle": {"x": 85.0, "y": 380.0, "confidence": confidence},
        "right_ankle": {"x": 115.0, "y": 380.0, "confidence": confidence},
    }


def _kp_dict_partial():
    # type: () -> Dict[str, Any]
    """Only shoulders and hips — minimal for torso detection."""
    return {
        "left_shoulder": {"x": 80.0, "y": 120.0, "confidence": 0.9},
        "right_shoulder": {"x": 120.0, "y": 120.0, "confidence": 0.9},
        "left_hip": {"x": 85.0, "y": 220.0, "confidence": 0.9},
        "right_hip": {"x": 115.0, "y": 220.0, "confidence": 0.9},
    }


_BONE_FIELDS = ("x", "y", "rotation", "scale_x", "scale_y")


def _adaptive(kp=None, threshold=0.5):
    # type: (Optional[Dict[str, Any]], float) -> Dict[str, Any]
    """Shortcut to call get_adaptive_chibi_template with Dict keypoints."""
    if kp is None:
        kp = _kp_dict()
    return get_adaptive_chibi_template(kp, confidence_threshold=threshold)


# ===================================================================
# Tests for internal helpers (unchanged functions)
# ===================================================================

class TestCalculateBodyProportions:
    def test_valid_keypoints_returns_valid_true(self):
        p = _calculate_body_proportions(_valid_keypoints())
        assert p["valid"] is True

    def test_invalid_keypoints_returns_valid_false(self):
        p = _calculate_body_proportions([[0.0, 0.0, 0.0] for _ in range(17)])
        assert p["valid"] is False

    def test_low_confidence_keypoints_ignored(self):
        kpts = _valid_keypoints()
        kpts[5][2] = 0.1
        kpts[6][2] = 0.1
        p = _calculate_body_proportions(kpts)
        assert p["valid"] is False

    def test_shoulder_width_calculated(self):
        p = _calculate_body_proportions(_valid_keypoints())
        assert p["shoulder_width"] == 40.0

    def test_torso_height_calculated(self):
        p = _calculate_body_proportions(_valid_keypoints())
        assert p["torso_height"] == 100.0

    def test_leg_height_calculated(self):
        p = _calculate_body_proportions(_valid_keypoints())
        assert p["leg_height"] == 160.0

    def test_zero_coordinates_ignored(self):
        kpts = _valid_keypoints()
        kpts[5] = [0.0, 120.0, 0.9]
        p = _calculate_body_proportions(kpts)
        assert p["valid"] is True
        assert p["shoulder_width"] == 60.0


class TestApplyChibiTransform:
    def test_head_enlarged_vs_realistic(self):
        p = _sample_proportions(20.0, 80.0, 100.0, 60.0, 200.0)
        lengths = _apply_chibi_transform(p)
        assert lengths["head"] > p["head_height"]

    def test_torso_reduced_vs_realistic(self):
        p = _sample_proportions(20.0, 80.0, 100.0, 60.0, 200.0)
        lengths = _apply_chibi_transform(p)
        assert lengths["torso"] < p["torso_height"]

    def test_all_values_clamped_10_300(self):
        p = _sample_proportions(2000.0, 2000.0, 2000.0, 2000.0, 5000.0)
        lengths = _apply_chibi_transform(p)
        clamped_values = [
            lengths["head"], lengths["neck"], lengths["torso"],
            lengths["upper_arm"], lengths["lower_arm"],
            lengths["upper_leg"], lengths["lower_leg"],
            lengths["shoulder_width"],
        ]
        assert all(10.0 <= v <= 300.0 for v in clamped_values)

    def test_returns_all_required_keys(self):
        p = _sample_proportions(20.0, 80.0, 100.0, 60.0, 200.0)
        lengths = _apply_chibi_transform(p)
        assert set(lengths.keys()) == {
            "head", "neck", "torso",
            "upper_arm", "lower_arm",
            "upper_leg", "lower_leg",
            "shoulder_width",
        }


# ===================================================================
# Tests for COCO-format backward compatibility
# ===================================================================

class TestAdaptiveChibiTemplateCOCO:
    """Backward-compat: Sequence[Sequence[float]] input still works."""

    def test_returns_bones_key(self):
        template = _adaptive_coco()
        assert "bones" in template

    def test_returns_animations_key(self):
        template = _adaptive_coco()
        assert "animations" in template

    def test_bones_have_names(self):
        template = _adaptive_coco()
        assert all("name" in bone for bone in _bones_coco(template))

    def test_root_bone_exists(self):
        template = _adaptive_coco()
        names = {cast(str, bone["name"]) for bone in _bones_coco(template)}
        assert "root" in names

    def test_head_bone_exists(self):
        template = _adaptive_coco()
        names = {cast(str, bone["name"]) for bone in _bones_coco(template)}
        assert "head" in names

    def test_bone_lengths_clamped(self):
        template = _adaptive_coco()
        lengths = [
            float(cast(Union[int, float], bone["length"]))
            for bone in _bones_coco(template)
            if "length" in bone and bone.get("name") != "root"
        ]
        assert all(10.0 <= v <= 300.0 for v in lengths)

    def test_fallback_on_invalid_keypoints(self):
        fallback = get_adaptive_chibi_template([[0.0, 0.0, 0.0] for _ in range(17)])
        assert fallback == get_template("chibi")

    def test_adaptive_larger_head_ratio(self):
        template = _adaptive_coco()
        by_name = {cast(str, bone["name"]): bone for bone in _bones_coco(template)}
        head = float(cast(Union[int, float], by_name["head"]["length"]))
        torso = float(cast(Union[int, float], by_name["hip"]["length"]))
        upper_leg = float(cast(Union[int, float], by_name["leg_L"]["length"]))
        lower_leg = float(cast(Union[int, float], by_name["shin_L"]["length"]))
        total = head + torso + upper_leg + lower_leg
        ratio = head / total
        assert ratio > 0.35

    def test_no_regression_on_static_templates(self):
        humanoid = _template_dict("humanoid")
        chibi = _template_dict("chibi")
        monster = _template_dict("monster")
        assert "bones" in humanoid and isinstance(humanoid["bones"], list)
        assert "bones" in chibi and isinstance(chibi["bones"], list)
        assert "bones" in monster and isinstance(monster["bones"], list)
        assert isinstance(humanoid["ik"], list)
        assert isinstance(chibi["ik"], list)
        assert isinstance(monster["ik"], list)


# ===================================================================
# Tests for Dict-based adaptive chibi template (NEW)
# ===================================================================

class TestAdaptiveChibiDictRequired:
    """Given valid Dict keypoints, the result has all required bones and fields."""

    def test_returns_dict(self):
        result = _adaptive()
        assert isinstance(result, dict)

    def test_has_all_required_bones(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            assert bone in result, "Missing bone: {}".format(bone)

    def test_each_bone_has_x(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            assert "x" in result[bone], "Bone {} missing 'x'".format(bone)

    def test_each_bone_has_y(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            assert "y" in result[bone], "Bone {} missing 'y'".format(bone)

    def test_each_bone_has_rotation(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            assert "rotation" in result[bone]

    def test_each_bone_has_scale_x(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            assert "scale_x" in result[bone]

    def test_each_bone_has_scale_y(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            assert "scale_y" in result[bone]

    def test_all_values_are_numeric(self):
        result = _adaptive()
        for bone in _REQUIRED_CHIBI_BONES:
            for field in _BONE_FIELDS:
                assert isinstance(result[bone][field], (int, float))


class TestChibiProportions:
    """Chibi body proportions: big head, short arms, short legs."""

    def test_head_scale_greater_than_1(self):
        result = _adaptive()
        assert result["head"]["scale_x"] > 1.0
        assert result["head"]["scale_y"] > 1.0

    def test_arm_l_scale_less_than_1(self):
        result = _adaptive()
        assert result["arm_l"]["scale_x"] < 1.0
        assert result["arm_l"]["scale_y"] < 1.0

    def test_arm_r_scale_less_than_1(self):
        result = _adaptive()
        assert result["arm_r"]["scale_x"] < 1.0
        assert result["arm_r"]["scale_y"] < 1.0

    def test_leg_l_scale_less_than_1(self):
        result = _adaptive()
        assert result["leg_l"]["scale_x"] < 1.0
        assert result["leg_l"]["scale_y"] < 1.0

    def test_leg_r_scale_less_than_1(self):
        result = _adaptive()
        assert result["leg_r"]["scale_x"] < 1.0
        assert result["leg_r"]["scale_y"] < 1.0

    def test_root_scale_is_unit(self):
        result = _adaptive()
        assert result["root"]["scale_x"] == 1.0
        assert result["root"]["scale_y"] == 1.0

    def test_head_scale_larger_than_arm_scale(self):
        result = _adaptive()
        assert result["head"]["scale_x"] > result["arm_l"]["scale_x"]

    def test_head_scale_larger_than_leg_scale(self):
        result = _adaptive()
        assert result["head"]["scale_x"] > result["leg_l"]["scale_x"]


class TestConfidenceThreshold:
    """Confidence-based adaptive behaviour."""

    def test_default_threshold_is_0_5(self):
        # Given keypoints with conf=0.6 → default threshold 0.5 → adaptive
        kp = _kp_dict(confidence=0.6)
        result = get_adaptive_chibi_template(kp)
        defaults = get_adaptive_chibi_template({})
        assert result != defaults

    def test_all_below_threshold_returns_defaults(self):
        # Given conf=0.3 and threshold=0.5 → all joints below → defaults
        kp = _kp_dict(confidence=0.3)
        result = get_adaptive_chibi_template(kp, confidence_threshold=0.5)
        defaults = get_adaptive_chibi_template({})
        assert result == defaults

    def test_high_confidence_uses_keypoint_positions(self):
        # Given conf=0.95 → positions derived from keypoints
        kp = _kp_dict(confidence=0.95)
        result = _adaptive(kp, threshold=0.5)
        expected_hip_x = (85.0 + 115.0) / 2.0
        assert abs(result["hip"]["x"] - expected_hip_x) < 1.0

    def test_custom_threshold_0_8_filters_moderate_confidence(self):
        # Given conf=0.7 → threshold=0.8 → falls back to defaults
        kp = _kp_dict(confidence=0.7)
        result = get_adaptive_chibi_template(kp, confidence_threshold=0.8)
        defaults = get_adaptive_chibi_template({})
        assert result == defaults

    def test_threshold_0_accepts_all(self):
        # Given conf=0.01 → threshold=0.0 → adaptive (not defaults)
        kp = _kp_dict(confidence=0.01)
        result = get_adaptive_chibi_template(kp, confidence_threshold=0.0)
        defaults = get_adaptive_chibi_template({})
        assert result != defaults

    def test_mixed_confidence_partial_adaptation(self):
        # Given: shoulders/hips high conf, elbows low conf
        kp = _kp_dict(confidence=0.9)
        kp["left_elbow"] = {"x": 60.0, "y": 170.0, "confidence": 0.1}
        kp["right_elbow"] = {"x": 140.0, "y": 170.0, "confidence": 0.1}
        result = _adaptive(kp, threshold=0.5)
        # Arms placed (shoulders valid) but rotation defaults to 0
        assert result["arm_l"]["rotation"] == 0.0
        assert result["arm_r"]["rotation"] == 0.0


class TestAdaptivePositions:
    """Keypoint positions influence bone placement."""

    def test_shoulder_position_affects_chest(self):
        result = _adaptive()
        expected_x = (80.0 + 120.0) / 2.0
        assert abs(result["chest"]["x"] - expected_x) < 1.0

    def test_hip_position_affects_hip_bone(self):
        result = _adaptive()
        expected_x = (85.0 + 115.0) / 2.0
        assert abs(result["hip"]["x"] - expected_x) < 1.0

    def test_nose_affects_head_position(self):
        kp = _kp_dict()
        kp["nose"] = {"x": 105.0, "y": 50.0, "confidence": 0.9}
        result = _adaptive(kp)
        assert abs(result["head"]["x"] - 105.0) < 5.0

    def test_elbow_affects_arm_rotation(self):
        # Given elbow directly below shoulder → rotation ≈ 0
        kp = _kp_dict()
        kp["left_elbow"] = {"x": 80.0, "y": 170.0, "confidence": 0.9}
        result = _adaptive(kp)
        assert abs(result["arm_l"]["rotation"]) < 5.0

    def test_knee_affects_leg_rotation(self):
        kp = _kp_dict()
        kp["left_knee"] = {"x": 85.0, "y": 300.0, "confidence": 0.9}
        result = _adaptive(kp)
        assert abs(result["leg_l"]["rotation"]) < 5.0

    def test_partial_keypoints_only_shoulders_and_hips(self):
        result = _adaptive(_kp_dict_partial())
        for bone in _REQUIRED_CHIBI_BONES:
            assert bone in result


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_keypoints_returns_defaults(self):
        result = get_adaptive_chibi_template({})
        for bone in _REQUIRED_CHIBI_BONES:
            assert bone in result

    def test_zero_coordinate_treated_as_invalid(self):
        kp = _kp_dict()
        kp["left_shoulder"] = {"x": 0.0, "y": 120.0, "confidence": 0.9}
        kp["right_shoulder"] = {"x": 0.0, "y": 120.0, "confidence": 0.9}
        result = get_adaptive_chibi_template(kp, confidence_threshold=0.5)
        defaults = get_adaptive_chibi_template({})
        assert result == defaults

    def test_negative_coordinate_treated_as_invalid(self):
        kp = _kp_dict()
        kp["left_shoulder"] = {"x": -10.0, "y": 120.0, "confidence": 0.9}
        kp["right_shoulder"] = {"x": -20.0, "y": 120.0, "confidence": 0.9}
        result = get_adaptive_chibi_template(kp, confidence_threshold=0.5)
        defaults = get_adaptive_chibi_template({})
        assert result == defaults

    def test_very_high_confidence_accepted(self):
        kp = _kp_dict(confidence=1.0)
        result = _adaptive(kp)
        defaults = get_adaptive_chibi_template({})
        assert result != defaults

    def test_result_is_independent_copy(self):
        result1 = get_adaptive_chibi_template({})
        result2 = get_adaptive_chibi_template({})
        result1["head"]["x"] = 9999.0
        assert result2["head"]["x"] != 9999.0


class TestExtractKeypoint:
    def test_valid_keypoint_extracted(self):
        kpts = _valid_keypoints()
        assert _extract_keypoint(kpts, "left_shoulder") == (80.0, 120.0)

    def test_low_confidence_returns_none(self):
        kpts = _valid_keypoints()
        kpts[5][2] = 0.2
        assert _extract_keypoint(kpts, "left_shoulder") is None

    def test_zero_x_returns_none(self):
        kpts = _valid_keypoints()
        kpts[5] = [0.0, 120.0, 0.9]
        assert _extract_keypoint(kpts, "left_shoulder") is None

    def test_index_out_of_range_returns_none(self):
        assert _extract_keypoint([], "left_shoulder") is None

    def test_supports_2d_and_3d_keypoints(self):
        kpts_2d = np.array(_valid_keypoints(with_conf=False), dtype=float)
        kpts_3d = np.array(_valid_keypoints(with_conf=True), dtype=float)
        assert _extract_keypoint(
            cast(Sequence[Sequence[float]], cast(object, kpts_2d)),
            "left_shoulder",
        ) == (80.0, 120.0)
        assert _extract_keypoint(
            cast(Sequence[Sequence[float]], cast(object, kpts_3d)),
            "left_shoulder",
        ) == (80.0, 120.0)
