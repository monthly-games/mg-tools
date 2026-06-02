#!/usr/bin/env python3
"""Import See-through/Stretchy layer assets as pipeline-compatible parts.

This adapter consumes plain PNG layers plus optional JSON metadata. It can also
read PSD files when the optional psd-tools package is installed. The output
matches the existing split_parts contract:

    parts/
      metadata.json
      head.png
      body.png
      arm_L.png
      ...

Usage:
    python scripts/import_see_through_layers.py \
        --input output/see_through_layers \
        --output output/hero/parts \
        --source images/hero.png \
        --overwrite

    python scripts/import_see_through_layers.py \
        --input output/see_through_model.psd \
        --output output/hero/parts \
        --overwrite
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image


logger = logging.getLogger(__name__)

BBox = Tuple[int, int, int, int]


def _slug_tokens(value: str) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def _safe_slug(value: str) -> str:
    tokens = _slug_tokens(value)
    return "_".join(tokens) if tokens else "part"


def _detect_side(tokens: Sequence[str]) -> Optional[str]:
    left_markers = {"l", "left", "lt", "lhs"}
    right_markers = {"r", "right", "rt", "rhs"}

    if any(token in left_markers for token in tokens):
        return "L"
    if any(token in right_markers for token in tokens):
        return "R"
    return None


def _with_side(base: str, side: Optional[str]) -> str:
    return f"{base}_{side}" if side else base


def normalize_layer_name(raw_name: str) -> str:
    """Map external layer names to names understood by rig_character.py.

    The importer keeps the current rigging contract stable by normalizing common
    See-through/Stretchy layer names to existing part names such as head, body,
    arm_L, arm_R, leg_L, and leg_R. Unknown semantic parts are preserved as safe
    snake_case names so they can still be emitted and manually mapped later.
    """
    raw_name = Path(str(raw_name)).stem
    tokens = _slug_tokens(raw_name)
    token_set = set(tokens)
    side = _detect_side(tokens)

    if not tokens:
        return "part"

    if "hair" in token_set and "front" in token_set:
        return "hair_front"
    if "hair" in token_set and "back" in token_set:
        return "hair_back"
    if "hair" in token_set:
        return _with_side("hair", side)

    if token_set & {"arm", "hand", "forearm", "elbow", "sleeve"}:
        return _with_side("arm", side)

    if token_set & {"leg", "foot", "thigh", "knee", "boot"}:
        return _with_side("leg", side)

    if token_set & {"head", "face"}:
        return "head"

    if token_set & {"body", "torso", "chest", "clothes", "clothing", "dress", "outfit", "robe", "armor"}:
        return "body"

    if token_set & {"weapon", "sword", "staff", "bow", "gun", "blade", "wand"}:
        return "weapon"

    if "shield" in token_set:
        return "shield"

    if token_set & {"cape", "cloak"}:
        return "cape"

    for base in ("eye", "brow", "mouth", "ear", "horn", "tail", "wing"):
        if base in token_set or f"{base}s" in token_set:
            return _with_side(base, side)

    return _safe_slug(raw_name)


def alpha_bbox(image: Image.Image) -> Optional[BBox]:
    """Return the visible alpha bounds as (left, top, right, bottom)."""
    if "A" not in image.getbands():
        return (0, 0, image.width, image.height)

    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return None
    return tuple(int(value) for value in bbox)  # type: ignore[return-value]


def alpha_coverage(image: Image.Image, box: BBox) -> float:
    """Return visible alpha pixel ratio inside a bounding box."""
    left, top, right, bottom = box
    width = max(0, right - left)
    height = max(0, bottom - top)
    area = width * height
    if area == 0:
        return 0.0

    crop = image.crop(box)
    if "A" not in crop.getbands():
        return 1.0

    alpha = crop.getchannel("A")
    visible = sum(1 for value in alpha.getdata() if int(value) > 0)
    return float(visible) / float(area)


def _clamp_box(box: Sequence[Any], image: Image.Image) -> Optional[BBox]:
    if len(box) != 4:
        return None

    try:
        left, top, right, bottom = (int(round(float(value))) for value in box)
    except (TypeError, ValueError):
        return None

    left = max(0, min(left, image.width))
    top = max(0, min(top, image.height))
    right = max(left, min(right, image.width))
    bottom = max(top, min(bottom, image.height))

    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)


def _coerce_bounds(value: Any) -> Optional[List[int]]:
    if isinstance(value, dict):
        try:
            x = int(round(float(value.get("x", value.get("left", 0)))))
            y = int(round(float(value.get("y", value.get("top", 0)))))
            if "width" in value and "height" in value:
                return [x, y, x + int(round(float(value["width"]))), y + int(round(float(value["height"])))]
            return [
                x,
                y,
                int(round(float(value.get("right")))),
                int(round(float(value.get("bottom")))),
            ]
        except (TypeError, ValueError):
            return None

    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            return [int(round(float(item))) for item in value]
        except (TypeError, ValueError):
            return None

    return None


def _load_external_layers(metadata_path: Optional[Path]) -> List[Dict[str, Any]]:
    if metadata_path is None:
        return []

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        layers = payload
    elif isinstance(payload, dict):
        layers = payload.get("layers") or payload.get("parts") or []
    else:
        layers = []

    return [layer for layer in layers if isinstance(layer, dict)]


def _layer_file_from_entry(entry: Dict[str, Any]) -> Optional[str]:
    for key in ("file", "filename", "path", "image", "source"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _layer_name_from_entry(entry: Dict[str, Any], fallback_file: Path) -> str:
    for key in ("name", "layer_name", "label", "part"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback_file.stem


def _metadata_bounds_from_entry(entry: Dict[str, Any]) -> Optional[List[int]]:
    for key in ("bounds", "bbox", "region"):
        bounds = _coerce_bounds(entry.get(key))
        if bounds:
            return bounds
    return None


def _resolve_layer_path(input_dir: Path, layer_file: str) -> Path:
    layer_path = Path(layer_file)
    if layer_path.is_absolute():
        return layer_path
    return input_dir / layer_path


def _is_psd_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".psd"


def _psd_layer_children(layer: Any) -> List[Any]:
    try:
        return list(layer)
    except TypeError:
        return []


def _iter_psd_leaf_layers(layer: Any) -> List[Any]:
    children = _psd_layer_children(layer)
    if not children:
        return [layer]

    leaves: List[Any] = []
    for child in children:
        leaves.extend(_iter_psd_leaf_layers(child))
    return leaves


def _is_visible_psd_layer(layer: Any) -> bool:
    is_visible = getattr(layer, "is_visible", None)
    if callable(is_visible):
        try:
            return bool(is_visible())
        except TypeError:
            pass

    visible = getattr(layer, "visible", True)
    return bool(visible)


def _psd_layer_bounds(layer: Any, image: Image.Image) -> BBox:
    bbox = getattr(layer, "bbox", None)
    if bbox is not None:
        if all(hasattr(bbox, attr) for attr in ("x1", "y1", "x2", "y2")):
            return (int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2))
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return tuple(int(value) for value in bbox)  # type: ignore[return-value]

    attrs = ("left", "top", "right", "bottom")
    if all(hasattr(layer, attr) for attr in attrs):
        return (
            int(getattr(layer, "left")),
            int(getattr(layer, "top")),
            int(getattr(layer, "right")),
            int(getattr(layer, "bottom")),
        )

    return (0, 0, int(image.width), int(image.height))


def _psd_layer_image(layer: Any) -> Optional[Image.Image]:
    for method_name in ("composite", "topil"):
        method = getattr(layer, method_name, None)
        if not callable(method):
            continue
        image = method()
        if image is not None:
            return image.convert("RGBA")
    return None


def _psd_layer_as_canvas(layer: Any, canvas_size: Tuple[int, int]) -> Optional[Tuple[Image.Image, BBox]]:
    layer_image = _psd_layer_image(layer)
    if layer_image is None:
        return None

    bounds = _psd_layer_bounds(layer, layer_image)
    if layer_image.size == canvas_size:
        return layer_image, bounds

    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    paste_mask = layer_image if "A" in layer_image.getbands() else None
    canvas.paste(layer_image, (bounds[0], bounds[1]), paste_mask)
    return canvas, bounds


def _iter_psd_layer_entries(psd_path: Path) -> List[Dict[str, Any]]:
    try:
        psd_tools = importlib.import_module("psd_tools")
    except ImportError as exc:
        raise RuntimeError(
            "PSD import requires psd-tools. Install with: pip install psd-tools"
        ) from exc

    psd_image = psd_tools.PSDImage.open(psd_path)
    canvas_size = (int(psd_image.width), int(psd_image.height))
    entries: List[Dict[str, Any]] = []

    for layer in _iter_psd_leaf_layers(psd_image):
        if not _is_visible_psd_layer(layer):
            continue

        result = _psd_layer_as_canvas(layer, canvas_size)
        if result is None:
            continue

        image, bounds = result
        entries.append(
            {
                "path": psd_path,
                "name": str(getattr(layer, "name", psd_path.stem)),
                "bounds": list(bounds),
                "image": image,
                "source_file": psd_path.name,
            }
        )

    return entries


def _iter_layer_entries(input_dir: Path, metadata_path: Optional[Path]) -> List[Dict[str, Any]]:
    metadata_layers = _load_external_layers(metadata_path)
    entries: List[Dict[str, Any]] = []
    consumed: set[Path] = set()

    for layer in metadata_layers:
        layer_file = _layer_file_from_entry(layer)
        if not layer_file:
            continue
        layer_path = _resolve_layer_path(input_dir, layer_file)
        entries.append(
            {
                "path": layer_path,
                "name": _layer_name_from_entry(layer, layer_path),
                "bounds": _metadata_bounds_from_entry(layer),
            }
        )
        consumed.add(layer_path.resolve())

    for png_path in sorted(input_dir.glob("*.png"), key=lambda path: path.name.lower()):
        if png_path.resolve() in consumed:
            continue
        entries.append({"path": png_path, "name": png_path.stem, "bounds": None})

    return entries


def _unique_name(base_name: str, seen: Dict[str, int]) -> str:
    count = seen.get(base_name, 0) + 1
    seen[base_name] = count
    if count == 1:
        return base_name
    return f"{base_name}_{count}"


def _prepare_output_dir(output_dir: Path, overwrite: bool, dry_run: bool) -> None:
    if dry_run:
        return

    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Output directory already exists: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)


def _source_image_size(source: Optional[str]) -> Optional[List[int]]:
    if not source:
        return None

    source_path = Path(source)
    if not source_path.exists():
        return None

    try:
        with Image.open(source_path) as image:
            return [int(image.width), int(image.height)]
    except Exception:
        return None


def import_layers(
    input_dir: Path | str,
    output_dir: Path | str,
    *,
    source: Optional[str] = None,
    metadata_path: Optional[Path | str] = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Convert layer PNGs or a PSD file into the parts/metadata.json contract."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    metadata_input = Path(metadata_path) if metadata_path is not None else None
    is_psd = _is_psd_file(input_path)

    if not is_psd and not input_path.is_dir():
        raise FileNotFoundError(f"Input layer directory or PSD file does not exist: {input_path}")
    if metadata_input is not None and not metadata_input.exists():
        raise FileNotFoundError(f"Layer metadata does not exist: {metadata_input}")

    entries = _iter_psd_layer_entries(input_path) if is_psd else _iter_layer_entries(input_path, metadata_input)
    if not entries:
        raise ValueError(f"No importable layers found in {input_path}")

    _prepare_output_dir(output_path, overwrite=overwrite, dry_run=dry_run)

    parts: List[Dict[str, Any]] = []
    seen_names: Dict[str, int] = {}
    max_width = 0
    max_height = 0

    for draw_order, entry in enumerate(entries):
        layer_path = Path(entry["path"]) if entry.get("path") else None
        entry_image = entry.get("image")

        if isinstance(entry_image, Image.Image):
            image = entry_image.convert("RGBA")
        else:
            if layer_path is None or layer_path.suffix.lower() != ".png" or not layer_path.exists():
                logger.warning("Skipping missing or non-PNG layer: %s", layer_path)
                continue
            with Image.open(layer_path) as opened:
                image = opened.convert("RGBA")

        max_width = max(max_width, image.width)
        max_height = max(max_height, image.height)

        raw_bounds = entry.get("bounds")
        box = _clamp_box(raw_bounds, image) if raw_bounds else alpha_bbox(image)
        if box is None:
            logger.warning("Skipping fully transparent layer: %s", layer_path or entry.get("name"))
            continue

        fallback_name = layer_path.stem if layer_path is not None else "part"
        base_name = normalize_layer_name(str(entry.get("name") or fallback_name))
        part_name = _unique_name(base_name, seen_names)
        out_file = f"{part_name}.png"
        crop = image.crop(box)

        if not dry_run:
            crop.save(output_path / out_file)

        source_file = str(entry.get("source_file") or (layer_path.name if layer_path is not None else input_path.name))
        region = [int(value) for value in box]
        coverage = alpha_coverage(image, box)
        parts.append(
            {
                "name": part_name,
                "file": out_file,
                "region": region,
                "bbox": region,
                "alpha_coverage": coverage,
                "confidence": 0.95,
                "source_layer": str(entry.get("name") or fallback_name),
                "source_file": source_file,
                "draw_order": draw_order,
                "size": [int(crop.width), int(crop.height)],
            }
        )

    if not parts:
        raise ValueError(f"No visible layers found in {input_path}")

    effective_source = source if source is not None else (str(input_path) if is_psd else None)
    image_size = _source_image_size(effective_source) or [max_width, max_height]
    metadata = {
        "source": effective_source,
        "method": "see-through-psd-import" if is_psd else "see-through-layer-import",
        "image_size": image_size,
        "parts": parts,
    }

    if not dry_run:
        (output_path / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return metadata


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import See-through/Stretchy PNG layers or PSD files into spine-ai-pipeline parts.",
    )
    parser.add_argument("--input", required=True, help="Directory containing transparent PNG layers, or a PSD file")
    parser.add_argument("--output", required=True, help="Output parts directory")
    parser.add_argument("--source", help="Original source image path to store in metadata")
    parser.add_argument("--metadata", help="Optional See-through/Stretchy layer metadata JSON")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output directory")
    parser.add_argument("--dry-run", action="store_true", help="Print planned metadata without writing files")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    metadata = import_layers(
        args.input,
        args.output,
        source=args.source,
        metadata_path=args.metadata,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    print(
        json.dumps(
            {
                "output": args.output,
                "parts": len(metadata["parts"]),
                "method": metadata["method"],
                "dry_run": bool(args.dry_run),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
