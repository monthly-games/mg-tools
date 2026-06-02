# MG_TOOLS KNOWLEDGE BASE

## OVERVIEW
Python dev tools: CLI for Firebase/ads/game management, Spine AI character pipeline, batch processors, asset generators.

## STRUCTURE
```
mg-tools/
├── mg-cli/                     # Primary CLI tool (Click-based, v0.1.0)
│   ├── __main__.py            # Module entry: python -m mg-cli
│   ├── cli.py                 # Main CLI with Click groups
│   ├── config.py              # CLI configuration
│   ├── commands/              # analytics, cicd, infra, batch
│   ├── services/              # firebase_service, ads_service, game_scanner
│   └── templates/             # Code generation templates
├── spine-ai-pipeline/          # Character rigging AI
│   ├── scripts/               # generate_gallery, batch_generate, animate, export
│   ├── config/                # Pipeline config
│   ├── models/                # AI model references
│   ├── images/, input/, output/ # Asset I/O
│   └── test/                  # Pipeline tests
├── batch-processor/            # Batch operations (remove_bg, scripts/)
├── asset-generator/            # Asset generation (scripts/)
├── ci-tools/                   # CI/CD helpers
├── data-tools/                 # Data processing
├── prompt-extractor/           # Prompt extraction tool
├── config/                     # Shared tool configs
├── docs/                       # Tool documentation
└── scripts/                    # Setup/maintenance
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI entry | `mg-cli/cli.py` | Click framework, `python -m mg_cli` |
| Firebase mgmt | `mg-cli/services/firebase_service.py` | Project CRUD |
| Ad mgmt | `mg-cli/services/ads_service.py` | Ad unit config |
| Game discovery | `mg-cli/services/game_scanner.py` | Scan repos, find games |
| Character rigging | `spine-ai-pipeline/scripts/` | AI-powered Spine animation |
| Batch generation | `spine-ai-pipeline/scripts/batch_generate.py` | Multi-character |
| BG removal | `batch-processor/remove_bg.py` | Background removal tool |
| Tool config | `config/` | YAML configs for all tools |

## SPINE AI PIPELINE
Uses YOLO (pose detection) + SAM2 (segmentation) + LaMa ONNX (inpainting) for character rigging:
- Models: `yolo11n-pose.pt`, `yolov8l-worldv2.pt`, `sam2.1_b.pt`, `sam2.1_l.pt`, `lama_fp32.onnx`
- Pipeline: Input → BiRefNet matting → YOLO pose → SAM2 segment → LaMa inpaint → Rig → Animate → Export
- Quality gates: 3-stage (segmentation, rigging, animation). **87.5% PASS rate achieved**
- Tests: 242 Python tests (0 failures). Run: `pytest -m "not requires_gpu" -v`
- Markers: `requires_gpu`, `e2e`, `slow` (skip GPU tests on CI)
- See `spine-ai-pipeline/AGENTS.md` for full details

## CONVENTIONS
- Python 3.11+, type hints required
- Services encapsulate external API calls, commands are thin wrappers
- Click framework for CLI (not argparse)
- YAML for all config files
- Dependencies: `requirements.txt` (PyTorch, YOLO, SAM2, ONNX, Diffusers, Gradio)

## ANTI-PATTERNS
- **NEVER** hardcode game paths — use `game_scanner` service
- **NEVER** store API keys in code — use environment variables or `config/gemini_key.txt` (gitignored)
- **NEVER** commit model weights (`models/*.pt`, `*.onnx`) — gitignored, download on demand
