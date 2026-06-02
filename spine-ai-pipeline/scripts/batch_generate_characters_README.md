# batch_generate_characters.py

Batch generate character images via ComfyUI with multi-seed best-pick strategy.

## Overview

For each character in the manifest:
1. Generate N images with different seeds via ComfyUI API
2. Run segmentation (split_parts) on each
3. Pick the image with best QG1 score (most parts, highest completeness)
4. Run full pipeline (rig + animate + export) on the winner
5. Track results in JSON report

## Usage

### Dry-run (preview without generating)
```bash
python scripts/batch_generate_characters.py --dry-run --all
python scripts/batch_generate_characters.py --dry-run --game-id 0001,0002
```

### Generate with specific games
```bash
python scripts/batch_generate_characters.py --game-id 0001,0002 --seeds 3
python scripts/batch_generate_characters.py --all --seeds 3
```

### Custom output and seeds
```bash
python scripts/batch_generate_characters.py --all --seeds 5 --seed-start 100 --output-base output/custom
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--manifest` | `.sisyphus/evidence/character-manifest.json` | Character manifest JSON path |
| `--output-base` | `output/batch` | Base output directory |
| `--seeds` | 3 | Number of seeds per character |
| `--seed-start` | 42 | Starting seed value (increments by 111) |
| `--all` | — | Process all games |
| `--game-id` | — | Comma-separated game IDs (e.g., 0001,0002) |
| `--dry-run` | — | Preview without generating |
| `--report` | `output/batch/batch_report.json` | Save JSON report |

## Output Structure

```
output/batch/
├── generation/
│   ├── tower_archer/
│   │   ├── tower_archer_s42.png
│   │   ├── tower_archer_s153.png
│   │   ├── tower_archer_s264.png
│   │   ├── tower_archer_s42_parts/
│   │   │   ├── metadata.json
│   │   │   ├── head.png
│   │   │   └── ...
│   │   └── ...
│   └── ...
├── pipeline_output/
│   ├── tower_archer/
│   │   └── spine/
│   │       ├── skeleton.json
│   │       ├── skeleton.atlas
│   │       └── ...
│   └── ...
└── batch_report.json
```

## Report Format

```json
{
  "timestamp": "2026-03-14T12:34:56.789012+00:00",
  "config": {
    "seeds": 3,
    "seed_start": 42,
    "dry_run": false
  },
  "summary": {
    "total": 158,
    "pass": 120,
    "warn": 25,
    "fail": 10,
    "skip": 3
  },
  "results": [
    {
      "game_id": "MG-0001",
      "character_key": "tower_archer",
      "seeds_tried": 3,
      "best_seed": 153,
      "best_parts": 12,
      "best_qg1": "PASS",
      "pipeline_result": "PASS",
      "animations": ["idle", "walk", "attack"],
      "bones": 18,
      "error": null
    },
    ...
  ]
}
```

## Requirements

- Python 3.11+
- ComfyUI running on `192.168.50.165` (ports 8192, 8193, 8191, 8190)
- `requests` library: `pip install requests`
- `split_parts.py` and `batch_process.py` in same scripts directory
- Character manifest at `.sisyphus/evidence/character-manifest.json`

## Quality Gate Thresholds

| Metric | WARN | FAIL |
|--------|------|------|
| Part count | — | < 3 |
| Completeness | < 0.75 | < 0.5 |
| Avg confidence | < 0.25 | < 0.15 |
| Alpha noise | > 0.18 | > 0.36 |

## Prompt Template

Uses **Prompt B** (winning prompt from testing):

**Positive**: "single game character, fantasy {char_type}, front facing, T-pose arms out, full body visible, 2D anime style, clean lines, white background, no accessories, standing straight, solo"

**Negative**: "multiple characters, character sheet, reference sheet, turnaround, dynamic pose, cropped, text, watermark, photorealistic, 3d render"

**Model**: `Lunark/novaAnimeXL_ilV100.safetensors`

## Seed Strategy

Seeds are generated as: `seed_start + i * 111` for i in range(seeds)

Default: 42, 153, 264 (3 seeds)

This ensures diverse image variations while maintaining reproducibility.

## Error Handling

- **Generation fails**: Tries next seed
- **Segmentation fails**: Tries next seed
- **All seeds fail**: Marks character as FAIL, skips pipeline
- **QG1 FAIL**: Skips pipeline (QG1 WARN/PASS proceed)
- **Pipeline fails**: Marks as FAIL with error message

## Example Workflow

```bash
# 1. Preview what would happen
python scripts/batch_generate_characters.py --dry-run --game-id 0001,0002

# 2. Generate with 3 seeds per character
python scripts/batch_generate_characters.py --game-id 0001,0002 --seeds 3

# 3. Check report
cat output/batch/batch_report.json | python -m json.tool

# 4. Inspect best images
ls output/batch/generation/tower_archer/
```

## Notes

- ComfyUI must be running and reachable
- Generation takes ~3-5 minutes per seed (depends on ComfyUI load)
- Segmentation takes ~1-2 minutes per image
- Full pipeline takes ~2-3 minutes per character
- Total time for 158 characters with 3 seeds: ~24-36 hours
- Use `--workers` flag with `batch_process.py` for parallelization
