"""
Firebase Service

Handles Firebase configuration for MG Games projects.
- Creates firebase_options.dart
- Enables Firebase dependencies in pubspec.yaml
- Generates google-services.json and GoogleService-Info.plist templates
- Creates Firebase projects via Firebase CLI
- Configures apps via FlutterFire CLI
"""

import os
import re
import subprocess
import shutil
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from ..config import get_config, Config
from .game_scanner import GameInfo


class FirebaseService:
    """Firebase configuration service"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self._firebase_cli = self._find_firebase_cli()
        self._flutterfire_cli = self._find_flutterfire_cli()

    def _find_firebase_cli(self) -> Optional[str]:
        """Find Firebase CLI executable"""
        # Try common locations
        if shutil.which("firebase"):
            return "firebase"
        # Windows npm global
        npm_path = Path(os.environ.get("APPDATA", "")) / "npm" / "firebase.cmd"
        if npm_path.exists():
            return str(npm_path)
        return None

    def _find_flutterfire_cli(self) -> Optional[str]:
        """Find FlutterFire CLI executable"""
        if shutil.which("flutterfire"):
            return "flutterfire"
        # Dart pub global
        dart_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Pub" / "Cache" / "bin" / "flutterfire.bat"
        if dart_path.exists():
            return str(dart_path)
        return None

    def check_cli_available(self) -> Tuple[bool, str]:
        """Check if Firebase CLI is available"""
        if not self._firebase_cli:
            return False, "Firebase CLI not found. Install with: npm install -g firebase-tools"
        try:
            result = subprocess.run(
                [self._firebase_cli, "--version"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, f"Firebase CLI {result.stdout.strip()}"
            return False, "Firebase CLI check failed"
        except Exception as e:
            return False, str(e)

    def check_flutterfire_available(self) -> Tuple[bool, str]:
        """Check if FlutterFire CLI is available"""
        if not self._flutterfire_cli:
            return False, "FlutterFire CLI not found. Install with: dart pub global activate flutterfire_cli"
        try:
            result = subprocess.run(
                [self._flutterfire_cli, "--version"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, f"FlutterFire CLI {result.stdout.strip()}"
            return False, "FlutterFire CLI check failed"
        except Exception as e:
            return False, str(e)

    def list_projects(self) -> Tuple[bool, List[str]]:
        """List existing Firebase projects"""
        if not self._firebase_cli:
            return False, ["Firebase CLI not available"]

        try:
            result = subprocess.run(
                [self._firebase_cli, "projects:list", "--json"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                projects = [p.get("projectId", "") for p in data.get("result", [])]
                return True, projects
            return False, [result.stderr]
        except json.JSONDecodeError:
            # Parse non-JSON output
            return True, []
        except Exception as e:
            return False, [str(e)]

    def create_project(self, game_id: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Create a Firebase project for a game

        Args:
            game_id: Game ID (e.g., "0001")
            dry_run: If True, don't actually create

        Returns:
            Tuple of (success, message)
        """
        if not self._firebase_cli:
            return False, "Firebase CLI not available"

        project_id = f"mg-game-{game_id}"
        display_name = f"MG Game {game_id}"

        if dry_run:
            return True, f"[DRY-RUN] Would create project: {project_id}"

        # Check if project already exists
        success, projects = self.list_projects()
        if success and project_id in projects:
            return True, f"Project {project_id} already exists"

        try:
            result = subprocess.run(
                [self._firebase_cli, "projects:create", project_id,
                 "--display-name", display_name],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, f"Project {project_id} created"
            elif "already exists" in result.stderr.lower():
                return True, f"Project {project_id} already exists"
            else:
                return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Timeout creating project"
        except Exception as e:
            return False, str(e)

    def register_android_app(self, game_id: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Register Android app in Firebase project"""
        if not self._firebase_cli:
            return False, "Firebase CLI not available"

        project_id = f"mg-game-{game_id}"
        package_name = f"com.monthlygames.game{game_id}"

        if dry_run:
            return True, f"[DRY-RUN] Would register Android app: {package_name}"

        try:
            result = subprocess.run(
                [self._firebase_cli, "apps:create", "ANDROID",
                 "--package-name", package_name,
                 "--project", project_id],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, f"Android app registered: {package_name}"
            elif "already exists" in result.stderr.lower():
                return True, f"Android app already exists"
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def register_ios_app(self, game_id: str, dry_run: bool = False) -> Tuple[bool, str]:
        """Register iOS app in Firebase project"""
        if not self._firebase_cli:
            return False, "Firebase CLI not available"

        project_id = f"mg-game-{game_id}"
        bundle_id = f"com.monthlygames.game{game_id}"

        if dry_run:
            return True, f"[DRY-RUN] Would register iOS app: {bundle_id}"

        try:
            result = subprocess.run(
                [self._firebase_cli, "apps:create", "IOS",
                 "--bundle-id", bundle_id,
                 "--project", project_id],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return True, f"iOS app registered: {bundle_id}"
            elif "already exists" in result.stderr.lower():
                return True, f"iOS app already exists"
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def run_flutterfire_configure(
        self, game_info: GameInfo, dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Run flutterfire configure for a game

        This downloads actual API keys and generates firebase_options.dart
        """
        if not self._flutterfire_cli:
            return False, "FlutterFire CLI not available"

        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        project_id = f"mg-game-{game_info.game_id}"

        if dry_run:
            return True, f"[DRY-RUN] Would run flutterfire configure for {project_id}"

        try:
            result = subprocess.run(
                [self._flutterfire_cli, "configure",
                 "--project", project_id,
                 "--platforms", "android,ios",
                 "--yes"],  # Auto-accept prompts
                cwd=str(game_dir),
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                return True, "FlutterFire configured successfully"
            else:
                return False, result.stderr.strip() or result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Timeout running flutterfire configure"
        except Exception as e:
            return False, str(e)

    def create_and_configure(
        self, game_info: GameInfo, dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Create Firebase project and configure app (full setup)

        Args:
            game_info: Game information
            dry_run: If True, don't actually make changes

        Returns:
            Tuple of (success, message)
        """
        results = []
        game_id = game_info.game_id

        # 1. Create Firebase project
        success, msg = self.create_project(game_id, dry_run)
        results.append(f"Project: {msg}")
        if not success and "already exists" not in msg.lower():
            return False, "; ".join(results)

        # Wait a bit for project to be ready
        if not dry_run:
            time.sleep(2)

        # 2. Register Android app
        success, msg = self.register_android_app(game_id, dry_run)
        results.append(f"Android: {msg}")

        # 3. Register iOS app
        success, msg = self.register_ios_app(game_id, dry_run)
        results.append(f"iOS: {msg}")

        # Wait for apps to be ready
        if not dry_run:
            time.sleep(2)

        # 4. Run flutterfire configure
        success, msg = self.run_flutterfire_configure(game_info, dry_run)
        results.append(f"FlutterFire: {msg}")

        return True, "; ".join(results)

    def init_firebase(self, game_info: GameInfo, force: bool = False) -> Tuple[bool, str]:
        """Initialize Firebase for a game

        Args:
            game_info: Game information
            force: Force overwrite existing config

        Returns:
            Tuple of (success, message)
        """
        if not game_info.exists:
            return False, "Game does not exist"

        game_dir = game_info.path / "game"
        if not game_dir.exists():
            return False, "Game directory not found"

        results = []

        # 1. Enable Firebase dependencies in pubspec.yaml
        success, msg = self._enable_firebase_deps(game_dir)
        results.append(f"pubspec.yaml: {msg}")

        # 2. Create firebase_options.dart
        success, msg = self._create_firebase_options(game_info, game_dir, force)
        results.append(f"firebase_options.dart: {msg}")

        # 3. Create google-services.json template if not exists
        success, msg = self._create_google_services(game_info, game_dir, force)
        results.append(f"google-services.json: {msg}")

        # 4. Create GoogleService-Info.plist template if not exists
        success, msg = self._create_google_service_info(game_info, game_dir, force)
        results.append(f"GoogleService-Info.plist: {msg}")

        return True, "; ".join(results)

    def _enable_firebase_deps(self, game_dir: Path) -> Tuple[bool, str]:
        """Enable Firebase dependencies in pubspec.yaml"""
        pubspec_path = game_dir / "pubspec.yaml"
        if not pubspec_path.exists():
            return False, "pubspec.yaml not found"

        content = pubspec_path.read_text(encoding="utf-8")
        original_content = content

        # Uncomment firebase_core
        content = re.sub(
            r"#\s*(firebase_core:\s*\^[\d.]+)",
            r"\1",
            content
        )

        # Uncomment firebase_analytics
        content = re.sub(
            r"#\s*(firebase_analytics:\s*\^[\d.]+)",
            r"\1",
            content
        )

        # Uncomment firebase_crashlytics
        content = re.sub(
            r"#\s*(firebase_crashlytics:\s*\^[\d.]+)",
            r"\1",
            content
        )

        if content == original_content:
            return True, "already enabled or no commented deps"

        pubspec_path.write_text(content, encoding="utf-8")
        return True, "enabled"

    def _create_firebase_options(
        self, game_info: GameInfo, game_dir: Path, force: bool
    ) -> Tuple[bool, str]:
        """Create firebase_options.dart file"""
        lib_dir = game_dir / "lib"
        options_path = lib_dir / "firebase_options.dart"

        if options_path.exists() and not force:
            return True, "already exists"

        project_id = self.config.get_firebase_project_id(game_info.game_id)
        game_id = game_info.game_id

        content = FIREBASE_OPTIONS_TEMPLATE.format(
            project_id=project_id,
            game_id=game_id,
            android_app_id=f"1:000000000000:android:{game_id}",
            ios_app_id=f"1:000000000000:ios:{game_id}",
            web_app_id=f"1:000000000000:web:{game_id}",
            api_key_android="YOUR_ANDROID_API_KEY",
            api_key_ios="YOUR_IOS_API_KEY",
            api_key_web="YOUR_WEB_API_KEY",
            messaging_sender_id="000000000000",
            storage_bucket=f"{project_id}.appspot.com",
        )

        lib_dir.mkdir(parents=True, exist_ok=True)
        options_path.write_text(content, encoding="utf-8")
        return True, "created"

    def _create_google_services(
        self, game_info: GameInfo, game_dir: Path, force: bool
    ) -> Tuple[bool, str]:
        """Create google-services.json for Android"""
        android_app_dir = game_dir / "android" / "app"
        json_path = android_app_dir / "google-services.json"

        if json_path.exists() and not force:
            return True, "already exists"

        project_id = self.config.get_firebase_project_id(game_info.game_id)

        content = GOOGLE_SERVICES_TEMPLATE.format(
            project_id=project_id,
            project_number="000000000000",
            package_name=f"com.monthlygames.game{game_info.game_id}",
            app_id=f"1:000000000000:android:game{game_info.game_id}",
            api_key="YOUR_ANDROID_API_KEY",
            storage_bucket=f"{project_id}.appspot.com",
        )

        android_app_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(content, encoding="utf-8")
        return True, "created"

    def _create_google_service_info(
        self, game_info: GameInfo, game_dir: Path, force: bool
    ) -> Tuple[bool, str]:
        """Create GoogleService-Info.plist for iOS"""
        ios_runner_dir = game_dir / "ios" / "Runner"
        plist_path = ios_runner_dir / "GoogleService-Info.plist"

        if plist_path.exists() and not force:
            return True, "already exists"

        project_id = self.config.get_firebase_project_id(game_info.game_id)

        content = GOOGLE_SERVICE_INFO_TEMPLATE.format(
            project_id=project_id,
            bundle_id=f"com.monthlygames.game{game_info.game_id}",
            app_id=f"1:000000000000:ios:game{game_info.game_id}",
            api_key="YOUR_IOS_API_KEY",
            gc_sender_id="000000000000",
            storage_bucket=f"{project_id}.appspot.com",
        )

        ios_runner_dir.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(content, encoding="utf-8")
        return True, "created"


# Template for firebase_options.dart
FIREBASE_OPTIONS_TEMPLATE = '''// File generated by MG-CLI
// Do not edit manually

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {{
  static FirebaseOptions get currentPlatform {{
    if (kIsWeb) {{
      return web;
    }}
    switch (defaultTargetPlatform) {{
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      case TargetPlatform.macOS:
        throw UnsupportedError('macOS is not supported');
      case TargetPlatform.windows:
        throw UnsupportedError('Windows is not supported');
      case TargetPlatform.linux:
        throw UnsupportedError('Linux is not supported');
      default:
        throw UnsupportedError('Unknown platform');
    }}
  }}

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: '{api_key_android}',
    appId: '{android_app_id}',
    messagingSenderId: '{messaging_sender_id}',
    projectId: '{project_id}',
    storageBucket: '{storage_bucket}',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: '{api_key_ios}',
    appId: '{ios_app_id}',
    messagingSenderId: '{messaging_sender_id}',
    projectId: '{project_id}',
    storageBucket: '{storage_bucket}',
    iosBundleId: 'com.monthlygames.game{game_id}',
  );

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: '{api_key_web}',
    appId: '{web_app_id}',
    messagingSenderId: '{messaging_sender_id}',
    projectId: '{project_id}',
    storageBucket: '{storage_bucket}',
    authDomain: '{project_id}.firebaseapp.com',
  );
}}
'''

# Template for google-services.json
GOOGLE_SERVICES_TEMPLATE = '''{{
  "project_info": {{
    "project_number": "{project_number}",
    "project_id": "{project_id}",
    "storage_bucket": "{storage_bucket}"
  }},
  "client": [
    {{
      "client_info": {{
        "mobilesdk_app_id": "{app_id}",
        "android_client_info": {{
          "package_name": "{package_name}"
        }}
      }},
      "oauth_client": [],
      "api_key": [
        {{
          "current_key": "{api_key}"
        }}
      ],
      "services": {{
        "appinvite_service": {{
          "other_platform_oauth_client": []
        }}
      }}
    }}
  ],
  "configuration_version": "1"
}}'''

# Template for GoogleService-Info.plist
GOOGLE_SERVICE_INFO_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>API_KEY</key>
    <string>{api_key}</string>
    <key>GCM_SENDER_ID</key>
    <string>{gc_sender_id}</string>
    <key>PLIST_VERSION</key>
    <string>1</string>
    <key>BUNDLE_ID</key>
    <string>{bundle_id}</string>
    <key>PROJECT_ID</key>
    <string>{project_id}</string>
    <key>STORAGE_BUCKET</key>
    <string>{storage_bucket}</string>
    <key>IS_ADS_ENABLED</key>
    <false/>
    <key>IS_ANALYTICS_ENABLED</key>
    <true/>
    <key>IS_APPINVITE_ENABLED</key>
    <true/>
    <key>IS_GCM_ENABLED</key>
    <true/>
    <key>IS_SIGNIN_ENABLED</key>
    <true/>
    <key>GOOGLE_APP_ID</key>
    <string>{app_id}</string>
</dict>
</plist>'''
