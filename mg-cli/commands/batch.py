"""Batch commands for mg-cli."""

import subprocess
import os
import re
from pathlib import Path
from typing import List, Tuple


class BatchService:
    """Service for batch operations across games."""

    def __init__(self, repos_path: Path):
        self.repos_path = repos_path

    def get_game_path(self, game_id: int) -> Path:
        return self.repos_path / f"mg-game-{game_id:04d}"

    def get_game_lib_path(self, game_id: int) -> Path:
        return self.get_game_path(game_id) / "game" / "lib"

    # ==================== Submodule Operations ====================

    def update_submodule(self, game_id: int, submodule: str = "libs/mg_common_game") -> Tuple[bool, str]:
        """Update a submodule in a game repository."""
        game_path = self.get_game_path(game_id)
        submodule_path = game_path / submodule

        if not submodule_path.exists():
            return False, "Submodule not found"

        # Reset submodule
        os.chdir(submodule_path)
        subprocess.run(["git", "checkout", "--", "."], capture_output=True)
        subprocess.run(["git", "clean", "-fd"], capture_output=True)

        # Update
        os.chdir(game_path)
        result = subprocess.run(
            ["git", "submodule", "update", "--remote", submodule],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            return False, f"Update failed: {result.stderr[:100]}"

        # Check and commit if changed
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if submodule in status.stdout:
            subprocess.run(["git", "add", submodule], capture_output=True)
            subprocess.run([
                "git", "commit", "-m",
                f"chore: Update {submodule.split('/')[-1]} submodule\n\n"
                "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\n"
                "Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
            ], capture_output=True)
            return True, "Updated and committed"
        return True, "Already up to date"

    # ==================== Gacha/BattlePass Adapter Operations ====================

    def fix_gacha_adapter(self, game_id: int) -> Tuple[bool, str]:
        """Fix gacha adapter for new mg-common-game API."""
        adapter_path = self.get_game_lib_path(game_id) / "features" / "gacha" / "gacha_adapter.dart"

        if not adapter_path.exists():
            return False, "Adapter not found"

        with open(adapter_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Apply fixes
        content = re.sub(r'\.pullMulti\(', '.multiPull(', content)
        content = re.sub(r'\.multiPull\((\w+), (\d+)\)', r'.multiPull(\1, count: \2)', content)
        content = re.sub(r'\.pullsUntilPity\(', '.remainingPity(', content)
        content = re.sub(
            r'_gachaManager\.getTotalPulls\((\w+)\)',
            r'_gachaManager.getPityState(\1)?.totalPulls ?? 0',
            content
        )
        content = re.sub(r'\.getStatistics\(', '.getStats(', content)
        content = re.sub(
            r'return _convertToItem\(result\);',
            'return _convertToItem(result.item);',
            content
        )
        content = re.sub(
            r'return results\.map\(_convertToItem\)\.toList\(\);',
            'return results.map((r) => _convertToItem(r.item)).toList();',
            content
        )
        content = re.sub(
            r'Map<GachaRarity, int> get stats =>',
            'GachaStats get stats =>',
            content
        )

        if content != original:
            with open(adapter_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, "Fixed"
        return False, "No changes needed"

    def fix_battlepass_adapter(self, game_id: int) -> Tuple[bool, str]:
        """Fix battlepass adapter for new mg-common-game API."""
        adapter_path = self.get_game_lib_path(game_id) / "features" / "battlepass" / "battlepass_adapter.dart"

        if not adapter_path.exists():
            return False, "Adapter not found"

        with open(adapter_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Fix incrementMissionProgress
        content = re.sub(
            r'_manager\.incrementMissionProgress\((\w+), (\w+)\)',
            r'_manager.incrementMissionProgress(\1, amount: \2)',
            content
        )

        # Fix setMissions
        content = re.sub(
            r'_manager\.setMissions\(\s*_createDailyMissions\(\),\s*_createWeeklyMissions\(\)\s*\)',
            '_manager.setMissions(daily: _createDailyMissions(), weekly: _createWeeklyMissions())',
            content
        )

        if content != original:
            with open(adapter_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, "Fixed"
        return False, "No changes needed"

    # ==================== Analyze Operations ====================

    def analyze_game(self, game_id: int, path: str = "lib/") -> Tuple[bool, List[str]]:
        """Run flutter analyze on a game."""
        game_path = self.get_game_path(game_id) / "game"

        if not game_path.exists():
            return False, ["Game not found"]

        os.chdir(game_path)
        result = subprocess.run(
            ["flutter", "analyze", path, "--no-fatal-infos"],
            capture_output=True, text=True, timeout=120
        )

        errors = []
        for line in result.stdout.split('\n'):
            if 'error -' in line.lower() or 'error:' in line.lower():
                errors.append(line.strip())

        return len(errors) == 0, errors

    def test_game(self, game_id: int) -> Tuple[bool, str]:
        """Run flutter test on a game."""
        game_path = self.get_game_path(game_id) / "game"

        if not game_path.exists():
            return False, "Game not found"

        os.chdir(game_path)
        result = subprocess.run(
            ["flutter", "test"],
            capture_output=True, text=True, timeout=300
        )

        if result.returncode == 0:
            # Extract test count
            match = re.search(r'\+(\d+)', result.stdout)
            count = match.group(1) if match else "?"
            return True, f"{count} tests passed"
        else:
            return False, result.stderr[:200] if result.stderr else result.stdout[:200]

    # ==================== Build Operations ====================

    def build_game(self, game_id: int, platform: str = "apk", flavor: str = None) -> Tuple[bool, str]:
        """Build a game for the specified platform."""
        game_path = self.get_game_path(game_id) / "game"

        if not game_path.exists():
            return False, "Game not found"

        os.chdir(game_path)

        # Build command based on platform
        if platform == "apk":
            cmd = ["flutter", "build", "apk", "--debug"]
        elif platform == "appbundle":
            cmd = ["flutter", "build", "appbundle", "--debug"]
        elif platform == "ios":
            cmd = ["flutter", "build", "ios", "--debug", "--no-codesign"]
        elif platform == "web":
            cmd = ["flutter", "build", "web"]
        else:
            return False, f"Unknown platform: {platform}"

        if flavor:
            cmd.extend(["--flavor", flavor])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=600  # 10 minute timeout
            )

            if result.returncode == 0:
                return True, f"{platform} build successful"
            else:
                # Extract relevant error
                error_lines = []
                for line in result.stderr.split('\n'):
                    if 'error' in line.lower() or 'exception' in line.lower():
                        error_lines.append(line.strip())
                if not error_lines:
                    error_lines = result.stderr.split('\n')[:3]
                return False, '; '.join(error_lines)[:150]
        except subprocess.TimeoutExpired:
            return False, "Build timed out (10 min)"

    def verify_build(self, game_id: int) -> Tuple[bool, dict]:
        """Verify a game can build (analyze + quick build check)."""
        game_path = self.get_game_path(game_id) / "game"

        if not game_path.exists():
            return False, {"error": "Game not found"}

        results = {
            "analyze": None,
            "pub_get": None,
            "build_runner": None,
        }

        os.chdir(game_path)

        # 1. Pub get
        result = subprocess.run(
            ["flutter", "pub", "get"],
            capture_output=True, text=True, timeout=120
        )
        results["pub_get"] = result.returncode == 0

        if not results["pub_get"]:
            return False, results

        # 2. Analyze
        result = subprocess.run(
            ["flutter", "analyze", "--no-fatal-infos"],
            capture_output=True, text=True, timeout=120
        )
        has_errors = 'error' in result.stdout.lower() and 'error •' in result.stdout.lower()
        results["analyze"] = not has_errors

        # 3. Build runner (if needed)
        pubspec_path = game_path / "pubspec.yaml"
        if pubspec_path.exists():
            with open(pubspec_path, 'r') as f:
                if 'build_runner' in f.read():
                    result = subprocess.run(
                        ["flutter", "pub", "run", "build_runner", "build", "--delete-conflicting-outputs"],
                        capture_output=True, text=True, timeout=300
                    )
                    results["build_runner"] = result.returncode == 0
                else:
                    results["build_runner"] = None  # Not applicable

        all_passed = all(v is True or v is None for v in results.values())
        return all_passed, results

    # ==================== Commit Operations ====================

    def commit_changes(self, game_id: int, message: str) -> Tuple[bool, str]:
        """Commit all changes in a game repository."""
        game_path = self.get_game_path(game_id)

        if not game_path.exists():
            return False, "Game not found"

        os.chdir(game_path)

        # Check for changes
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            return False, "No changes to commit"

        # Add and commit
        subprocess.run(["git", "add", "-A"], capture_output=True)

        full_message = f"{message}\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

        result = subprocess.run(
            ["git", "commit", "-m", full_message],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            return True, "Committed"
        return False, result.stderr[:100]
