"""Tests for scripts/lib/lama_client.py — LamaClient (ONNX inpainting)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# LamaClient __init__ & _load_model
# ---------------------------------------------------------------------------
class TestLamaClientInit:
    def test_default_model_path(self):
        """LamaClient stores expected default model path."""
        with patch("lib.lama_client.LamaClient._load_model"):
            from lib.lama_client import LamaClient
            client = LamaClient()
            assert "big-lama.onnx" in str(client.model_path)

    def test_session_none_when_model_missing(self):
        """Session stays None when model file does not exist and download is mocked out."""
        with patch("lib.lama_client.LamaClient._load_model"):
            from lib.lama_client import LamaClient
            client = LamaClient()
            client.session = None
            assert client.session is None

    def test_model_url_points_to_huggingface(self):
        with patch("lib.lama_client.LamaClient._load_model"):
            from lib.lama_client import LamaClient
            client = LamaClient()
            assert "huggingface.co" in client.model_url

    def test_load_model_handles_missing_onnxruntime(self):
        """If onnxruntime is not installed, session remains None."""
        with patch("lib.lama_client.LamaClient._load_model"):
            from lib.lama_client import LamaClient
            client = LamaClient()
            client.session = None
            assert client.session is None


# ---------------------------------------------------------------------------
# LamaClient.inpaint
# ---------------------------------------------------------------------------
class TestLamaInpaint:
    @pytest.fixture(autouse=True)
    def _setup_client(self, mock_onnx_session):
        with patch("lib.lama_client.LamaClient._load_model"):
            from lib.lama_client import LamaClient
            self.client = LamaClient()
            self.client.session = mock_onnx_session

    def test_inpaint_returns_numpy_array(self, small_rgb_image, small_mask):
        result = self.client.inpaint(small_rgb_image, small_mask)
        assert isinstance(result, np.ndarray)

    def test_inpaint_output_same_hw(self, small_rgb_image, small_mask):
        result = self.client.inpaint(small_rgb_image, small_mask)
        assert result.shape[:2] == small_rgb_image.shape[:2]

    def test_inpaint_returns_input_when_session_none(self, small_rgb_image, small_mask):
        # B-5 fix: session=None일 때 None 대신 원본 이미지를 반환해야 한다 (graceful fallback)
        self.client.session = None
        result = self.client.inpaint(small_rgb_image, small_mask)
        np.testing.assert_array_equal(result, small_rgb_image)

    def test_inpaint_returns_image_when_mask_empty(self, small_rgb_image):
        empty_mask = np.zeros((64, 64), dtype=np.uint8)
        result = self.client.inpaint(small_rgb_image, empty_mask)
        np.testing.assert_array_equal(result, small_rgb_image)

    def test_inpaint_calls_session_run(self, small_rgb_image, small_mask, mock_onnx_session):
        self.client.inpaint(small_rgb_image, small_mask)
        mock_onnx_session.run.assert_called_once()

    def test_inpaint_session_run_receives_correct_keys(self, small_rgb_image, small_mask, mock_onnx_session):
        self.client.inpaint(small_rgb_image, small_mask)
        call_args = mock_onnx_session.run.call_args
        feed_dict = call_args[1] if call_args[1] else call_args[0][1]
        assert "image" in feed_dict
        assert "mask" in feed_dict

    def test_inpaint_output_dtype_uint8(self, small_rgb_image, small_mask):
        result = self.client.inpaint(small_rgb_image, small_mask)
        assert result.dtype == np.uint8

    def test_inpaint_graceful_on_inference_error(self, small_rgb_image, small_mask, mock_onnx_session):
        """On inference exception, should return original image."""
        mock_onnx_session.run.side_effect = RuntimeError("ONNX error")
        result = self.client.inpaint(small_rgb_image, small_mask)
        np.testing.assert_array_equal(result, small_rgb_image)

    def test_inpaint_handles_large_mask(self):
        """Mask covering entire image (edge case: padding calculation)."""
        img = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
        mask = np.ones((128, 128), dtype=np.uint8) * 255
        result = self.client.inpaint(img, mask)
        assert isinstance(result, np.ndarray)
        assert result.shape[:2] == (128, 128)

    def test_inpaint_handles_small_corner_mask(self):
        """Mask at corner (edge case: padding exceeds image bounds)."""
        img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[0:5, 0:5] = 255
        result = self.client.inpaint(img, mask)
        assert isinstance(result, np.ndarray)

    def test_inpaint_no_padding_branch(self):
        """When mask is in center with large image, no padding needed (lines 102-103)."""
        img = np.random.randint(0, 255, (1024, 1024, 3), dtype=np.uint8)
        mask = np.zeros((1024, 1024), dtype=np.uint8)
        mask[400:600, 400:600] = 255  # center, plenty of room for padding
        result = self.client.inpaint(img, mask)
        assert isinstance(result, np.ndarray)
        assert result.shape[:2] == (1024, 1024)


# ---------------------------------------------------------------------------
# LamaClient._load_model (exercise actual code paths)
# ---------------------------------------------------------------------------
class TestLamaLoadModel:
    def test_load_model_onnxruntime_import_error(self):
        """When onnxruntime is not importable, session stays None."""
        import importlib
        import lib.lama_client as lama_mod

        # Temporarily remove onnxruntime from sys.modules to force ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "onnxruntime":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            client = object.__new__(lama_mod.LamaClient)
            client.model_url = "https://example.com/model.onnx"
            client.model_path = Path("nonexistent_model.onnx")
            client.session = None
            client._load_model()

        assert client.session is None

    def test_load_model_existing_file_session_fail(self, tmp_path):
        """When model file exists but InferenceSession fails, session stays None."""
        import lib.lama_client as lama_mod

        fake_model = tmp_path / "fake_model.onnx"
        fake_model.write_bytes(b"fake")

        mock_ort = MagicMock()
        mock_ort.InferenceSession.side_effect = RuntimeError("bad model")

        client = object.__new__(lama_mod.LamaClient)
        client.model_url = "https://example.com/model.onnx"
        client.model_path = fake_model
        client.session = None

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            client._load_model()

        assert client.session is None

    def test_load_model_existing_file_session_success(self, tmp_path):
        """When model exists and InferenceSession succeeds, session is set."""
        import lib.lama_client as lama_mod

        fake_model = tmp_path / "fake_model.onnx"
        fake_model.write_bytes(b"fake")

        mock_session = MagicMock()
        mock_ort = MagicMock()
        mock_ort.InferenceSession.return_value = mock_session

        client = object.__new__(lama_mod.LamaClient)
        client.model_url = "https://example.com/model.onnx"
        client.model_path = fake_model
        client.session = None

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            client._load_model()

        assert client.session is mock_session

    def test_load_model_download_failure(self, tmp_path):
        """When model doesn't exist and download fails, session stays None."""
        import lib.lama_client as lama_mod

        fake_model = tmp_path / "sub" / "model.onnx"  # doesn't exist

        mock_ort = MagicMock()
        mock_requests_get = MagicMock(side_effect=Exception("network error"))

        client = object.__new__(lama_mod.LamaClient)
        client.model_url = "https://example.com/model.onnx"
        client.model_path = fake_model
        client.session = None

        with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
            with patch("lib.lama_client.requests.get", mock_requests_get):
                client._load_model()

        assert client.session is None
