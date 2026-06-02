# SPINE AI PIPELINE KNOWLEDGE BASE

**Last Updated:** Fri Mar 13 2026

## OVERVIEW
Python 3.11 pipeline: auto-rig 2D characters for Spine 4.1 using YOLO pose detection + SAM2 segmentation + LaMa inpainting. **87.5% PASS rate**. 242 tests, 0 failures.

## STRUCTURE
```
spine-ai-pipeline/
├── scripts/
│   ├── batch_process.py      # 451 lines — Main orchestrator (--input, --workers)
│   ├── split_parts.py        # 1,084 lines — YOLO+SAM2 segmentation engine
│   ├── rig_character.py      # 768 lines — Template-based skeleton generation
│   ├── export_spine.py       # 239 lines — Spine JSON/atlas export + deployment
│   ├── animate_character.py  # 311 lines — Preset animation application
│   └── lib/
│       ├── quality_gate.py   # 330 lines — 3-stage validation (seg/rig/anim)
│       ├── spine_templates.py # 547 lines — Humanoid/Chibi/Monster bone hierarchies
│       ├── asset_registry.py # 361 lines — SQLite deployment tracker
│       ├── gemini_client.py  # 113 lines — Gemini API image refinement
│       └── lama_client.py    # 181 lines — ONNX inpainting (graceful degradation)
├── tests/                    # 8 test files, 1,925 lines
│   ├── conftest.py           # Shared fixtures (sample_parts_metadata, small_rgba_image)
│   ├── test_quality_gate.py  # 311 lines — 3-stage validation coverage
│   ├── test_asset_registry.py # 339 lines — SQLite CRUD
│   ├── test_chibi_stabilization.py # 508 lines — Proportional scaling
│   └── e2e/test_full_pipeline.py   # End-to-end (requires_gpu marker)
├── models/                   # AI weights (gitignored — download on demand)
├── requirements.txt          # PyTorch, YOLO, SAM2, ONNX, Diffusers, Gradio
└── pytest.ini                # markers: requires_gpu, e2e, slow
```

## PIPELINE STAGES
```
Input PNG → BiRefNet matting → YOLO pose (17 keypoints) → SAM2 segment
→ QG1 (segmentation) → LaMa inpaint → rig_character (template auto-scale)
→ QG2 (rigging) → animate_character (idle/walk/attack presets)
→ QG3 (animation) → export_spine (JSON+atlas) → asset_registry (SQLite)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Run pipeline | `scripts/batch_process.py` | `--input dir --workers 4` |
| Quality validation | `scripts/lib/quality_gate.py` | PASS/WARN/FAIL per stage |
| Skeleton templates | `scripts/lib/spine_templates.py` | humanoid/chibi/monster |
| Deployment tracking | `scripts/lib/asset_registry.py` | SQLite, game_id → status |
| Inpainting | `scripts/lib/lama_client.py` | ONNX, graceful degradation |
| Tests | `tests/` | `pytest -m "not requires_gpu" -v` |

## QUALITY GATE THRESHOLDS
| Metric | WARN | FAIL | Stage |
|--------|------|------|-------|
| Part count | — | < 3 | Segmentation |
| Completeness | < 0.75 | < 0.5 | Segmentation |
| Avg confidence | < 0.25 | < 0.15 | Segmentation |
| Alpha noise | > 0.18 | > 0.36 | Segmentation |
| Bone count | — | < 6 | Rigging |
| Bone variance | > 0.20 | > 0.40 | Rigging |
| Symmetry error | > 0.10 | > 0.20 | Rigging |

## COMMANDS
```bash
pip install -r requirements.txt
pytest -m "not requires_gpu" -v                          # Run tests (no GPU)
pytest -m "not requires_gpu and not slow" -v             # Fast tests only
python scripts/batch_process.py --input input/ --workers 4
python scripts/quality_gate.py <skeleton.json>           # Single validation
```

## CONVENTIONS
- Python 3.11+, type hints required, AAA test pattern
- pytest fixtures in `conftest.py` (not inline)
- Mark GPU/slow tests: `@pytest.mark.requires_gpu`, `@pytest.mark.slow`
- Models gitignored — download via `lama_client._load_model()` or manually

## ANTI-PATTERNS
- **NEVER** commit model weights (`*.pt`, `*.onnx`) — gitignored
- **NEVER** commit API keys — use `config/gemini_key.txt` (gitignored)
- **NEVER** hardcode quality thresholds inline — use `QualityGate` ClassVars
- **DO NOT** skip quality gates — FAIL blocks pipeline, WARN allows with logging
