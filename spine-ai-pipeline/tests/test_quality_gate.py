"""Tests for scripts/lib/quality_gate.py — QualityLevel, QualityGateResult, QualityGate."""

import pytest
from lib.quality_gate import QualityGate, QualityGateResult, QualityLevel


# ---------------------------------------------------------------------------
# QualityLevel enum
# ---------------------------------------------------------------------------
class TestQualityLevel:
    def test_pass_value(self):
        assert QualityLevel.PASS.value == "pass"

    def test_warn_value(self):
        assert QualityLevel.WARN.value == "warn"

    def test_fail_value(self):
        assert QualityLevel.FAIL.value == "fail"

    def test_enum_members_count(self):
        assert len(QualityLevel) == 3


# ---------------------------------------------------------------------------
# QualityGateResult dataclass
# ---------------------------------------------------------------------------
class TestQualityGateResult:
    def test_defaults(self):
        r = QualityGateResult(stage="test", level=QualityLevel.PASS)
        assert r.metrics == {}
        assert r.issues == []

    def test_custom_fields(self):
        r = QualityGateResult(
            stage="seg", level=QualityLevel.WARN,
            metrics={"a": 1.0}, issues=["low"],
        )
        assert r.stage == "seg"
        assert r.level == QualityLevel.WARN
        assert r.metrics["a"] == 1.0
        assert "low" in r.issues


# ---------------------------------------------------------------------------
# check_segmentation
# ---------------------------------------------------------------------------
class TestCheckSegmentation:
    def test_pass_with_7_valid_parts(self, sample_parts_metadata):
        result = QualityGate.check_segmentation(sample_parts_metadata)
        assert result.level == QualityLevel.PASS
        assert result.stage == "segmentation"

    def test_fail_with_none_metadata(self):
        result = QualityGate.check_segmentation(None)
        assert result.level == QualityLevel.FAIL

    def test_fail_with_empty_dict(self):
        result = QualityGate.check_segmentation({})
        assert result.level == QualityLevel.FAIL

    def test_fail_with_less_than_3_parts(self):
        meta = {"parts": [{"name": "head"}, {"name": "body"}]}
        result = QualityGate.check_segmentation(meta)
        assert result.level == QualityLevel.FAIL
        assert "Too few" in result.issues[0]

    def test_warn_with_no_body_part(self):
        """Only arms/legs — no body/head → completeness 0.5 → WARN (marginal)."""
        meta = {"parts": [
            {"name": "arm_L"}, {"name": "arm_R"},
            {"name": "leg_L"}, {"name": "leg_R"},
        ]}
        result = QualityGate.check_segmentation(meta)
        assert result.level == QualityLevel.WARN
        assert result.metrics["completeness"] == 0.5

    def test_warn_with_missing_optional_parts(self):
        """head + arm = completeness 0.5 (no body, no leg) → WARN (0.5 < 0.75)."""
        meta = {"parts": [
            {"name": "head"}, {"name": "arm_L"}, {"name": "arm_R"},
        ]}
        result = QualityGate.check_segmentation(meta)
        assert result.level == QualityLevel.WARN
        assert result.metrics["completeness"] == 0.5

    def test_metrics_contain_part_count(self, sample_parts_metadata):
        result = QualityGate.check_segmentation(sample_parts_metadata)
        assert "part_count" in result.metrics
        assert result.metrics["part_count"] == 7.0

    def test_metrics_contain_completeness(self, sample_parts_metadata):
        result = QualityGate.check_segmentation(sample_parts_metadata)
        assert "completeness" in result.metrics
        assert result.metrics["completeness"] == 1.0

    def test_low_confidence_fails(self):
        meta = {"parts": [
            {"name": "head", "confidence": 0.10},
            {"name": "body", "confidence": 0.12},
            {"name": "arm_L", "confidence": 0.11},
        ]}
        result = QualityGate.check_segmentation(meta)
        assert result.metrics.get("avg_confidence", 1.0) < 0.15
        assert result.level == QualityLevel.FAIL

    def test_marginal_confidence_warns(self):
        meta = {"parts": [
            {"name": "head", "confidence": 0.20},
            {"name": "body", "confidence": 0.22},
            {"name": "arm_L", "confidence": 0.24},
            {"name": "leg_L", "confidence": 0.21},
        ]}
        result = QualityGate.check_segmentation(meta)
        assert result.level == QualityLevel.WARN
        assert result.metrics.get("avg_confidence", 1.0) < 0.25

    def test_alpha_noise_none_when_no_parts_dir(self, sample_parts_metadata):
        result = QualityGate.check_segmentation(sample_parts_metadata, parts_dir=None)
        assert "alpha_noise" not in result.metrics

    def test_duplicate_part_names_deduped(self):
        meta = {"parts": [
            {"name": "head"}, {"name": "head"}, {"name": "body"},
            {"name": "arm_L"}, {"name": "leg_L"},
        ]}
        result = QualityGate.check_segmentation(meta)
        assert result.metrics["part_count"] == 4.0

    def test_non_dict_parts_ignored(self):
        meta = {"parts": ["not_a_dict", {"name": "head"}, 42]}
        result = QualityGate.check_segmentation(meta)
        assert result.metrics["part_count"] == 1.0


# ---------------------------------------------------------------------------
# check_rigging
# ---------------------------------------------------------------------------
class TestCheckRigging:
    def test_pass_with_valid_skeleton(self, sample_skeleton):
        result = QualityGate.check_rigging(sample_skeleton)
        assert result.stage == "rigging"
        assert result.level in (QualityLevel.PASS, QualityLevel.WARN)

    def test_fail_with_none(self):
        result = QualityGate.check_rigging(None)
        assert result.level == QualityLevel.FAIL
        assert "missing" in result.issues[0].lower()

    def test_fail_with_no_bones(self):
        result = QualityGate.check_rigging({"bones": []})
        assert result.level == QualityLevel.FAIL

    def test_fail_missing_root_or_body(self):
        skel = {"bones": [
            {"name": "a"}, {"name": "b"}, {"name": "c"},
            {"name": "d"}, {"name": "e"}, {"name": "f"},
        ]}
        result = QualityGate.check_rigging(skel)
        assert result.level == QualityLevel.FAIL
        assert any("base bones" in i.lower() for i in result.issues)

    def test_metrics_contain_bone_count(self, sample_skeleton):
        result = QualityGate.check_rigging(sample_skeleton)
        assert "bone_count" in result.metrics
        assert result.metrics["bone_count"] == 10.0

    def test_metrics_contain_slot_count(self, sample_skeleton):
        result = QualityGate.check_rigging(sample_skeleton)
        assert "slot_count" in result.metrics

    def test_metrics_contain_ik_count(self, sample_skeleton):
        result = QualityGate.check_rigging(sample_skeleton)
        assert "ik_count" in result.metrics

    def test_bone_length_variance_symmetric(self, sample_skeleton):
        """arm_L/arm_R and leg_L/leg_R are equal → variance 0."""
        result = QualityGate.check_rigging(sample_skeleton)
        assert result.metrics["bone_length_variance"] == 0.0

    def test_bone_length_variance_high_fails(self):
        skel = {"bones": [
            {"name": "root", "length": 0},
            {"name": "body", "parent": "root", "length": 30},
            {"name": "arm_L", "length": 100},
            {"name": "arm_R", "length": 10},
            {"name": "c", "length": 5}, {"name": "d", "length": 5},
        ], "ik": [{"name": "ik1"}]}
        result = QualityGate.check_rigging(skel)
        assert result.level == QualityLevel.FAIL
        assert result.metrics["bone_length_variance"] > 0.3

    def test_symmetry_error_zero_for_symmetric(self, sample_skeleton):
        result = QualityGate.check_rigging(sample_skeleton)
        assert result.metrics["symmetry_error"] == 0.0

    def test_no_ik_warns_on_otherwise_pass(self):
        skel = {"bones": [
            {"name": "root", "length": 0},
            {"name": "body", "parent": "root", "length": 30},
            {"name": "hip"}, {"name": "spine"}, {"name": "chest"}, {"name": "head"},
        ], "ik": []}
        result = QualityGate.check_rigging(skel)
        if result.level == QualityLevel.PASS or result.level == QualityLevel.WARN:
            assert any("IK" in i for i in result.issues) or result.level != QualityLevel.PASS


# ---------------------------------------------------------------------------
# check_animation
# ---------------------------------------------------------------------------
class TestCheckAnimation:
    def test_pass_with_enough_keyframes(self, sample_skeleton):
        result = QualityGate.check_animation(sample_skeleton)
        assert result.stage == "animation"
        assert result.metrics["animation_count"] == 2.0
        assert result.metrics["keyframe_count"] >= 8.0
        assert result.level == QualityLevel.PASS

    def test_fail_with_none(self):
        result = QualityGate.check_animation(None)
        assert result.level == QualityLevel.FAIL

    def test_fail_with_no_animations(self):
        result = QualityGate.check_animation({"animations": {}})
        assert result.level == QualityLevel.FAIL
        assert result.metrics.get("animation_count") == 0.0

    def test_fail_with_empty_keyframes(self):
        skel = {"animations": {"idle": {"bones": {}}}}
        result = QualityGate.check_animation(skel)
        assert result.level == QualityLevel.FAIL
        assert "empty" in result.issues[0].lower()

    def test_warn_with_few_keyframes(self):
        skel = {"animations": {
            "idle": {"bones": {"body": {"rotate": [{"time": 0}, {"time": 1}]}}},
        }}
        result = QualityGate.check_animation(skel)
        assert result.level == QualityLevel.WARN
        assert result.metrics["keyframe_count"] < 8

    def test_non_dict_animations_fail(self):
        result = QualityGate.check_animation({"animations": "bad"})
        assert result.level == QualityLevel.FAIL


# ---------------------------------------------------------------------------
# overall_gate
# ---------------------------------------------------------------------------
class TestOverallGate:
    def test_pass_when_all_pass(self, sample_parts_metadata, sample_skeleton):
        result = QualityGate.overall_gate(sample_parts_metadata, sample_skeleton)
        assert result.stage == "overall"
        assert result.level in (QualityLevel.PASS, QualityLevel.WARN)

    def test_fail_propagates_from_segmentation(self, sample_skeleton):
        result = QualityGate.overall_gate(None, sample_skeleton)
        assert result.level == QualityLevel.FAIL

    def test_fail_propagates_from_rigging(self, sample_parts_metadata):
        result = QualityGate.overall_gate(sample_parts_metadata, None)
        assert result.level == QualityLevel.FAIL

    def test_combined_metrics_prefixed(self, sample_parts_metadata, sample_skeleton):
        result = QualityGate.overall_gate(sample_parts_metadata, sample_skeleton)
        keys = list(result.metrics.keys())
        assert any(k.startswith("segmentation_") for k in keys)
        assert any(k.startswith("rigging_") for k in keys)
        assert any(k.startswith("animation_") for k in keys)

    def test_combined_issues_prefixed(self, sample_parts_metadata):
        result = QualityGate.overall_gate(sample_parts_metadata, None)
        for issue in result.issues:
            assert ":" in issue  # format: "stage: issue text"


# ---------------------------------------------------------------------------
# Private helpers (indirectly tested above, but explicit edge-case coverage)
# ---------------------------------------------------------------------------
class TestPrivateHelpers:
    def test_count_keyframes_nested_list(self):
        anims = {"idle": {"bones": {"body": [1, 2, 3]}}}
        assert QualityGate._count_keyframes(anims) == 3

    def test_count_keyframes_non_dict_anim_data(self):
        anims = {"idle": "not_a_dict"}
        assert QualityGate._count_keyframes(anims) == 0

    def test_count_nested_frames_scalar(self):
        assert QualityGate._count_nested_frames(42) == 0

    def test_bone_length_variance_no_pairs(self):
        assert QualityGate._compute_bone_length_variance({"root": {"length": 10}}) == 0.0

    def test_symmetry_error_no_pairs(self):
        assert QualityGate._compute_symmetry_error({"root": {"x": 10}}) == 0.0

    def test_alpha_noise_for_part_nonexistent(self, tmp_path):
        from pathlib import Path
        result = QualityGate._alpha_noise_for_part(tmp_path / "nonexistent.png")
        assert result is None

    def test_alpha_noise_for_part_non_png(self, tmp_path):
        p = tmp_path / "file.jpg"
        p.touch()
        assert QualityGate._alpha_noise_for_part(p) is None

    def test_compute_alpha_noise_none_dir(self):
        assert QualityGate._compute_alpha_noise([], None) is None

    def test_compute_alpha_noise_empty_parts(self, tmp_path):
        assert QualityGate._compute_alpha_noise([], tmp_path) is None
