# Batch Processor

**Batch Processor** is a collection of Python scripts for automated bulk processing of asset files.

## Tools

### 1. Transparency (Background Removal)

`remove_bg.py` uses AI (`rembg`) to automatically remove backgrounds from images, making them suitable for game assets (sprites, icons).

#### Installation

1.  Navigate to the directory:
    ```bash
    cd mg-tools/batch-processor
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: This installs `rembg`, `pillow`, and other required libraries.*

#### Usage

```bash
python remove_bg.py --input <input_folder> --output <output_folder>
```

| Argument | Short | Description |
|----------|-------|-------------|
| `--input` | `-i` | **Required**. Path to the folder containing original images (JPG/PNG). |
| `--output` | `-o` | **Required**. Path where processed PNGs with transparency will be saved. |

#### Example

```bash
python remove_bg.py -i "../../mg-game-0013/raw_assets" -o "../../mg-game-0013/game/assets/images"
```

---

## Future Tools
- Batch image resizing
- Format conversion (e.g., to WebP)
