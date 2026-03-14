#!/usr/bin/env python3
"""Generate Spine .atlas text files from individual part PNGs.

Scans a spine/ directory for PNG files, reads their dimensions,
and produces a Spine-compatible atlas file with one page per PNG.

Usage:
    # Single character
    python scripts/generate_atlas.py \\
        --input-dir output/full_batch/pipeline_output/arena_fighter/spine \\
        --char-name arena_fighter

    # Batch mode (all characters in pipeline_output)
    python scripts/generate_atlas.py \\
        --batch --output-dir output/full_batch/pipeline_output

    # Dry-run (preview only)
    python scripts/generate_atlas.py \\
        --input-dir output/full_batch/pipeline_output/arena_fighter/spine \\
        --char-name arena_fighter --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Atlas Generation
# ---------------------------------------------------------------------------

def get_png_dimensions(png_path: Path) -> Tuple[int, int]:
    """Read width and height from a PNG file using PIL.

    Returns:
        Tuple of (width, height).

    Raises:
        FileNotFoundError: If the PNG file does not exist.
        PIL.UnidentifiedImageError: If the file is not a valid image.
    """
    with Image.open(png_path) as img:
        return img.size  # (width, height)


def find_pngs(spine_dir: Path) -> List[Path]:
    """Find all .png files in a directory, sorted alphabetically.

    Args:
        spine_dir: Directory to scan for PNGs.

    Returns:
        Sorted list of PNG file paths.
    """
    pngs = sorted(spine_dir.glob("*.png"), key=lambda p: p.name)
    return pngs


def generate_atlas_content(
    png_paths: List[Path],
) -> str:
    """Generate Spine atlas text content for a list of PNGs.

    Each PNG becomes one page in the atlas with its region entry.
    Format follows Spine 4.x atlas specification.

    Args:
        png_paths: Sorted list of PNG file paths.

    Returns:
        Atlas file content as a string.

    Raises:
        ValueError: If png_paths is empty.
    """
    if not png_paths:
        raise ValueError("No PNG files provided for atlas generation")

    pages: List[str] = []
    for png_path in png_paths:
        width, height = get_png_dimensions(png_path)
        part_name = png_path.stem

        page = (
            f"{part_name}.png\n"
            f"size: {width},{height}\n"
            f"format: RGBA8888\n"
            f"filter: Linear,Linear\n"
            f"repeat: none\n"
            f"{part_name}\n"
            f"  rotate: false\n"
            f"  xy: 0, 0\n"
            f"  size: {width}, {height}\n"
            f"  orig: {width}, {height}\n"
            f"  offset: 0, 0\n"
            f"  index: -1\n"
        )
        pages.append(page)

    return "\n".join(pages) + "\n"


def generate_atlas_for_character(
    spine_dir: Path,
    char_name: str,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
) -> Optional[Path]:
    """Generate a .atlas file for a single character.

    Args:
        spine_dir: Directory containing part PNGs and skeleton.json.
        char_name: Character name used for the output filename.
        dry_run: If True, do not write the file.
        overwrite: If True, overwrite existing atlas files.

    Returns:
        Path to the generated atlas file, or None if skipped/failed.
    """
    output_path = spine_dir / f"{char_name}.atlas"

    if output_path.exists() and not overwrite:
        logger.info("SKIP %s — atlas already exists (use --overwrite)", output_path)
        return None

    pngs = find_pngs(spine_dir)
    if not pngs:
        logger.error("No PNG files found in %s", spine_dir)
        return None

    logger.info(
        "Generating atlas for '%s': %d PNGs in %s",
        char_name,
        len(pngs),
        spine_dir,
    )

    content = generate_atlas_content(pngs)

    if dry_run:
        logger.info("[DRY-RUN] Would write %s (%d bytes)", output_path, len(content))
        return output_path

    output_path.write_text(content, encoding="utf-8")
    logger.info("Wrote %s (%d bytes)", output_path, len(content))
    return output_path


# ---------------------------------------------------------------------------
# Batch Mode
# ---------------------------------------------------------------------------

def find_character_dirs(output_dir: Path) -> List[Tuple[Path, str]]:
    """Find all character directories containing spine/skeleton.json.

    Scans output_dir for subdirectories structured as:
        {char_name}/spine/skeleton.json

    Args:
        output_dir: Pipeline output directory to scan.

    Returns:
        Sorted list of (spine_dir, char_name) tuples.
    """
    results: List[Tuple[Path, str]] = []
    if not output_dir.is_dir():
        logger.error("Output directory does not exist: %s", output_dir)
        return results

    for char_dir in sorted(output_dir.iterdir()):
        if not char_dir.is_dir():
            continue
        spine_dir = char_dir / "spine"
        skeleton = spine_dir / "skeleton.json"
        if skeleton.exists():
            results.append((spine_dir, char_dir.name))

    return results


def run_batch(
    output_dir: Path,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
) -> Tuple[int, int, int]:
    """Run atlas generation for all characters in a pipeline output directory.

    Args:
        output_dir: Pipeline output directory.
        dry_run: If True, do not write files.
        overwrite: If True, overwrite existing atlas files.

    Returns:
        Tuple of (processed, skipped, failed) counts.
    """
    char_dirs = find_character_dirs(output_dir)
    if not char_dirs:
        logger.warning("No characters found in %s", output_dir)
        return (0, 0, 0)

    logger.info("Found %d characters for batch processing", len(char_dirs))

    processed = 0
    skipped = 0
    failed = 0

    for spine_dir, char_name in char_dirs:
        result = generate_atlas_for_character(
            spine_dir, char_name, dry_run=dry_run, overwrite=overwrite
        )
        if result is not None:
            processed += 1
        else:
            # Distinguish skip vs fail: if PNGs exist it was a skip, else fail
            pngs = find_pngs(spine_dir)
            if pngs:
                skipped += 1
            else:
                failed += 1

    logger.info(
        "Batch complete: %d processed, %d skipped, %d failed",
        processed,
        skipped,
        failed,
    )
    return (processed, skipped, failed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Spine .atlas files from individual part PNGs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Single character\n"
            "  python scripts/generate_atlas.py \\\n"
            "      --input-dir output/.../spine --char-name arena_fighter\n\n"
            "  # Batch mode\n"
            "  python scripts/generate_atlas.py \\\n"
            "      --batch --output-dir output/full_batch/pipeline_output\n"
        ),
    )

    # Single character mode
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="spine/ directory containing PNGs + skeleton.json (single char mode)",
    )
    parser.add_argument(
        "--char-name",
        type=str,
        help="Character name for output filename (single char mode)",
    )

    # Batch mode
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch mode: process all characters in pipeline_output directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Pipeline output directory (batch mode)",
    )

    # Common options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .atlas files (default: skip if exists)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args(argv)

    # Validation
    if args.batch:
        if not args.output_dir:
            parser.error("--output-dir is required in batch mode (--batch)")
    else:
        if not args.input_dir or not args.char_name:
            parser.error(
                "--input-dir and --char-name are required in single character mode"
            )

    return args


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for generate_atlas script.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.batch:
        processed, skipped, failed = run_batch(
            args.output_dir, dry_run=args.dry_run, overwrite=args.overwrite
        )
        if failed > 0:
            return 1
        return 0
    else:
        result = generate_atlas_for_character(
            args.input_dir,
            args.char_name,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
