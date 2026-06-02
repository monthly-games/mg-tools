#!/usr/bin/env python3
"""
Comprehensive Spine Asset Validation Script
Validates visual quality, animation smoothness, and performance metrics
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def validate_visual_quality(skeleton_path: Path) -> Tuple[bool, Dict[str, bool]]:
    """
    Validate visual quality metrics

    Args:
        skeleton_path: Path to skeleton.json file

    Returns:
        (overall_pass, individual_checks)
    """
    with open(skeleton_path) as f:
        skeleton = json.load(f)

    bones = skeleton.get('bones', [])
    slots = skeleton.get('slots', [])
    skins = skeleton.get('skins', [])
    animations = skeleton.get('animations', {})

    checks = {
        'bone_count': len(bones) >= 20,
        'slot_count': len(slots) >= 10,
        'skin_count': len(skins) >= 1,
        'animation_count': len(animations) >= 3,
        'has_ik': any('ik' in bone for bone in bones),
        'has_constraints': len(skeleton.get('transform', [])) > 0,
        'has_meshes': any('mesh' in slot for slot in slots),
    }

    return all(checks.values()), checks


def validate_animation_smoothness(skeleton_path: Path) -> Tuple[bool, List[str]]:
    """
    Check animation smoothness by validating keyframe density

    Args:
        skeleton_path: Path to skeleton.json file

    Returns:
        (overall_pass, error_messages)
    """
    with open(skeleton_path) as f:
        skeleton = json.load(f)

    errors = []
    animations = skeleton.get('animations', {})

    if len(animations) == 0:
        return False, ["No animations found"]

    for anim_name, anim_data in animations.items():
        # Check keyframe density for each bone
        for bone_name, timeline in anim_data.items():
            if 'rotate' in timeline:
                keyframes = timeline['rotate']
                if len(keyframes) < 2:
                    errors.append(f"Animation {anim_name}: {bone_name} has insufficient keyframes ({len(keyframes)} < 2)")

            if 'translate' in timeline:
                keyframes = timeline['translate']
                if len(keyframes) < 2:
                    errors.append(f"Animation {anim_name}: {bone_name} has insufficient translation keyframes")

            if 'scale' in timeline:
                keyframes = timeline['scale']
                if len(keyframes) < 2:
                    errors.append(f"Animation {anim_name}: {bone_name} has insufficient scale keyframes")

    return len(errors) == 0, errors


def validate_file_size(skeleton_path: Path, max_size_mb: float = 5.0) -> Tuple[bool, float]:
    """
    Check if file size is within acceptable limits

    Args:
        skeleton_path: Path to skeleton.json file
        max_size_mb: Maximum file size in MB

    Returns:
        (pass, actual_size_mb)
    """
    size_bytes = skeleton_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return size_mb <= max_size_mb, size_mb


def validate_json_structure(skeleton_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate JSON structure and required fields

    Args:
        skeleton_path: Path to skeleton.json file

    Returns:
        (overall_pass, error_messages)
    """
    errors = []

    try:
        with open(skeleton_path) as f:
            skeleton = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Check required top-level fields
    required_fields = ['skeleton', 'bones', 'slots']
    for field in required_fields:
        if field not in skeleton:
            errors.append(f"Missing required field: {field}")

    # Check skeleton metadata
    if 'skeleton' in skeleton:
        skeleton_meta = skeleton['skeleton']
        if 'width' not in skeleton_meta or 'height' not in skeleton_meta:
            errors.append("Missing width/height in skeleton metadata")

    # Check bones structure
    if 'bones' in skeleton:
        bones = skeleton['bones']
        for i, bone in enumerate(bones):
            if 'name' not in bone:
                errors.append(f"Bone {i} missing name")

    return len(errors) == 0, errors


def comprehensive_quality_check(
    output_dir: Path,
    threshold: float = 0.95
) -> Dict:
    """
    Run comprehensive quality check on all skeleton files

    Args:
        output_dir: Directory containing generated assets
        threshold: Quality threshold (0.0 to 1.0)

    Returns:
        Quality report dictionary
    """
    skeleton_files = list(output_dir.rglob('skeleton.json'))

    if len(skeleton_files) == 0:
        return {
            'status': 'error',
            'message': 'No skeleton files found',
            'total_files': 0,
            'passed_files': 0,
            'pass_rate': 0.0,
        }

    results = []
    passed_count = 0

    for skeleton_path in skeleton_files:
        # Run all validations
        visual_pass, visual_checks = validate_visual_quality(skeleton_path)
        animation_pass, animation_errors = validate_animation_smoothness(skeleton_path)
        size_pass, size_mb = validate_file_size(skeleton_path)
        json_pass, json_errors = validate_json_structure(skeleton_path)

        overall_pass = visual_pass and animation_pass and size_pass and json_pass

        if overall_pass:
            passed_count += 1

        results.append({
            'path': str(skeleton_path.relative_to(output_dir)),
            'overall_pass': overall_pass,
            'visual_quality': {
                'pass': visual_pass,
                'checks': visual_checks,
            },
            'animation_smoothness': {
                'pass': animation_pass,
                'errors': animation_errors,
            },
            'file_size': {
                'pass': size_pass,
                'size_mb': size_mb,
            },
            'json_structure': {
                'pass': json_pass,
                'errors': json_errors,
            },
        })

    pass_rate = passed_count / len(skeleton_files) if skeleton_files else 0.0

    return {
        'status': 'pass' if pass_rate >= threshold else 'fail',
        'threshold': threshold,
        'total_files': len(skeleton_files),
        'passed_files': passed_count,
        'failed_files': len(skeleton_files) - passed_count,
        'pass_rate': pass_rate,
        'results': results,
    }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Spine assets')
    parser.add_argument('--input', required=True, help='Input directory')
    parser.add_argument('--threshold', type=float, default=0.95, help='Quality threshold (0.0-1.0)')
    parser.add_argument('--report', default='quality_report.json', help='Output report path')

    args = parser.parse_args()

    output_dir = Path(args.input)
    if not output_dir.exists():
        print(f"ERROR: Input directory not found: {output_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Running quality check on: {output_dir}")
    print(f"Threshold: {args.threshold:.0%}")

    report = comprehensive_quality_check(output_dir, args.threshold)

    # Save report
    report_path = Path(args.report)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nQuality Report: {report_path}")
    print(f"Status: {report['status'].upper()}")
    print(f"Total files: {report['total_files']}")
    print(f"Passed: {report['passed_files']}")
    print(f"Failed: {report['failed_files']}")
    print(f"Pass rate: {report['pass_rate']:.1%}")

    if report['status'] == 'fail':
        print("\nFailed files:")
        for result in report['results']:
            if not result['overall_pass']:
                print(f"  - {result['path']}")
        sys.exit(1)
    else:
        print("\n✓ Quality check passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
