"""Tests for scripts/generate_atlas.py — atlas generation from individual PNGs."""

import json

import pytest
from PIL import Image

from generate_atlas import (
    find_character_dirs,
    find_pngs,
    generate_atlas_content,
    generate_atlas_for_character,
    main,
    parse_args,
    run_batch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_png(path, width: int = 100, height: int = 50) -> None:
    """Create a small RGBA PNG at the given path."""
    Image.new("RGBA", (width, height), (255, 128, 0, 255)).save(path)


def _create_spine_dir(base_dir, char_name: str, part_names: list[str]) -> dict:
    """Create a spine directory structure with PNGs and skeleton.json.

    Returns dict with paths for further assertions.
    """
    char_dir = base_dir / char_name
    spine_dir = char_dir / "spine"
    spine_dir.mkdir(parents=True)

    # Create skeleton.json
    skeleton = {"bones": [{"name": "root"}], "animations": {"idle": {}}}
    (spine_dir / "skeleton.json").write_text(
        json.dumps(skeleton), encoding="utf-8"
    )

    # Create part PNGs with varying sizes
    sizes = {
        "head": (64, 80),
        "body": (80, 120),
        "arm_L": (30, 60),
        "arm_R": (30, 60),
        "leg_L": (35, 70),
        "leg_R": (35, 70),
        "weapon": (20, 50),
    }
    for name in part_names:
        w, h = sizes.get(name, (100, 50))
        _create_test_png(spine_dir / f"{name}.png", w, h)

    return {"char_dir": char_dir, "spine_dir": spine_dir}


# ---------------------------------------------------------------------------
# find_pngs
# ---------------------------------------------------------------------------

class TestFindPngs:
    def test_finds_pngs_sorted_alphabetically(self, tmp_path):
        # Arrange
        _create_test_png(tmp_path / "body.png")
        _create_test_png(tmp_path / "arm_L.png")
        _create_test_png(tmp_path / "head.png")

        # Act
        result = find_pngs(tmp_path)

        # Assert
        names = [p.name for p in result]
        assert names == ["arm_L.png", "body.png", "head.png"]

    def test_returns_empty_for_no_pngs(self, tmp_path):
        # Arrange — empty dir
        # Act
        result = find_pngs(tmp_path)

        # Assert
        assert result == []

    def test_ignores_non_png_files(self, tmp_path):
        # Arrange
        _create_test_png(tmp_path / "body.png")
        (tmp_path / "skeleton.json").write_text("{}", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("hi", encoding="utf-8")

        # Act
        result = find_pngs(tmp_path)

        # Assert
        assert len(result) == 1
        assert result[0].name == "body.png"


# ---------------------------------------------------------------------------
# generate_atlas_content
# ---------------------------------------------------------------------------

class TestGenerateAtlasContent:
    def test_single_png_produces_correct_format(self, tmp_path):
        # Arrange
        png_path = tmp_path / "head.png"
        _create_test_png(png_path, width=64, height=80)

        # Act
        content = generate_atlas_content([png_path])

        # Assert
        expected = (
            "head.png\n"
            "size: 64,80\n"
            "format: RGBA8888\n"
            "filter: Linear,Linear\n"
            "repeat: none\n"
            "head\n"
            "  rotate: false\n"
            "  xy: 0, 0\n"
            "  size: 64, 80\n"
            "  orig: 64, 80\n"
            "  offset: 0, 0\n"
            "  index: -1\n"
            "\n"
        )
        assert content == expected

    def test_multiple_pngs_separated_by_blank_line(self, tmp_path):
        # Arrange
        png_a = tmp_path / "arm.png"
        png_b = tmp_path / "body.png"
        _create_test_png(png_a, 30, 60)
        _create_test_png(png_b, 80, 120)

        # Act
        content = generate_atlas_content([png_a, png_b])

        # Assert — each page ends with newline, blank line separates pages
        pages = content.strip().split("\n\n")
        assert len(pages) == 2
        assert pages[0].startswith("arm.png")
        assert pages[1].startswith("body.png")

    def test_correct_dimensions_from_real_png(self, tmp_path):
        # Arrange — use non-square dimensions
        png_path = tmp_path / "weapon.png"
        _create_test_png(png_path, width=20, height=50)

        # Act
        content = generate_atlas_content([png_path])

        # Assert
        assert "size: 20,50" in content
        assert "size: 20, 50" in content
        assert "orig: 20, 50" in content

    def test_raises_on_empty_list(self):
        # Arrange / Act / Assert
        with pytest.raises(ValueError, match="No PNG files"):
            generate_atlas_content([])


# ---------------------------------------------------------------------------
# generate_atlas_for_character — single char mode
# ---------------------------------------------------------------------------

class TestGenerateAtlasForCharacter:
    def test_creates_atlas_file(self, tmp_path):
        # Arrange
        info = _create_spine_dir(tmp_path, "hero", ["head", "body", "weapon"])

        # Act
        result = generate_atlas_for_character(info["spine_dir"], "hero")

        # Assert
        assert result is not None
        atlas_path = info["spine_dir"] / "hero.atlas"
        assert atlas_path.exists()
        content = atlas_path.read_text(encoding="utf-8")
        assert "body.png" in content
        assert "head.png" in content
        assert "weapon.png" in content

    def test_dry_run_does_not_write_file(self, tmp_path):
        # Arrange
        info = _create_spine_dir(tmp_path, "hero", ["head", "body"])

        # Act
        result = generate_atlas_for_character(
            info["spine_dir"], "hero", dry_run=True
        )

        # Assert
        assert result is not None  # returns path (planned)
        atlas_path = info["spine_dir"] / "hero.atlas"
        assert not atlas_path.exists()

    def test_skips_existing_atlas_without_overwrite(self, tmp_path):
        # Arrange
        info = _create_spine_dir(tmp_path, "hero", ["head", "body"])
        atlas_path = info["spine_dir"] / "hero.atlas"
        atlas_path.write_text("existing", encoding="utf-8")

        # Act
        result = generate_atlas_for_character(info["spine_dir"], "hero")

        # Assert
        assert result is None  # skipped
        assert atlas_path.read_text(encoding="utf-8") == "existing"

    def test_overwrites_existing_atlas_with_flag(self, tmp_path):
        # Arrange
        info = _create_spine_dir(tmp_path, "hero", ["head", "body"])
        atlas_path = info["spine_dir"] / "hero.atlas"
        atlas_path.write_text("old content", encoding="utf-8")

        # Act
        result = generate_atlas_for_character(
            info["spine_dir"], "hero", overwrite=True
        )

        # Assert
        assert result is not None
        content = atlas_path.read_text(encoding="utf-8")
        assert content != "old content"
        assert "head.png" in content

    def test_returns_none_for_empty_directory(self, tmp_path):
        # Arrange — dir with no PNGs
        spine_dir = tmp_path / "empty_char" / "spine"
        spine_dir.mkdir(parents=True)

        # Act
        result = generate_atlas_for_character(spine_dir, "empty_char")

        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------

class TestBatchMode:
    def test_finds_all_characters_with_skeleton_json(self, tmp_path):
        # Arrange
        _create_spine_dir(tmp_path, "warrior", ["head", "body"])
        _create_spine_dir(tmp_path, "mage", ["head", "body", "weapon"])

        # Also create a dir WITHOUT skeleton.json — should be ignored
        no_spine = tmp_path / "incomplete" / "spine"
        no_spine.mkdir(parents=True)

        # Act
        char_dirs = find_character_dirs(tmp_path)

        # Assert
        names = [name for _, name in char_dirs]
        assert "warrior" in names
        assert "mage" in names
        assert "incomplete" not in names

    def test_batch_processes_all_characters(self, tmp_path):
        # Arrange
        _create_spine_dir(tmp_path, "warrior", ["head", "body"])
        _create_spine_dir(tmp_path, "mage", ["head", "body"])

        # Act
        processed, skipped, failed = run_batch(
            tmp_path, dry_run=False, overwrite=True
        )

        # Assert
        assert processed == 2
        assert skipped == 0
        assert failed == 0
        assert (tmp_path / "warrior" / "spine" / "warrior.atlas").exists()
        assert (tmp_path / "mage" / "spine" / "mage.atlas").exists()

    def test_batch_dry_run_no_files_written(self, tmp_path):
        # Arrange
        _create_spine_dir(tmp_path, "warrior", ["head", "body"])

        # Act
        processed, skipped, failed = run_batch(tmp_path, dry_run=True)

        # Assert
        assert processed == 1
        assert not (tmp_path / "warrior" / "spine" / "warrior.atlas").exists()

    def test_batch_returns_zero_for_empty_dir(self, tmp_path):
        # Arrange — empty directory
        # Act
        processed, skipped, failed = run_batch(tmp_path)

        # Assert
        assert processed == 0
        assert skipped == 0
        assert failed == 0


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestParseArgs:
    def test_single_mode_requires_input_dir_and_char_name(self):
        # Arrange / Act / Assert
        with pytest.raises(SystemExit):
            parse_args(["--input-dir", "some/dir"])

    def test_batch_mode_requires_output_dir(self):
        # Arrange / Act / Assert
        with pytest.raises(SystemExit):
            parse_args(["--batch"])

    def test_valid_single_mode(self):
        # Arrange / Act
        args = parse_args(["--input-dir", "path/to/spine", "--char-name", "hero"])

        # Assert
        assert args.char_name == "hero"
        assert not args.batch
        assert not args.dry_run

    def test_valid_batch_mode(self):
        # Arrange / Act
        args = parse_args(["--batch", "--output-dir", "path/to/output", "--dry-run"])

        # Assert
        assert args.batch is True
        assert args.dry_run is True


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_single_char_returns_zero(self, tmp_path):
        # Arrange
        info = _create_spine_dir(tmp_path, "hero", ["head", "body"])

        # Act
        exit_code = main([
            "--input-dir", str(info["spine_dir"]),
            "--char-name", "hero",
        ])

        # Assert
        assert exit_code == 0
        assert (info["spine_dir"] / "hero.atlas").exists()

    def test_main_batch_returns_zero(self, tmp_path):
        # Arrange
        _create_spine_dir(tmp_path, "a", ["head"])
        _create_spine_dir(tmp_path, "b", ["body"])

        # Act
        exit_code = main([
            "--batch",
            "--output-dir", str(tmp_path),
            "--overwrite",
        ])

        # Assert
        assert exit_code == 0
