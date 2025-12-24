"""Firebase configuration service for mg-cli."""

import os
import subprocess
import json
from pathlib import Path
from typing import Tuple, Optional, List
from jinja2 import Template

from .game_scanner import GameInfo


class FirebaseService:
    """Handles Firebase project creation and configuration."""

    def __init__(self, config):
        self.config = config
        self.templates_path = Path(__file__).parent.parent / "templates"

    def _run_cmd(self, cmd: list, cwd: str = None) -> subprocess.CompletedProcess:
        """Run a subprocess command with proper encoding."""
        return subprocess.run(
            cmd,
            capture_output=True,
            shell=True,
            cwd=cwd,
            encoding='utf-8',
            errors='replace'
        )

    def check_cli_installed(self) -> Tuple[bool, str]:
        """Check if Firebase CLI is installed."""
        try:
            result = self._run_cmd(["firebase", "--version"])
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, "Firebase CLI not found"
        except Exception as e:
            return False, str(e)

    def check_flutterfire_installed(self) -> Tuple[bool, str]:
        """Check if FlutterFire CLI is installed."""
        try:
            result = self._run_cmd(["flutterfire", "--version"])
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, "FlutterFire CLI not found"
        except Exception as e:
            return False, str(e)

    def list_projects(self) -> Tuple[bool, List[str]]:
        """List existing Firebase projects."""
        try:
            result = self._run_cmd(["firebase", "projects:list", "--json"])
            if result.returncode == 0:
                data = json.loads(result.stdout)
                projects = [p.get('projectId', '') for p in data.get('result', [])]
                return True, projects
            return False, []
        except Exception as e:
            print(f"Error listing projects: {e}")
            return False, []

    def create_project(self, game_id: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Create a Firebase project for a game."""
        project_id = f"mg-game-{game_id}"
        display_name = f"MG Game {game_id}"

        if dry_run:
            return True, f"[DRY RUN] Would create project: {project_id}"

        try:
            result = self._run_cmd([
                "firebase", "projects:create", project_id,
                "--display-name", display_name
            ])
            if result.returncode == 0:
                return True, f"Created project: {project_id}"
            return False, result.stderr

        except Exception as e:
            return False, str(e)

    def register_apps(self, game_id: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Register Android and iOS apps for a Firebase project."""
        project_id = f"mg-game-{game_id}"
        package_name = f"com.monthlygames.game{game_id}"
        bundle_id = f"com.monthlygames.game{game_id}"

        if dry_run:
            return True, f"[DRY RUN] Would register apps for {project_id}: {package_name}"

        messages = []

        # Register Android app
        try:
            result = self._run_cmd([
                "firebase", "apps:create", "ANDROID",
                "--package-name", package_name,
                "--project", project_id
            ])
            if result.returncode == 0:
                messages.append(f"Registered Android app: {package_name}")
            else:
                messages.append(f"Android registration failed: {result.stderr}")
        except Exception as e:
            messages.append(f"Android error: {e}")

        # Register iOS app
        try:
            result = self._run_cmd([
                "firebase", "apps:create", "IOS",
                "--bundle-id", bundle_id,
                "--project", project_id
            ])
            if result.returncode == 0:
                messages.append(f"Registered iOS app: {bundle_id}")
            else:
                messages.append(f"iOS registration failed: {result.stderr}")
        except Exception as e:
            messages.append(f"iOS error: {e}")

        return True, "\n".join(messages)

    def generate_firebase_options(self, game_info: GameInfo, dry_run: bool = False) -> Tuple[bool, str]:
        """Generate firebase_options.dart from template."""
        template_path = self.templates_path / "firebase_options.dart.j2"

        if not template_path.exists():
            return False, f"Template not found: {template_path}"

        game_dir = game_info.path / "game"
        output_path = game_dir / "lib" / "firebase_options.dart"

        if dry_run:
            return True, f"[DRY RUN] Would generate: {output_path}"

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())

            # Generate placeholder values (real values come from flutterfire configure)
            content = template.render(
                game_id=game_info.game_id,
                project_id=self.config.get_firebase_project_id(int(game_info.game_id)),
                android_app_id=f"1:000000000000:android:placeholder{game_info.game_id}",
                ios_app_id=f"1:000000000000:ios:placeholder{game_info.game_id}",
                api_key_android="PLACEHOLDER_API_KEY",
                api_key_ios="PLACEHOLDER_API_KEY",
                messaging_sender_id="000000000000",
                storage_bucket=f"mg-game-{game_info.game_id}.appspot.com",
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True, f"Generated: {output_path}"

        except Exception as e:
            return False, str(e)

    def run_flutterfire_configure(self, game_info: GameInfo, dry_run: bool = False) -> Tuple[bool, str]:
        """Run flutterfire configure for a game."""
        game_dir = game_info.path / "game"
        project_id = self.config.get_firebase_project_id(int(game_info.game_id))

        if dry_run:
            return True, f"[DRY RUN] Would run flutterfire configure in {game_dir}"

        try:
            result = self._run_cmd([
                "flutterfire", "configure",
                "--project", project_id,
                "--platforms", "android,ios",
                "--yes"
            ], cwd=str(game_dir))
            if result.returncode == 0:
                return True, f"FlutterFire configured for {game_info.game_id}"
            return False, result.stderr

        except Exception as e:
            return False, str(e)

    def enable_pubspec_deps(self, game_info: GameInfo, dry_run: bool = False) -> Tuple[bool, str]:
        """Enable Firebase dependencies in pubspec.yaml by uncommenting."""
        pubspec_path = game_info.path / "game" / "pubspec.yaml"

        if not pubspec_path.exists():
            return False, f"pubspec.yaml not found: {pubspec_path}"

        if dry_run:
            return True, f"[DRY RUN] Would enable Firebase deps in {pubspec_path}"

        try:
            with open(pubspec_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Firebase dependencies to uncomment
            firebase_deps = [
                'firebase_core',
                'firebase_analytics',
                'firebase_crashlytics',
                'firebase_remote_config',
            ]

            modified = False
            lines = content.split('\n')
            new_lines = []

            for line in lines:
                new_line = line
                for dep in firebase_deps:
                    # Match commented dependency
                    if f'# {dep}:' in line or f'#{dep}:' in line:
                        new_line = line.lstrip('#').lstrip()
                        modified = True
                        break
                new_lines.append(new_line)

            if modified:
                with open(pubspec_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))
                return True, f"Enabled Firebase deps in {pubspec_path}"

            return True, "Firebase deps already enabled or not found"

        except Exception as e:
            return False, str(e)

    def get_status(self, game_info: GameInfo) -> dict:
        """Get Firebase configuration status for a game."""
        return {
            'game_id': game_info.game_id,
            'firebase_options': game_info.has_firebase_options,
            'google_services_json': game_info.has_google_services_json,
            'google_service_info_plist': game_info.has_google_service_info_plist,
            'deps_enabled': game_info.firebase_deps_enabled,
            'ready': all([
                game_info.has_firebase_options,
                game_info.has_google_services_json,
                game_info.firebase_deps_enabled
            ])
        }
