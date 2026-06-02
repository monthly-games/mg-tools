# Prompt Extractor

**Prompt Extractor** is a CLI tool designed to automate the extraction of asset generation prompts from markdown documentation. It parses structured markdown files and outputs the prompts in a JSON format suitable for automated asset generation pipelines.

## Features

- Extracts prompts tagged with specific keywords (`Prompt:`, `VFX Prompt:`, `Music Prompt:`, `SFX Prompt:`).
- Parses section headers (e.g., `#### Item Name`) to infer asset names.
- Filters results by asset type (Image, VFX, Audio).
- Outputs standard JSON for easy integration with other tools.

## Installation

This tool is a Dart package. Ensure you have the Dart SDK installed.

```bash
cd mg-tools/prompt-extractor
dart pub get
```

## Usage

Run the tool using `dart run` or directly via the script.

```bash
dart bin/extract_prompts.dart --input <path_to_markdown_file> [options]
```

### Arguments

| Argument | Partial | Required | Description |
|----------|---------|----------|-------------|
| `--input` | `-i` | **Yes** | Path to the markdown file containing prompts. |
| `--type` | `-t` | No | Filter prompts by type (e.g., `VFX`, `Image`, `Audio`). |

### Example

Extract all VFX prompts from a design document:

```bash
dart bin/extract_prompts.dart -i "../../mg-game-0002/docs/resource_generation_prompts.md" -t VFX
```

## Markdown Format Requirements

To be correctly parsed, your markdown file should follow this structure:

1.  **Asset Name**: Use a level 4 header (`####`) for the asset name.
2.  **Prompt Block**: Use a code block (triple backticks) containing the prompt.
3.  **Keywords**: Inside the code block, start the prompt text with `Prompt:`, `VFX Prompt:`, `SFX Prompt:`, or `Music Prompt:`.

**Example:**

```markdown
#### Fireball Spell

\`\`\`
VFX Prompt:
A swirling ball of fire, 64x64 pixels. Orange and yellow core with smoke trail.
\`\`\`
```

## Output Format

The tool outputs a JSON array:

```json
[
  {
    "name": "Fireball Spell",
    "prompt": "A swirling ball of fire, 64x64 pixels. Orange and yellow core with smoke trail.",
    "type": "VFX"
  }
]
```
