"""
Firebase Service

Handles Firebase configuration for MG Games projects.
- Creates firebase_options.dart
- Enables Firebase dependencies in pubspec.yaml
- Generates google-services.json and GoogleService-Info.plist templates
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from jinja2 import Template

from ..config import get_config, Config
from .game_scanner import GameInfo


class FirebaseService:
    """Firebase configuration service"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

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
