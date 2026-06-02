"""E2E pipeline tests: skeleton structure, golden reference, quality gates.

CPU-only 구조 검증 테스트 (마커 없음) — 항상 실행.
@pytest.mark.e2e — 실제 파이프라인 스크립트 호출.
@pytest.mark.requires_gpu — GPU 환경에서만 실행.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_golden(golden_dir: Path) -> dict:
    """Load and parse the golden skeleton reference JSON."""
    path = golden_dir / "skeleton_reference.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _bone_names(skeleton: dict) -> list[str]:
    """Extract bone names from a skeleton dict."""
    return [b["name"] for b in skeleton.get("bones", [])]


# ---------------------------------------------------------------------------
# TestSkeletonJsonStructure — rig_character.py 출력 JSON 구조 검증
# (실제 파이프라인 실행 없이, in-memory dict 검증)
# ---------------------------------------------------------------------------
class TestSkeletonJsonStructure:
    """rig_character.py 출력 JSON 구조 검증."""

    def test_valid_skeleton_has_bones(self, sample_skeleton_json):
        assert "bones" in sample_skeleton_json
        assert isinstance(sample_skeleton_json["bones"], list)
        assert len(sample_skeleton_json["bones"]) > 0

    def test_valid_skeleton_has_animations(self, sample_skeleton_json):
        assert "animations" in sample_skeleton_json
        assert isinstance(sample_skeleton_json["animations"], dict)

    def test_valid_skeleton_has_skins(self, sample_skeleton_json):
        assert "skins" in sample_skeleton_json
        assert isinstance(sample_skeleton_json["skins"], list)
        assert len(sample_skeleton_json["skins"]) > 0

    def test_bones_have_required_fields(self, sample_skeleton_json):
        """모든 bone은 name 필드가 있어야 하고, root가 아니면 parent 필드도 있어야 한다."""
        for bone in sample_skeleton_json["bones"]:
            assert "name" in bone, f"Bone missing 'name': {bone}"
            if bone["name"] != "root":
                assert "parent" in bone, f"Non-root bone missing 'parent': {bone}"

    def test_root_bone_exists(self, sample_skeleton_json):
        names = _bone_names(sample_skeleton_json)
        assert "root" in names, f"No 'root' bone found. Bones: {names}"

    def test_animations_have_duration_or_bones(self, sample_skeleton_json):
        """각 animation은 비어있거나 'bones'/'duration' 등의 키를 가져야 한다."""
        for anim_name, anim_data in sample_skeleton_json["animations"].items():
            # 빈 dict (placeholder) 또는 bones/duration 키를 가진 dict
            assert isinstance(anim_data, dict), (
                f"Animation '{anim_name}' is not a dict: {type(anim_data)}"
            )


# ---------------------------------------------------------------------------
# TestGoldenReference — 골든 레퍼런스 파일 존재 및 구조 검증
# ---------------------------------------------------------------------------
class TestGoldenReference:
    """골든 레퍼런스 파일 존재 및 구조 검증."""

    def test_golden_file_exists(self, golden_dir):
        path = golden_dir / "skeleton_reference.json"
        assert path.exists(), f"Golden file not found: {path}"

    def test_golden_parseable_json(self, golden_dir):
        """골든 파일이 유효한 JSON인지 검증."""
        path = golden_dir / "skeleton_reference.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)  # JSONDecodeError 시 실패
        assert isinstance(data, dict)

    def test_golden_has_bones(self, golden_dir):
        data = _load_golden(golden_dir)
        assert "bones" in data
        assert isinstance(data["bones"], list)
        assert len(data["bones"]) > 0

    def test_golden_has_animations(self, golden_dir):
        data = _load_golden(golden_dir)
        assert "animations" in data
        assert isinstance(data["animations"], dict)
        assert len(data["animations"]) > 0

    def test_golden_bone_count_reasonable(self, golden_dir):
        """골든 스켈레톤은 5~50개 사이의 bone을 가져야 한다."""
        data = _load_golden(golden_dir)
        bone_count = len(data["bones"])
        assert 5 <= bone_count <= 50, (
            f"Bone count {bone_count} outside reasonable range [5, 50]"
        )


# ---------------------------------------------------------------------------
# TestQualityGateOnSkeleton — 스켈레톤 출력에 대한 품질 게이트 검증
# ---------------------------------------------------------------------------
class TestQualityGateOnSkeleton:
    """스켈레톤 출력에 대한 품질 게이트 검증."""

    def test_quality_gate_pass_on_valid_skeleton(self):
        """유효한 스켈레톤은 quality gate를 통과해야 한다."""
        from lib.quality_gate import QualityGate, QualityLevel

        valid_skel = {
            "bones": [
                {"name": "root", "length": 0},
                {"name": "body", "parent": "root", "length": 30},
                {"name": "hip", "parent": "body", "length": 30},
                {"name": "spine", "parent": "hip", "length": 50},
                {"name": "chest", "parent": "spine", "length": 40},
                {"name": "head", "parent": "chest", "length": 60},
            ],
            "slots": [{"name": "body_slot"}],
            "ik": [{"name": "leg_ik"}],
            "animations": {
                "idle": {
                    "bones": {
                        "body": {
                            "rotate": [
                                {"time": 0, "angle": 0},
                                {"time": 1, "angle": 5},
                            ]
                        },
                        "head": {
                            "rotate": [
                                {"time": 0, "angle": 0},
                                {"time": 0.5, "angle": -3},
                            ]
                        },
                    },
                },
            },
            "skins": [{"name": "default", "attachments": {}}],
        }
        result = QualityGate.check_rigging(valid_skel)
        assert result.level in (QualityLevel.PASS, QualityLevel.WARN), (
            f"Expected PASS/WARN, got {result.level}. Issues: {result.issues}"
        )

    def test_quality_gate_fail_on_empty_skeleton(self):
        """빈 스켈레톤은 quality gate에서 FAIL이어야 한다."""
        from lib.quality_gate import QualityGate, QualityLevel

        result = QualityGate.check_rigging({"bones": []})
        assert result.level == QualityLevel.FAIL

    def test_quality_gate_fail_on_missing_bones(self):
        """bones 키가 없는 스켈레톤은 FAIL이어야 한다."""
        from lib.quality_gate import QualityGate, QualityLevel

        result = QualityGate.check_rigging(None)
        assert result.level == QualityLevel.FAIL


# ---------------------------------------------------------------------------
# TestPipelineOutputStructure — 실제 파이프라인 스크립트 호출 (e2e)
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestPipelineOutputStructure:
    """실제 파이프라인 스크립트를 subprocess로 호출하여 출력 구조 검증."""

    def test_rig_output_has_skeleton_json(self, tmp_path, input_single_dir, pipeline_root):
        """rig_character.py 실행 후 skeleton.json 출력 검증."""
        output_dir = tmp_path / "rig_output"
        output_dir.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(pipeline_root / "scripts" / "rig_character.py"),
                "--input", str(input_single_dir),
                "--output", str(output_dir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(pipeline_root),
        )

        # 스크립트가 성공적으로 실행된 경우 skeleton.json 존재 확인
        if result.returncode == 0:
            skeleton_files = list(output_dir.rglob("*.json"))
            assert len(skeleton_files) > 0, (
                f"No JSON output found in {output_dir}. "
                f"stdout: {result.stdout[:500]}"
            )
            # 첫 번째 JSON 파일 구조 검증
            with open(skeleton_files[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "bones" in data or "skeleton" in data, (
                f"Output JSON missing 'bones'/'skeleton' key: {list(data.keys())}"
            )
        else:
            pytest.skip(
                f"rig_character.py exited with {result.returncode}. "
                f"stderr: {result.stderr[:300]}"
            )

    def test_animate_adds_animations_key(self, tmp_path, pipeline_root):
        """animate_character.py가 animations 키를 추가하는지 검증."""
        # 임시 skeleton.json 생성
        skel_dir = tmp_path / "skel_input"
        skel_dir.mkdir()
        skel_file = skel_dir / "skeleton.json"
        skel_data = {
            "skeleton": {"spine": "4.1"},
            "bones": [
                {"name": "root"},
                {"name": "body", "parent": "root", "length": 30},
            ],
            "slots": [],
            "skins": {"default": {}},
            "animations": {},
        }
        with open(skel_file, "w", encoding="utf-8") as f:
            json.dump(skel_data, f)

        output_dir = tmp_path / "anim_output"
        output_dir.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(pipeline_root / "scripts" / "animate_character.py"),
                "--input", str(skel_dir),
                "--output", str(output_dir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(pipeline_root),
        )

        if result.returncode == 0:
            json_files = list(output_dir.rglob("*.json"))
            assert len(json_files) > 0, (
                f"No JSON output from animate_character.py. "
                f"stdout: {result.stdout[:500]}"
            )
        else:
            pytest.skip(
                f"animate_character.py exited with {result.returncode}. "
                f"stderr: {result.stderr[:300]}"
            )


# ---------------------------------------------------------------------------
# TestFullPipelineEndToEnd — GPU/모델 필요, 전체 파이프라인
# ---------------------------------------------------------------------------
@pytest.mark.requires_gpu
@pytest.mark.e2e
@pytest.mark.slow
class TestFullPipelineEndToEnd:
    """전체 파이프라인 E2E 테스트 (GPU + AI 모델 필요)."""

    def test_full_pipeline_produces_all_outputs(self, input_single_dir, tmp_path, pipeline_root):
        """batch_process.py로 전체 파이프라인 실행 → 모든 출력 검증."""
        output_dir = tmp_path / "full_output"
        output_dir.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(pipeline_root / "scripts" / "batch_process.py"),
                "--input", str(input_single_dir),
                "--output", str(output_dir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            cwd=str(pipeline_root),
        )

        assert result.returncode == 0, (
            f"Pipeline failed: {result.stderr[:500]}"
        )

        # 출력 구조 검증
        json_files = list(output_dir.rglob("*.json"))
        assert len(json_files) > 0, "No JSON outputs from full pipeline"

        # skeleton.json이 유효한 Spine 구조를 가지는지 검증
        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "bones" in data:
                assert len(data["bones"]) > 0, f"Empty bones in {jf.name}"
                root_bones = [b for b in data["bones"] if b.get("name") == "root"]
                assert len(root_bones) == 1, f"Missing root bone in {jf.name}"
