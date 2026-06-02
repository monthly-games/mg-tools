"""Tests for importing See-through/Stretchy layer PNGs into pipeline parts."""

import json

import pytest
from PIL import Image

import import_see_through_layers as importer
from import_see_through_layers import (
    alpha_bbox,
    alpha_coverage,
    import_layers,
    normalize_layer_name,
)


def _write_rgba_layer(path, size=(64, 64), box=(10, 12, 30, 40), color=(255, 0, 0, 255)):
    """Create a transparent canvas with one solid rectangle."""
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = image.load()
    left, top, right, bottom = box
    for y in range(top, bottom):
        for x in range(left, right):
            pixels[x, y] = color
    image.save(path)


def test_normalizes_core_humanoid_layer_names():
    assert normalize_layer_name("Left Arm") == "arm_L"
    assert normalize_layer_name("right-leg") == "leg_R"
    assert normalize_layer_name("Torso") == "body"
    assert normalize_layer_name("Face") == "head"
    assert normalize_layer_name("Back Hair") == "hair_back"
    assert normalize_layer_name("front_hair") == "hair_front"


def test_alpha_bbox_and_coverage_use_visible_pixels():
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pixels = image.load()
    for y in range(4, 8):
        for x in range(2, 10):
            pixels[x, y] = (255, 128, 0, 255)

    box = alpha_bbox(image)

    assert box == (2, 4, 10, 8)
    assert alpha_coverage(image, box) == pytest.approx(1.0)


def test_import_layers_crops_alpha_and_writes_metadata(tmp_path):
    input_dir = tmp_path / "layers"
    output_dir = tmp_path / "parts"
    input_dir.mkdir()
    _write_rgba_layer(input_dir / "torso.png", box=(8, 10, 28, 42))
    _write_rgba_layer(input_dir / "left_arm.png", box=(2, 14, 12, 44))
    _write_rgba_layer(input_dir / "right_leg.png", box=(30, 36, 40, 60))

    metadata = import_layers(input_dir, output_dir, source="hero.png")

    metadata_path = output_dir / "metadata.json"
    assert metadata_path.exists()
    written = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert written == metadata
    assert metadata["source"] == "hero.png"
    assert metadata["method"] == "see-through-layer-import"

    body = next(part for part in metadata["parts"] if part["name"] == "body")
    assert body["file"] == "body.png"
    assert body["region"] == [8, 10, 28, 42]
    assert body["bbox"] == [8, 10, 28, 42]
    assert body["alpha_coverage"] == pytest.approx(1.0)
    assert body["confidence"] == pytest.approx(0.95)

    with Image.open(output_dir / "body.png") as cropped:
        assert cropped.size == (20, 32)


def test_import_layers_resolves_name_collisions(tmp_path):
    input_dir = tmp_path / "layers"
    output_dir = tmp_path / "parts"
    input_dir.mkdir()
    _write_rgba_layer(input_dir / "face.png", box=(4, 4, 20, 20))
    _write_rgba_layer(input_dir / "head.png", box=(8, 8, 28, 28))

    metadata = import_layers(input_dir, output_dir)

    names = [part["name"] for part in metadata["parts"]]
    assert names == ["head", "head_2"]
    assert (output_dir / "head.png").exists()
    assert (output_dir / "head_2.png").exists()


def test_import_layers_accepts_metadata_layer_order_and_bounds(tmp_path):
    input_dir = tmp_path / "layers"
    output_dir = tmp_path / "parts"
    input_dir.mkdir()
    _write_rgba_layer(input_dir / "z_head_layer.png", box=(4, 4, 20, 20))
    _write_rgba_layer(input_dir / "a_body_layer.png", box=(10, 20, 30, 48))

    layer_metadata = {
        "layers": [
            {"name": "Torso", "file": "a_body_layer.png", "bounds": [10, 20, 30, 48]},
            {"name": "Face", "file": "z_head_layer.png", "bbox": [4, 4, 20, 20]},
        ]
    }
    metadata_path = tmp_path / "see_through_metadata.json"
    metadata_path.write_text(json.dumps(layer_metadata), encoding="utf-8")

    metadata = import_layers(input_dir, output_dir, metadata_path=metadata_path)

    assert [part["name"] for part in metadata["parts"]] == ["body", "head"]
    assert [part["draw_order"] for part in metadata["parts"]] == [0, 1]
    assert metadata["parts"][0]["region"] == [10, 20, 30, 48]
    assert metadata["parts"][1]["region"] == [4, 4, 20, 20]


def test_import_layers_raises_when_output_exists_without_overwrite(tmp_path):
    input_dir = tmp_path / "layers"
    output_dir = tmp_path / "parts"
    input_dir.mkdir()
    output_dir.mkdir()
    _write_rgba_layer(input_dir / "torso.png")

    with pytest.raises(FileExistsError, match="already exists"):
        import_layers(input_dir, output_dir)


def test_import_layers_accepts_psd_input_with_mocked_layer_entries(tmp_path, monkeypatch):
    psd_path = tmp_path / "hero.psd"
    output_dir = tmp_path / "parts"
    psd_path.write_bytes(b"fake psd placeholder")

    body = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    body_pixels = body.load()
    for y in range(12, 40):
        for x in range(16, 36):
            body_pixels[x, y] = (255, 128, 0, 255)

    arm = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    arm_pixels = arm.load()
    for y in range(18, 44):
        for x in range(4, 14):
            arm_pixels[x, y] = (0, 128, 255, 255)

    def fake_psd_entries(path):
        assert path == psd_path
        return [
            {"name": "Torso", "image": body, "bounds": [16, 12, 36, 40], "source_file": "hero.psd"},
            {"name": "Left Arm", "image": arm, "bounds": [4, 18, 14, 44], "source_file": "hero.psd"},
        ]

    monkeypatch.setattr(importer, "_iter_psd_layer_entries", fake_psd_entries, raising=False)

    metadata = import_layers(psd_path, output_dir)

    assert metadata["source"] == str(psd_path)
    assert metadata["method"] == "see-through-psd-import"
    assert [part["name"] for part in metadata["parts"]] == ["body", "arm_L"]
    assert metadata["parts"][0]["region"] == [16, 12, 36, 40]
    assert metadata["parts"][0]["source_file"] == "hero.psd"
    assert (output_dir / "body.png").exists()
    assert (output_dir / "arm_L.png").exists()


@pytest.mark.filterwarnings("ignore:'mode' parameter is deprecated.*:DeprecationWarning")
def test_import_layers_reads_real_psd_layers(tmp_path):
    from psd_tools import PSDImage

    psd_path = tmp_path / "hero.psd"
    output_dir = tmp_path / "parts"

    psd = PSDImage.new("RGB", (64, 64), color=(0, 0, 0))
    body = Image.new("RGBA", (20, 28), (255, 128, 0, 255))
    arm = Image.new("RGBA", (10, 26), (0, 128, 255, 255))
    psd.create_pixel_layer(body, name="Torso", top=12, left=16)
    psd.create_pixel_layer(arm, name="Left Arm", top=18, left=4)
    psd.save(psd_path)

    metadata = import_layers(psd_path, output_dir)

    assert metadata["method"] == "see-through-psd-import"
    assert metadata["source"] == str(psd_path)
    assert [part["name"] for part in metadata["parts"]] == ["body", "arm_L"]
    assert metadata["parts"][0]["region"] == [16, 12, 36, 40]
    assert metadata["parts"][1]["region"] == [4, 18, 14, 44]
    assert (output_dir / "body.png").exists()
    assert (output_dir / "arm_L.png").exists()


def test_psd_import_reports_optional_dependency_when_psd_tools_missing(tmp_path, monkeypatch):
    psd_path = tmp_path / "hero.psd"
    psd_path.write_bytes(b"fake psd placeholder")

    real_import_module = importer.importlib.import_module

    def fake_import_module(name):
        if name == "psd_tools":
            raise ImportError("missing psd_tools")
        return real_import_module(name)

    monkeypatch.setattr(importer.importlib, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="pip install psd-tools"):
        importer._iter_psd_layer_entries(psd_path)
