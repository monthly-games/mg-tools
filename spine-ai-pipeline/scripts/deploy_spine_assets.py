#!/usr/bin/env python3
"""Deploy Spine pipeline output to game repositories.

Loads character manifest from .sisyphus/evidence/character-manifest.json,
validates pipeline output, and copies Spine assets to game repos.

Usage:
    python scripts/deploy_spine_assets.py --dry-run --all
    python scripts/deploy_spine_assets.py --game-id 0001
    python scripts/deploy_spine_assets.py --force --all --report
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MANIFEST_PATH = ".sisyphus/evidence/character-manifest.json"
PIPELINE_OUTPUT_REL = "repos/mg-tools/spine-ai-pipeline/output"
GAME_REPO_PATTERN = "repos/mg-game-{game_num}/game/assets/spine/characters/{char_key}"
REQUIRED_SKELETON = "skeleton.json"
MIN_ATLAS_COUNT = 1
MIN_PNG_COUNT = 3


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class DeployResult:
    """Result of a single character deployment attempt."""

    game_id: str
    character: str
    success: bool
    files_copied: int
    source_path: str
    target_path: str
    error: Optional[str] = None


@dataclass
class DeploySummary:
    """Aggregated deployment summary."""

    games_processed: int = 0
    characters_deployed: int = 0
    characters_skipped: int = 0
    errors: int = 0
    files_copied: int = 0


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_monorepo_root() -> Path:
    """Resolve the monorepo root from the script location.

    Script: repos/mg-tools/spine-ai-pipeline/scripts/deploy_spine_assets.py
    Root:   mg-games/  (5 parents up)
    """
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def get_pipeline_output_dir(root: Path, character_key: str, pipeline_output_override: Optional[str] = None) -> Path:
    """Return the pipeline output directory for a character.

    Args:
        root: Monorepo root path.
        character_key: Character identifier (e.g. 'tower_archer').
        pipeline_output_override: If set, use this as the base directory instead of
            the default PIPELINE_OUTPUT_REL. Can be absolute or relative to root.
            Expected structure: {override}/{character_key}/spine/
    """
    if pipeline_output_override:
        base = Path(pipeline_output_override)
        if not base.is_absolute():
            base = root / base
        return base / character_key / "spine"
    return root / PIPELINE_OUTPUT_REL / character_key / "spine"


def get_game_target_dir(root: Path, game_id: str, character_key: str) -> Path:
    """Return the target asset directory inside a game repo."""
    game_num = game_id.replace("MG-", "")
    return root / GAME_REPO_PATTERN.format(game_num=game_num, char_key=character_key)


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def load_manifest(root: Path) -> Dict[str, object]:
    """Load the character manifest JSON.

    Returns:
        Parsed manifest dict with 'characters' list.

    Raises:
        FileNotFoundError: if manifest file is missing.
        json.JSONDecodeError: if manifest is malformed.
    """
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Character manifest not found: {manifest_path}\n"
            "Run the spine pipeline first to generate the manifest."
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "characters" not in data:
        raise ValueError(
            f"Manifest missing 'characters' key: {manifest_path}"
        )

    return data


def group_by_game(characters: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    """Group character entries by game_id.

    Args:
        characters: List of character dicts from manifest.

    Returns:
        Dict mapping game_id -> list of character dicts.
    """
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for char in characters:
        gid = str(char.get("game_id", "UNKNOWN"))
        grouped.setdefault(gid, []).append(char)
    return grouped


# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------

def validate_source(source_dir: Path) -> Optional[str]:
    """Validate that a pipeline output directory has required files.

    Required:
        - skeleton.json (exactly one)
        - At least 1 .atlas file
        - At least 3 .png files

    Returns:
        None if valid, error message string if invalid.
    """
    if not source_dir.exists():
        return f"Source directory does not exist: {source_dir}"

    if not source_dir.is_dir():
        return f"Source path is not a directory: {source_dir}"

    # Check skeleton (JSON or SKEL)
    has_json = (source_dir / "skeleton.json").exists()
    has_skel = (source_dir / "skeleton.skel").exists()
    if not (has_json or has_skel):
        return f"Missing skeleton (skeleton.json or .skel) in {source_dir}"

    # Check atlas files
    atlas_files = list(source_dir.glob("*.atlas"))
    if len(atlas_files) < MIN_ATLAS_COUNT:
        return (
            f"Need >= {MIN_ATLAS_COUNT} .atlas file(s), "
            f"found {len(atlas_files)} in {source_dir}"
        )

    # Check PNG files
    png_files = list(source_dir.glob("*.png"))
    if len(png_files) < MIN_PNG_COUNT:
        return (
            f"Need >= {MIN_PNG_COUNT} .png file(s), "
            f"found {len(png_files)} in {source_dir}"
        )

    return None


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

def count_files(directory: Path) -> int:
    """Count all files (non-directory) in a directory, non-recursive."""
    if not directory.exists():
        return 0
    return sum(1 for p in directory.iterdir() if p.is_file())


def _renamed(filename: str, char_key: str) -> str:
    """Compute the destination filename, renaming skeleton/atlas files.

    - skeleton.json -> {char_key}.json
    - skeleton.skel -> {char_key}.skel
    - *.atlas -> {char_key}.atlas
    - All other files (PNGs) keep original names.
    """
    if filename == "skeleton.json":
        return f"{char_key}.json"
    if filename == "skeleton.skel":
        return f"{char_key}.skel"
    if filename.endswith(".atlas"):
        return f"{char_key}.atlas"
    return filename


def deploy_character(
    root: Path,
    char_info: Dict[str, object],
    dry_run: bool,
    force: bool,
    skip_atlas_gen: bool = False,
    pipeline_output_override: Optional[str] = None,
) -> DeployResult:
    """Deploy a single character's Spine assets to the game repo.

    Args:
        root: Monorepo root path.
        char_info: Character dict from manifest.
        dry_run: If True, log actions without copying.
        force: If True, overwrite existing target directories.
        skip_atlas_gen: If True, skip auto-generation of .atlas files.
        pipeline_output_override: Override pipeline output base directory.

    Returns:
        DeployResult with outcome details.
    """
    game_id = str(char_info.get("game_id", "UNKNOWN"))
    char_key = str(char_info.get("character_key", "unknown"))

    source_dir = get_pipeline_output_dir(root, char_key, pipeline_output_override)
    target_dir = get_game_target_dir(root, game_id, char_key)

    result_base = {
        "game_id": game_id,
        "character": char_key,
        "source_path": str(source_dir),
        "target_path": str(target_dir),
    }

    # Auto-generate atlas if missing (before validation)
    if source_dir.exists() and source_dir.is_dir():
        atlas_files = list(source_dir.glob("*.atlas"))
        if not atlas_files and not skip_atlas_gen and not dry_run:
            generate_atlas_script = Path(__file__).parent / "generate_atlas.py"
            if generate_atlas_script.exists():
                print(f"  [INFO]  {game_id}/{char_key}: No .atlas found, auto-generating...")
                try:
                    subprocess.run(
                        [
                            sys.executable,
                            str(generate_atlas_script),
                            "--input-dir",
                            str(source_dir),
                            "--char-name",
                            char_key,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    print(f"  [OK]    {game_id}/{char_key}: Atlas generated successfully")
                except subprocess.CalledProcessError as e:
                    print(
                        f"  [WARN]  {game_id}/{char_key}: Atlas generation failed: "
                        f"{e.stderr.strip() if e.stderr else str(e)}"
                    )
            else:
                print(
                    f"  [WARN]  {game_id}/{char_key}: No .atlas found and "
                    f"generate_atlas.py not available"
                )
        elif not atlas_files and not skip_atlas_gen and dry_run:
            print(f"  [DRY]   {game_id}/{char_key}: Would auto-generate .atlas file")

    # Validate source
    validation_err = validate_source(source_dir)
    if validation_err is not None:
        print(f"  [WARN]  {game_id}/{char_key}: {validation_err}")
        return DeployResult(
            **result_base,
            success=False,
            files_copied=0,
            error=validation_err,
        )

    # Check if target already exists
    if target_dir.exists() and not force:
        existing_count = count_files(target_dir)
        print(f"  [SKIP]  {game_id}/{char_key}: target exists ({existing_count} files)")
        return DeployResult(
            **result_base,
            success=True,
            files_copied=0,
            error=None,
        )

    # Check game repo exists
    game_num = game_id.replace("MG-", "")
    game_repo = root / "repos" / f"mg-game-{game_num}" / "game"
    if not game_repo.exists():
        err_msg = f"Game repo not found: {game_repo}"
        print(f"  [ERROR] {game_id}/{char_key}: {err_msg}")
        return DeployResult(
            **result_base,
            success=False,
            files_copied=0,
            error=err_msg,
        )

    # Count source files
    source_files = [p for p in source_dir.iterdir() if p.is_file()]
    file_count = len(source_files)

    if dry_run:
        print(f"  [DRY]   {game_id}/{char_key}: would copy {file_count} files")
        print(f"          src:  {source_dir}")
        print(f"          dest: {target_dir}")
        for src_file in source_files:
            dst_name = _renamed(src_file.name, char_key)
            if dst_name != src_file.name:
                print(f"          [DRY-RUN] Would copy: {src_file.name} \u2192 {dst_name}")
            else:
                print(f"          [DRY-RUN] Would copy: {src_file.name}")
        return DeployResult(
            **result_base,
            success=True,
            files_copied=file_count,
            error=None,
        )

    # Actual deployment
    try:
        # Remove existing if force
        if target_dir.exists() and force:
            shutil.rmtree(str(target_dir))

        # Create target and copy files
        target_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        for src_file in source_files:
            dst_name = _renamed(src_file.name, char_key)
            dst_file = target_dir / dst_name
            shutil.copy2(str(src_file), str(dst_file))
            if dst_name != src_file.name:
                print(f"          Renamed: {src_file.name} \u2192 {dst_name}")
            copied += 1

        print(f"  [OK]    {game_id}/{char_key}: deployed {copied} files")
        return DeployResult(
            **result_base,
            success=True,
            files_copied=copied,
            error=None,
        )

    except Exception as e:
        err_msg = f"Copy failed: {e}"
        print(f"  [ERROR] {game_id}/{char_key}: {err_msg}")
        return DeployResult(
            **result_base,
            success=False,
            files_copied=0,
            error=err_msg,
        )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def compute_summary(results: List[DeployResult]) -> DeploySummary:
    """Compute aggregate statistics from deployment results."""
    summary = DeploySummary()

    game_ids = set()
    for r in results:
        game_ids.add(r.game_id)

        if r.error and not r.success:
            summary.errors += 1
        elif r.files_copied == 0 and r.success:
            summary.characters_skipped += 1
        elif r.success:
            summary.characters_deployed += 1

        summary.files_copied += r.files_copied

    summary.games_processed = len(game_ids)
    return summary


def print_summary(summary: DeploySummary, dry_run: bool) -> None:
    """Print the deployment summary to console."""
    mode_label = " (DRY RUN)" if dry_run else ""

    print()
    print(f"=== Spine Asset Deployment Report{mode_label} ===")
    print(f"Games processed:     {summary.games_processed}")
    print(f"Characters deployed: {summary.characters_deployed}")
    print(f"Characters skipped:  {summary.characters_skipped}")
    print(f"Errors:              {summary.errors}")
    print(f"Files copied:        {summary.files_copied}")
    print("=" * (37 + len(mode_label)))


def write_json_report(
    report_path: Path,
    results: List[DeployResult],
    summary: DeploySummary,
    dry_run: bool,
) -> None:
    """Write a JSON deployment report.

    Args:
        report_path: Output file path for the JSON report.
        results: List of per-character DeployResult.
        summary: Aggregated DeploySummary.
        dry_run: Whether this was a dry-run execution.
    """
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": "dry_run" if dry_run else "deploy",
        "summary": asdict(summary),
        "results": [asdict(r) for r in results],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n[OK]    Report written: {report_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_game_filter(game_id_str: str) -> List[str]:
    """Parse comma-separated game IDs into normalized MG-XXXX format.

    Accepts: '0001,0010' or 'MG-0001,MG-0010' or '1,10'
    """
    result = []
    for part in game_id_str.split(","):
        part = part.strip()
        if not part:
            continue

        # Strip MG- prefix if present
        cleaned = part.upper().replace("MG-", "")
        try:
            num = int(cleaned)
            result.append(f"MG-{num:04d}")
        except ValueError:
            print(f"[WARN]  Invalid game ID '{part}', skipping")
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Deploy Spine pipeline outputs to game repositories.\n"
            "Reads character-manifest.json and copies validated pipeline\n"
            "output files to each game's spine asset directory."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/deploy_spine_assets.py --dry-run --all\n"
            "  python scripts/deploy_spine_assets.py --game-id 0001,0010\n"
            "  python scripts/deploy_spine_assets.py --all --force\n"
            "  python scripts/deploy_spine_assets.py --all --report report.json\n"
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without copying any files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing target directories",
    )
    parser.add_argument(
        "--report",
        type=str,
        metavar="PATH",
        help="Write JSON deployment report to PATH",
    )

    parser.add_argument(
        "--skip-atlas-gen",
        action="store_true",
        help="Skip auto-generation of .atlas files if missing",
    )
    parser.add_argument(
        "--pipeline-output",
        type=str,
        metavar="PATH",
        default=None,
        help=(
            "Override pipeline output directory (absolute or relative to monorepo root). "
            "Default: repos/mg-tools/spine-ai-pipeline/output/{char_key}/spine. "
            "Example: repos/mg-tools/spine-ai-pipeline/output/full_batch/pipeline_output"
        ),
    )

    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--all",
        action="store_true",
        help="Deploy assets for all games in the manifest",
    )
    target_group.add_argument(
        "--game-id",
        type=str,
        metavar="IDS",
        help="Comma-separated game IDs (e.g., 0001,0010,0015)",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on errors.
    """
    parser = build_parser()
    args = parser.parse_args()

    # Resolve monorepo root
    root = resolve_monorepo_root()
    if not (root / "repos").is_dir():
        print(f"[ERROR] repos/ directory not found at {root}")
        print("Ensure this script is run from the spine-ai-pipeline directory.")
        return 1

    # Load manifest
    try:
        manifest = load_manifest(root)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to load manifest: {e}")
        return 1

    characters = manifest.get("characters", [])
    if not characters:
        print("[WARN]  No characters found in manifest.")
        return 0

    # Group by game
    by_game = group_by_game(characters if isinstance(characters, list) else [])

    # Filter games if --game-id specified
    if args.game_id:
        target_ids = set(parse_game_filter(args.game_id))
        if not target_ids:
            print("[ERROR] No valid game IDs provided.")
            return 1
        by_game = {gid: chars for gid, chars in by_game.items() if gid in target_ids}

    if not by_game:
        print("[WARN]  No matching games found in manifest.")
        return 0

    # Header
    mode = "DRY RUN" if args.dry_run else "DEPLOY"
    force_label = " (force)" if args.force else ""
    print(f"Spine Asset Deployment [{mode}{force_label}]")
    print(f"Monorepo root: {root}")
    print(f"Total games:   {len(by_game)}")
    total_chars = sum(len(c) for c in by_game.values())
    print(f"Total chars:   {total_chars}")
    print()

    # Deploy per game
    all_results: List[DeployResult] = []

    for game_id in sorted(by_game.keys()):
        chars = by_game[game_id]
        print(f"[{game_id}] ({len(chars)} character(s))")

        for char_info in chars:
            result = deploy_character(
                root, char_info, args.dry_run, args.force, args.skip_atlas_gen,
                pipeline_output_override=args.pipeline_output,
            )
            all_results.append(result)

        print()

    # Summary
    summary = compute_summary(all_results)
    print_summary(summary, args.dry_run)

    # JSON report
    if args.report:
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = Path.cwd() / report_path
        write_json_report(report_path, all_results, summary, args.dry_run)

    # Exit code
    return 1 if summary.errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
