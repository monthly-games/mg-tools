#!/usr/bin/env python3
"""Batch generate character images via ComfyUI with multi-seed best-pick strategy.

For each character in the manifest:
1. Generate N images with different seeds via ComfyUI API
2. Run segmentation (split_parts) on each
3. Pick the image with best QG1 score (most parts, highest completeness)
4. Run full pipeline (rig + animate + export) on the winner
5. Track results

Usage:
    python scripts/batch_generate_characters.py --dry-run --all
    python scripts/batch_generate_characters.py --game-id 0001,0002 --seeds 3
    python scripts/batch_generate_characters.py --all --seeds 3 --workers 2
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ComfyUI config
COMFY_HOST = '192.168.50.165'
COMFY_PORTS = [8192, 8193, 8191, 8190]

# Prompt B (winning prompt from testing — QG1 PASS with 12 parts)
# Character type gets substituted into {char_type}
PROMPT_TEMPLATE = {
    'positive': 'single game character, fantasy {char_type}, front facing, T-pose arms out, full body visible, 2D anime style, clean lines, white background, no accessories, standing straight, solo',
    'negative': 'multiple characters, character sheet, reference sheet, turnaround, dynamic pose, cropped, text, watermark, photorealistic, 3d render',
}

MODEL = 'Lunark/novaAnimeXL_ilV100.safetensors'

@dataclass
class CharacterResult:
    game_id: str
    character_key: str
    seeds_tried: int
    best_seed: Optional[int]
    best_parts: int
    best_qg1: str  # PASS/WARN/FAIL
    pipeline_result: str  # PASS/WARN/FAIL/SKIP
    animations: List[str] = field(default_factory=list)
    bones: int = 0
    error: Optional[str] = None

def find_comfy():
    """Find a reachable ComfyUI port."""
    try:
        import requests
    except ImportError:
        print('[ERROR] requests library not found. Install: pip install requests')
        return None
    
    for port in COMFY_PORTS:
        try:
            r = requests.get(f'http://{COMFY_HOST}:{port}/system_stats', timeout=5)
            if r.status_code == 200:
                return f'http://{COMFY_HOST}:{port}'
        except:
            continue
    return None

def extract_char_type(character_key: str) -> str:
    """Extract character type from key for prompt customization.
    'tower_archer' -> 'archer', 'hero_warrior' -> 'warrior', 'alchemist_cat' -> 'alchemist cat'
    """
    # Remove common prefixes
    prefixes = ['tower_', 'hero_', 'idle_', 'puzzle_', 'card_', 'rpg_', 'sports_']
    name = character_key
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
            break
    return name.replace('_', ' ')

def generate_image(comfy_url: str, char_key: str, seed: int, output_dir: Path) -> Optional[Path]:
    """Generate one image via ComfyUI API. Returns path or None."""
    try:
        import requests
    except ImportError:
        print('[ERROR] requests library not found')
        return None
    
    char_type = extract_char_type(char_key)
    pos = PROMPT_TEMPLATE['positive'].format(char_type=char_type)
    neg = PROMPT_TEMPLATE['negative']
    prefix = f'{char_key}_s{seed}'
    
    wf = {
        '3': {'class_type': 'KSampler', 'inputs': {'seed': seed, 'steps': 30, 'cfg': 7.0, 'sampler_name': 'euler_ancestral', 'scheduler': 'normal', 'denoise': 1.0, 'model': ['4', 0], 'positive': ['6', 0], 'negative': ['7', 0], 'latent_image': ['5', 0]}},
        '4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': MODEL}},
        '5': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 1024, 'height': 1024, 'batch_size': 1}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': pos, 'clip': ['4', 1]}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'text': neg, 'clip': ['4', 1]}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0], 'vae': ['4', 2]}},
        '9': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': prefix, 'images': ['8', 0]}},
    }
    
    try:
        r = requests.post(f'{comfy_url}/prompt', json={'prompt': wf}, timeout=30)
        pid = r.json()['prompt_id']
        for _ in range(40):  # 120s max
            time.sleep(3)
            h = requests.get(f'{comfy_url}/history/{pid}', timeout=10).json()
            if pid in h:
                imgs = h[pid].get('outputs', {}).get('9', {}).get('images', [])
                if imgs:
                    img = imgs[0]
                    url = f"{comfy_url}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}"
                    data = requests.get(url, timeout=30).content
                    out = output_dir / f'{prefix}.png'
                    out.write_bytes(data)
                    return out
        return None
    except Exception as e:
        print(f'    [ERROR] Generation failed (seed={seed}): {e}')
        return None

def run_segmentation(image_path: Path, output_dir: Path) -> Tuple[Optional[dict], Path]:
    """Run split_parts.py on an image. Returns (metadata_dict, parts_dir)."""
    parts_dir = output_dir / f'{image_path.stem}_parts'
    script_dir = Path(__file__).parent.parent  # spine-ai-pipeline root
    
    try:
        p = subprocess.run(
            [sys.executable, 'scripts/split_parts.py', '--input', str(image_path), '--output', str(parts_dir)],
            cwd=str(script_dir), capture_output=True, text=True, timeout=180, encoding='utf-8', errors='replace'
        )
        meta_path = parts_dir / 'metadata.json'
        if meta_path.exists():
            return json.loads(meta_path.read_text(encoding='utf-8')), parts_dir
    except Exception as e:
        print(f'    [ERROR] Segmentation failed: {e}')
    return None, parts_dir

def check_qg1(metadata: dict, parts_dir: Path) -> Tuple[str, int, float]:
    """Run QG1 check. Returns (level, part_count, completeness)."""
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from lib.quality_gate import QualityGate
    except ImportError:
        print('[ERROR] quality_gate module not found')
        return 'FAIL', 0, 0.0
    
    result = QualityGate.check_segmentation(metadata, parts_dir=parts_dir)
    parts = len(metadata.get('parts', []))
    completeness = result.metrics.get('completeness', 0.0)
    return result.level.value.upper(), parts, completeness

def run_full_pipeline(image_path: Path, char_key: str, output_base: Path) -> dict:
    """Run batch_process.py on a single image. Returns result dict."""
    script_dir = Path(__file__).parent.parent
    input_dir = output_base / 'pipeline_input' / char_key
    input_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        import shutil
    except ImportError:
        print('[ERROR] shutil module not found')
        return {'success': False, 'error': 'shutil import failed'}
    
    shutil.copy2(image_path, input_dir / f'{char_key}.png')
    
    try:
        p = subprocess.run(
            [sys.executable, 'scripts/batch_process.py', 
             '--input_dir', str(input_dir),
             '--output_base', str(output_base / 'pipeline_output'),
             '--template', 'humanoid', '--workers', '1'],
            cwd=str(script_dir), capture_output=True, text=True, timeout=300, encoding='utf-8', errors='replace'
        )
        
        # Check output
        spine_dir = output_base / 'pipeline_output' / char_key / 'spine'
        skel_path = spine_dir / 'skeleton.json'
        if skel_path.exists():
            skel = json.loads(skel_path.read_text(encoding='utf-8'))
            return {
                'success': True,
                'bones': len(skel.get('bones', [])),
                'animations': list(skel.get('animations', {}).keys()),
                'output_dir': str(spine_dir),
            }
        return {'success': False, 'error': 'No skeleton.json produced'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        # Cleanup temp input
        try:
            import shutil
            shutil.rmtree(input_dir, ignore_errors=True)
        except:
            pass

def process_character(comfy_url: str, char: dict, seeds: List[int], output_base: Path, dry_run: bool) -> CharacterResult:
    """Process one character: generate N images, pick best, run pipeline."""
    game_id = char['game_id']
    char_key = char['character_key']
    result = CharacterResult(game_id=game_id, character_key=char_key, seeds_tried=len(seeds),
                             best_seed=None, best_parts=0, best_qg1='SKIP', pipeline_result='SKIP')
    
    if dry_run:
        print(f'  [DRY] {game_id}/{char_key}: would generate {len(seeds)} images')
        return result
    
    char_dir = output_base / 'generation' / char_key
    char_dir.mkdir(parents=True, exist_ok=True)
    
    best_image = None
    best_score = (-1, -1.0)  # (parts, completeness)
    
    # Generate + segment + score each seed
    for seed in seeds:
        print(f'    Seed {seed}...', end=' ', flush=True)
        img = generate_image(comfy_url, char_key, seed, char_dir)
        if not img:
            print('FAIL (generation)')
            continue
        
        meta, parts_dir = run_segmentation(img, char_dir)
        if not meta:
            print('FAIL (segmentation)')
            continue
        
        level, parts, completeness = check_qg1(meta, parts_dir)
        print(f'{level} ({parts} parts, {completeness:.2f})')
        
        score = (parts, completeness)
        if score > best_score:
            best_score = score
            best_image = img
            result.best_seed = seed
            result.best_parts = parts
            result.best_qg1 = level
    
    if not best_image:
        result.pipeline_result = 'FAIL'
        result.error = 'All seeds failed generation/segmentation'
        print(f'  [ERROR] {game_id}/{char_key}: no viable image')
        return result
    
    print(f'  [BEST] {game_id}/{char_key}: seed={result.best_seed}, {result.best_parts} parts, QG1={result.best_qg1}')
    
    # Run full pipeline on best image
    if result.best_qg1 == 'FAIL':
        result.pipeline_result = 'SKIP'
        result.error = 'Best QG1 was FAIL, skipping pipeline'
        print(f'  [SKIP] {game_id}/{char_key}: QG1 FAIL, skipping pipeline')
        return result
    
    print(f'  [PIPE] Running full pipeline on best image...')
    pipe_result = run_full_pipeline(best_image, char_key, output_base)
    
    if pipe_result['success']:
        result.pipeline_result = 'PASS'
        result.bones = pipe_result['bones']
        result.animations = pipe_result['animations']
        print(f'  [OK] {game_id}/{char_key}: {result.bones} bones, {result.animations}')
    else:
        result.pipeline_result = 'FAIL'
        result.error = pipe_result.get('error', 'unknown')
        print(f'  [ERROR] {game_id}/{char_key}: pipeline failed: {result.error}')
    
    return result

def main():
    parser = argparse.ArgumentParser(description='Batch generate character images with multi-seed best-pick strategy')
    parser.add_argument('--manifest', type=Path, 
                        default=Path(__file__).resolve().parent.parent.parent.parent.parent / '.sisyphus' / 'evidence' / 'character-manifest.json',
                        help='Character manifest JSON path')
    parser.add_argument('--output-base', type=Path, default=Path('output/batch'),
                        help='Base output directory')
    parser.add_argument('--seeds', type=int, default=3, help='Number of seeds per character')
    parser.add_argument('--seed-start', type=int, default=42, help='Starting seed value')
    parser.add_argument('--all', action='store_true', help='Process all games')
    parser.add_argument('--game-id', type=str, help='Comma-separated game IDs (e.g., 0001,0002)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without generating')
    parser.add_argument('--report', type=Path, help='Save JSON report')
    args = parser.parse_args()
    
    if not args.all and not args.game_id:
        parser.error('Specify --all or --game-id')
    
    # Load manifest
    if not args.manifest.exists():
        print(f'[ERROR] Manifest not found: {args.manifest}')
        sys.exit(1)
    
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    characters = manifest.get('characters', [])
    
    # Filter by game-id
    if args.game_id:
        game_ids = {f'MG-{g.zfill(4)}' for g in args.game_id.split(',')}
        characters = [c for c in characters if c['game_id'] in game_ids]
    
    print(f'=== Batch Character Generation ===')
    print(f'Characters: {len(characters)}')
    print(f'Seeds per character: {args.seeds}')
    print(f'Total generations: ~{len(characters) * args.seeds}')
    print(f'Output: {args.output_base}')
    if args.dry_run:
        print(f'MODE: DRY RUN')
    print()
    
    # Find ComfyUI
    comfy_url = None
    if not args.dry_run:
        comfy_url = find_comfy()
        if not comfy_url:
            print('[ERROR] ComfyUI unreachable on all ports')
            sys.exit(1)
        print(f'[OK] ComfyUI: {comfy_url}')
    
    # Generate seeds
    seeds = [args.seed_start + i * 111 for i in range(args.seeds)]  # 42, 153, 264 etc.
    
    # Process characters
    args.output_base.mkdir(parents=True, exist_ok=True)
    results = []
    
    # Group by game for progress reporting
    games = {}
    for c in characters:
        games.setdefault(c['game_id'], []).append(c)
    
    for game_id in sorted(games.keys()):
        chars = games[game_id]
        print(f'\n--- {game_id} ({len(chars)} characters) ---')
        for char in chars:
            result = process_character(comfy_url, char, seeds, args.output_base, args.dry_run)
            results.append(result)
    
    # Summary
    passed = sum(1 for r in results if r.pipeline_result == 'PASS')
    warned = sum(1 for r in results if r.pipeline_result == 'WARN')
    failed = sum(1 for r in results if r.pipeline_result == 'FAIL')
    skipped = sum(1 for r in results if r.pipeline_result == 'SKIP')
    
    print(f'\n=== Summary ===')
    print(f'Total characters: {len(results)}')
    print(f'Pipeline PASS:    {passed}')
    print(f'Pipeline WARN:    {warned}')
    print(f'Pipeline FAIL:    {failed}')
    print(f'Pipeline SKIP:    {skipped}')
    print(f'Success rate:     {(passed + warned) / max(len(results), 1) * 100:.1f}%')
    
    # Save report
    report_path = args.report or args.output_base / 'batch_report.json'
    report = {
        'timestamp': datetime.now().isoformat(),
        'config': {'seeds': args.seeds, 'seed_start': args.seed_start, 'dry_run': args.dry_run},
        'summary': {'total': len(results), 'pass': passed, 'warn': warned, 'fail': failed, 'skip': skipped},
        'results': [asdict(r) for r in results],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\nReport: {report_path}')

if __name__ == '__main__':
    main()
