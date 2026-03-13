from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional


class QualityLevel(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class QualityGateResult:
    stage: str
    level: QualityLevel
    metrics: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


@dataclass
class QualityGate:
    alpha_noise_threshold: ClassVar[float] = 0.18
    bone_length_variance_threshold: ClassVar[float] = 0.40
    symmetry_error_threshold: ClassVar[float] = 0.20
    alpha_noise_fail_multiplier: ClassVar[float] = 2.0

    @staticmethod
    def check_segmentation(
        parts_metadata: Optional[Dict[str, Any]],
        parts_dir: Optional[Path] = None,
    ) -> QualityGateResult:
        metrics: Dict[str, float] = {}
        issues: List[str] = []
        level = QualityLevel.PASS

        parts = []
        if isinstance(parts_metadata, dict):
            parts = [part for part in parts_metadata.get("parts", []) if isinstance(part, dict)]

        part_names = {str(part.get("name", "")).strip() for part in parts if part.get("name")}
        part_names = {name for name in part_names if name}

        part_count = float(len(part_names))
        metrics["part_count"] = part_count

        if part_count < 3:
            issues.append("Too few extracted parts")
            level = QualityLevel.FAIL

        has_body = any(name in part_names for name in ["body", "torso", "chest"])
        has_head = any(name in part_names for name in ["head", "hair", "face"])
        has_arm = any("arm" in name or "hand" in name for name in part_names)
        has_leg = any("leg" in name or "thigh" in name or "hips" in name for name in part_names)

        completeness = float(sum([has_body, has_head, has_arm, has_leg])) / 4.0
        metrics["completeness"] = completeness

        if completeness < 0.5:
            issues.append("Segmentation completeness too low")
            level = QualityLevel.FAIL
        elif completeness < 0.75 and level != QualityLevel.FAIL:
            issues.append("Segmentation completeness is marginal")
            level = QualityLevel.WARN

        confidence_values = [
            float(part["confidence"])
            for part in parts
            if isinstance(part.get("confidence"), (int, float))
        ]
        if confidence_values:
            avg_confidence = sum(confidence_values) / float(len(confidence_values))
            metrics["avg_confidence"] = avg_confidence
            if avg_confidence < 0.15:
                issues.append("Part confidence is critically low")
                level = QualityLevel.FAIL
            elif avg_confidence < 0.25 and level != QualityLevel.FAIL:
                issues.append("Part confidence is low")
                level = QualityLevel.WARN

        alpha_noise = QualityGate._compute_alpha_noise(parts, parts_dir)
        if alpha_noise is not None:
            metrics["alpha_noise"] = alpha_noise
            if alpha_noise >= QualityGate.alpha_noise_threshold * QualityGate.alpha_noise_fail_multiplier:
                issues.append("Alpha noise is too high")
                level = QualityLevel.FAIL
            elif alpha_noise > QualityGate.alpha_noise_threshold and level != QualityLevel.FAIL:
                issues.append("Alpha noise above warning threshold")
                level = QualityLevel.WARN

        return QualityGateResult(stage="segmentation", level=level, metrics=metrics, issues=issues)

    @staticmethod
    def check_rigging(skeleton: Optional[Dict[str, Any]]) -> QualityGateResult:
        metrics: Dict[str, float] = {}
        issues: List[str] = []
        level = QualityLevel.PASS

        if not isinstance(skeleton, dict):
            return QualityGateResult(
                stage="rigging",
                level=QualityLevel.FAIL,
                metrics=metrics,
                issues=["Skeleton payload is missing"],
            )

        bones = [bone for bone in skeleton.get("bones", []) if isinstance(bone, dict)]
        bone_map = {str(bone.get("name", "")): bone for bone in bones if bone.get("name")}

        metrics["bone_count"] = float(len(bone_map))
        metrics["slot_count"] = float(len(skeleton.get("slots", [])))
        metrics["ik_count"] = float(len(skeleton.get("ik", [])))

        if len(bone_map) < 6:
            issues.append("Bone count is too low")
            level = QualityLevel.FAIL

        if "root" not in bone_map or "body" not in bone_map:
            issues.append("Required base bones are missing")
            level = QualityLevel.FAIL

        bone_length_variance = QualityGate._compute_bone_length_variance(bone_map)
        metrics["bone_length_variance"] = bone_length_variance
        if bone_length_variance > QualityGate.bone_length_variance_threshold:
            issues.append("Bone length variance exceeds threshold")
            level = QualityLevel.FAIL
        elif bone_length_variance > QualityGate.bone_length_variance_threshold * 0.5 and level != QualityLevel.FAIL:
            issues.append("Bone length variance is high")
            level = QualityLevel.WARN

        symmetry_error = QualityGate._compute_symmetry_error(bone_map)
        metrics["symmetry_error"] = symmetry_error
        if symmetry_error > QualityGate.symmetry_error_threshold:
            issues.append("Bone symmetry error exceeds threshold")
            level = QualityLevel.FAIL
        elif symmetry_error > QualityGate.symmetry_error_threshold * 0.5 and level != QualityLevel.FAIL:
            issues.append("Bone symmetry error is elevated")
            level = QualityLevel.WARN

        if metrics["ik_count"] < 1 and level == QualityLevel.PASS:
            issues.append("No IK constraints found")
            level = QualityLevel.WARN

        return QualityGateResult(stage="rigging", level=level, metrics=metrics, issues=issues)

    @staticmethod
    def check_animation(skeleton: Optional[Dict[str, Any]]) -> QualityGateResult:
        metrics: Dict[str, float] = {}
        issues: List[str] = []

        if not isinstance(skeleton, dict):
            return QualityGateResult(
                stage="animation",
                level=QualityLevel.FAIL,
                metrics=metrics,
                issues=["Skeleton payload is missing"],
            )

        animations = skeleton.get("animations", {})
        if not isinstance(animations, dict) or not animations:
            return QualityGateResult(
                stage="animation",
                level=QualityLevel.FAIL,
                metrics={"animation_count": 0.0, "keyframe_count": 0.0},
                issues=["No animations found"],
            )

        keyframe_count = float(QualityGate._count_keyframes(animations))
        animation_count = float(len(animations))
        metrics["animation_count"] = animation_count
        metrics["keyframe_count"] = keyframe_count

        if keyframe_count <= 0:
            return QualityGateResult(
                stage="animation",
                level=QualityLevel.FAIL,
                metrics=metrics,
                issues=["Animations exist but keyframes are empty"],
            )

        if keyframe_count < 8:
            issues.append("Animation keyframe count is low")
            return QualityGateResult(stage="animation", level=QualityLevel.WARN, metrics=metrics, issues=issues)

        return QualityGateResult(stage="animation", level=QualityLevel.PASS, metrics=metrics, issues=issues)

    @staticmethod
    def overall_gate(
        parts_metadata: Optional[Dict[str, Any]],
        skeleton: Optional[Dict[str, Any]],
        parts_dir: Optional[Path] = None,
    ) -> QualityGateResult:
        segmentation = QualityGate.check_segmentation(parts_metadata, parts_dir=parts_dir)
        rigging = QualityGate.check_rigging(skeleton)
        animation = QualityGate.check_animation(skeleton)

        stage_results = [segmentation, rigging, animation]
        severity_order = {
            QualityLevel.PASS: 0,
            QualityLevel.WARN: 1,
            QualityLevel.FAIL: 2,
        }

        overall_level = max(stage_results, key=lambda result: severity_order[result.level]).level
        combined_metrics: Dict[str, float] = {}
        combined_issues: List[str] = []
        for result in stage_results:
            for key, value in result.metrics.items():
                combined_metrics[f"{result.stage}_{key}"] = value
            for issue in result.issues:
                combined_issues.append(f"{result.stage}: {issue}")

        return QualityGateResult(
            stage="overall",
            level=overall_level,
            metrics=combined_metrics,
            issues=combined_issues,
        )

    @staticmethod
    def _compute_alpha_noise(parts: List[Dict[str, Any]], parts_dir: Optional[Path]) -> Optional[float]:
        if parts_dir is None or not parts_dir.exists():
            return None

        ratios: List[float] = []
        for part in parts:
            file_name = part.get("file")
            if not file_name:
                continue

            part_path = parts_dir / str(file_name)
            ratio = QualityGate._alpha_noise_for_part(part_path)
            if ratio is not None:
                ratios.append(ratio)

        if not ratios:
            return None

        return sum(ratios) / float(len(ratios))

    @staticmethod
    def _alpha_noise_for_part(part_path: Path) -> Optional[float]:
        if not part_path.exists() or part_path.suffix.lower() != ".png":
            return None

        try:
            import numpy as np
            from PIL import Image

            with Image.open(part_path) as image:
                if "A" not in image.getbands():
                    return None
                alpha = np.array(image.getchannel("A"))

            foreground = alpha > 0
            foreground_pixels = int(foreground.sum())
            if foreground_pixels <= 0:
                return 1.0

            noisy_pixels = int(((alpha > 0) & (alpha < 16)).sum())
            return float(noisy_pixels) / float(foreground_pixels)
        except Exception:
            return None

    @staticmethod
    def _compute_bone_length_variance(bone_map: Dict[str, Dict[str, Any]]) -> float:
        mirrored_deltas: List[float] = []
        for bone_name, left_bone in bone_map.items():
            if not bone_name.endswith("_L"):
                continue

            right_name = f"{bone_name[:-2]}_R"
            right_bone = bone_map.get(right_name)
            if not right_bone:
                continue

            left_length = float(left_bone.get("length", 0) or 0)
            right_length = float(right_bone.get("length", 0) or 0)
            if left_length <= 0 or right_length <= 0:
                continue

            mirrored_deltas.append(abs(left_length - right_length) / max(left_length, right_length))

        if not mirrored_deltas:
            return 0.0

        return sum(mirrored_deltas) / float(len(mirrored_deltas))

    @staticmethod
    def _compute_symmetry_error(bone_map: Dict[str, Dict[str, Any]]) -> float:
        errors: List[float] = []
        for bone_name, left_bone in bone_map.items():
            if not bone_name.endswith("_L"):
                continue

            right_name = f"{bone_name[:-2]}_R"
            right_bone = bone_map.get(right_name)
            if not right_bone:
                continue

            left_x = float(left_bone.get("x", 0) or 0)
            right_x = float(right_bone.get("x", 0) or 0)
            denom = max(abs(left_x), abs(right_x), 1.0)
            errors.append(abs(abs(left_x) - abs(right_x)) / denom)

        if not errors:
            return 0.0

        return sum(errors) / float(len(errors))

    @staticmethod
    def _count_keyframes(animations: Dict[str, Any]) -> int:
        count = 0
        for animation_data in animations.values():
            if not isinstance(animation_data, dict):
                continue
            for track_data in animation_data.values():
                count += QualityGate._count_nested_frames(track_data)
        return count

    @staticmethod
    def _count_nested_frames(track_data: Any) -> int:
        if isinstance(track_data, list):
            return len(track_data)
        if isinstance(track_data, dict):
            nested_count = 0
            for value in track_data.values():
                nested_count += QualityGate._count_nested_frames(value)
            return nested_count
        return 0
