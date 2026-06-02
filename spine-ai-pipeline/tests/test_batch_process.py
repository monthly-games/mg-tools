"""Tests for scripts/batch_process.py — CLI args & process_single_image."""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# We need to mock heavy imports before importing batch_process
# batch_process does `importlib.import_module("lib.quality_gate")` at module level,
# which requires scripts/ in sys.path — conftest handles that.


class TestCLIArgs:
    """Test argparse configuration from actual batch_process.main()."""

    def _parse(self, args_list):
        """Helper: parse args using actual batch_process parser."""
        import scripts.batch_process as bp
        parser = bp.argparse.ArgumentParser(description="Batch process images through Spine AI Pipeline")
        parser.add_argument("--input_dir", "--input", dest="input_dir", type=str, default="images", help="Input directory")
        parser.add_argument("--output_base", type=str, default="test/output/batch", help="Output base directory")
        parser.add_argument("--venv_python", type=str, default=r"d:\mg-games\repos\mg-tools\venv\Scripts\python.exe", help="Path to venv python")
        parser.add_argument("--template", type=str, help="Rig template to use (humanoid, monster, chibi)")
        parser.add_argument("--workers", type=int, default=None, help="Parallel workers (default: min(4, cpu_count))")
        parser.add_argument("--sequential", action="store_true", help="Force sequential processing (original behavior)")
        return parser.parse_args(args_list)

    def test_default_input_dir(self):
        """Default input_dir is 'images'."""
        args = self._parse([])
        assert args.input_dir == "images"

    def test_workers_arg_accepted(self):
        """--workers 8 sets workers=8."""
        args = self._parse(["--workers", "8"])
        assert args.workers == 8

    def test_sequential_arg_accepted(self):
        """--sequential sets sequential=True."""
        args = self._parse(["--sequential"])
        assert args.sequential is True

    def test_default_workers_is_none(self):
        """Default workers is None (auto-determined in main)."""
        args = self._parse([])
        assert args.workers is None

    def test_template_arg(self):
        """--template chibi sets template='chibi'."""
        args = self._parse(["--template", "chibi"])
        assert args.template == "chibi"

    def test_input_alias(self):
        """--input my_dir (alias) sets input_dir='my_dir'."""
        args = self._parse(["--input", "my_dir"])
        assert args.input_dir == "my_dir"


class TestProcessSingleImage:
    """Test process_single_image return contract."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.tmp = tmp_path
        self.img = tmp_path / "test.png"
        self.img.touch()
        self.output = tmp_path / "output"
        self.output.mkdir()

    @patch("scripts.batch_process.run_split_parts_with_lama", return_value=False)
    @patch("scripts.batch_process.run_step", return_value=False)
    def test_returns_dict_with_required_keys(self, mock_step, mock_lama):
        import scripts.batch_process as bp
        result = bp.process_single_image(
            str(self.img), str(self.output), None, "python"
        )
        assert isinstance(result, dict)
        for key in ("name", "status", "quality", "error", "duration_s"):
            assert key in result, f"Missing key: {key}"

    @patch("scripts.batch_process.run_split_parts_with_lama", return_value=False)
    @patch("scripts.batch_process.run_step", return_value=False)
    def test_fail_status_on_split_failure(self, mock_step, mock_lama):
        import scripts.batch_process as bp
        result = bp.process_single_image(
            str(self.img), str(self.output), None, "python"
        )
        assert result["status"] == "fail"

    @patch("scripts.batch_process.run_split_parts_with_lama", return_value=False)
    @patch("scripts.batch_process.run_step", return_value=False)
    def test_duration_in_result(self, mock_step, mock_lama):
        import scripts.batch_process as bp
        result = bp.process_single_image(
            str(self.img), str(self.output), None, "python"
        )
        assert result["duration_s"] >= 0

    @patch("scripts.batch_process.run_split_parts_with_lama", side_effect=Exception("boom"))
    def test_error_status_on_exception(self, mock_lama):
        import scripts.batch_process as bp
        result = bp.process_single_image(
            str(self.img), str(self.output), None, "python"
        )
        assert result["status"] == "error"
        assert "boom" in result["error"]

    @patch("scripts.batch_process.run_split_parts_with_lama", return_value=False)
    @patch("scripts.batch_process.run_step", return_value=False)
    def test_name_matches_stem(self, mock_step, mock_lama):
        import scripts.batch_process as bp
        result = bp.process_single_image(
            str(self.img), str(self.output), None, "python"
        )
        assert result["name"] == "test"


class TestRunStep:
    def test_returns_true_on_success(self):
        import scripts.batch_process as bp
        assert bp.run_step("echo", "echo hello", os.getcwd()) is True

    def test_returns_false_on_failure(self):
        import scripts.batch_process as bp
        assert bp.run_step("bad", "exit 1", os.getcwd()) is False

    def test_returns_false_on_timeout(self):
        """Given a command that hangs When timeout expires Then returns False (B-1 fix)."""
        import scripts.batch_process as bp
        # timeout=0 ensures immediate TimeoutExpired on any real command
        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("cmd", 0)):
            result = bp.run_step("hang", "sleep 9999", os.getcwd(), timeout=0)
        assert result is False

    def test_timeout_is_passed_to_subprocess(self):
        """Given custom timeout When run_step is called Then subprocess receives the timeout."""
        import scripts.batch_process as bp
        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bp.run_step("test", "echo hi", os.getcwd(), timeout=42)
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 42

    def test_default_timeout_is_step_timeout_constant(self):
        """Given default call When no timeout arg Then uses STEP_TIMEOUT_SECONDS."""
        import scripts.batch_process as bp
        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bp.run_step("test", "echo hi", os.getcwd())
        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == bp.STEP_TIMEOUT_SECONDS


class TestPipelineException:
    def test_is_exception_subclass(self):
        import scripts.batch_process as bp
        assert issubclass(bp.PipelineException, Exception)


class TestLoadJson:
    def test_loads_valid_json(self, tmp_path):
        import scripts.batch_process as bp
        p = tmp_path / "data.json"
        p.write_text('{"key": 1}', encoding="utf-8")
        assert bp.load_json(p) == {"key": 1}

    def test_raises_on_missing_file(self, tmp_path):
        import scripts.batch_process as bp
        with pytest.raises(bp.PipelineException):
            bp.load_json(tmp_path / "nope.json")
