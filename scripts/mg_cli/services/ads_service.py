"""Ads SDK configuration service for mg-cli."""

import os
import re
from pathlib import Path
from typing import Tuple, Optional
from jinja2 import Template

from .game_scanner import GameInfo


class AdsService:
    """Handles AdMob SDK configuration."""

    def __init__(self, config):
        self.config = config
        self.templates_path = Path(__file__).parent.parent / "templates"

    def setup_android(self, game_info: GameInfo, app_id: Optional[str] = None,
                      test_mode: bool = True, dry_run: bool = False) -> Tuple[bool, str]:
        """Configure AdMob for Android."""
        manifest_path = (game_info.path / "game" / "android" / "app" /
                        "src" / "main" / "AndroidManifest.xml")

        if not manifest_path.exists():
            return False, f"AndroidManifest.xml not found: {manifest_path}"

        # Use test ID in test mode
        if test_mode or app_id is None:
            app_id = self.config.ads.android_app_id_test

        if dry_run:
            return True, f"[DRY RUN] Would add AdMob app ID to {manifest_path}"

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if already configured
            if 'com.google.android.gms.ads.APPLICATION_ID' in content:
                # Update existing
                content = re.sub(
                    r'android:name="com\.google\.android\.gms\.ads\.APPLICATION_ID"\s+android:value="[^"]+"',
                    f'android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="{app_id}"',
                    content
                )
            else:
                # Add new meta-data before closing </application> tag
                meta_data = f'''
        <meta-data
            android:name="com.google.android.gms.ads.APPLICATION_ID"
            android:value="{app_id}"/>
'''
                content = content.replace('</application>', f'{meta_data}    </application>')

            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True, f"Configured AdMob for Android: {app_id}"

        except Exception as e:
            return False, str(e)

    def setup_ios(self, game_info: GameInfo, app_id: Optional[str] = None,
                  test_mode: bool = True, dry_run: bool = False) -> Tuple[bool, str]:
        """Configure AdMob for iOS."""
        plist_path = game_info.path / "game" / "ios" / "Runner" / "Info.plist"

        if not plist_path.exists():
            return False, f"Info.plist not found: {plist_path}"

        # Use test ID in test mode
        if test_mode or app_id is None:
            app_id = self.config.ads.ios_app_id_test

        if dry_run:
            return True, f"[DRY RUN] Would add AdMob app ID to {plist_path}"

        try:
            with open(plist_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if GADApplicationIdentifier already exists
            if 'GADApplicationIdentifier' in content:
                # Update existing
                content = re.sub(
                    r'<key>GADApplicationIdentifier</key>\s*<string>[^<]+</string>',
                    f'<key>GADApplicationIdentifier</key>\n\t<string>{app_id}</string>',
                    content
                )
            else:
                # Add before closing </dict> (last one, which closes the root)
                gad_entry = f'''
\t<key>GADApplicationIdentifier</key>
\t<string>{app_id}</string>
'''
                # Find the last </dict> before </plist>
                content = re.sub(
                    r'(</dict>\s*</plist>)',
                    f'{gad_entry}\\1',
                    content
                )

            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True, f"Configured AdMob for iOS: {app_id}"

        except Exception as e:
            return False, str(e)

    def add_skadnetwork_ids(self, game_info: GameInfo, dry_run: bool = False) -> Tuple[bool, str]:
        """Add SKAdNetwork IDs to Info.plist."""
        plist_path = game_info.path / "game" / "ios" / "Runner" / "Info.plist"
        skad_template = self.templates_path / "skadnetwork_ids.json"

        if not plist_path.exists():
            return False, f"Info.plist not found: {plist_path}"

        if dry_run:
            return True, f"[DRY RUN] Would add SKAdNetwork IDs to {plist_path}"

        try:
            # Load SKAdNetwork IDs from template
            import json
            if skad_template.exists():
                with open(skad_template, 'r', encoding='utf-8') as f:
                    skad_ids = json.load(f)
            else:
                # Default Google SKAdNetwork IDs
                skad_ids = [
                    "cstr6suwn9.skadnetwork",
                    "4fzdc2evr5.skadnetwork",
                    "2fnua5tdw4.skadnetwork",
                    "ydx93a7ass.skadnetwork",
                    "5a6flpkh64.skadnetwork",
                ]

            with open(plist_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if SKAdNetworkItems already exists
            if 'SKAdNetworkItems' in content:
                return True, "SKAdNetwork IDs already configured"

            # Build SKAdNetwork array
            skad_array = '\n'.join([
                f'\t\t<dict>\n\t\t\t<key>SKAdNetworkIdentifier</key>\n\t\t\t<string>{sid}</string>\n\t\t</dict>'
                for sid in skad_ids
            ])

            skad_entry = f'''
\t<key>SKAdNetworkItems</key>
\t<array>
{skad_array}
\t</array>
'''
            # Add before closing </dict> (last one)
            content = re.sub(
                r'(</dict>\s*</plist>)',
                f'{skad_entry}\\1',
                content
            )

            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True, f"Added {len(skad_ids)} SKAdNetwork IDs"

        except Exception as e:
            return False, str(e)

    def enable_pubspec_deps(self, game_info: GameInfo, dry_run: bool = False) -> Tuple[bool, str]:
        """Enable google_mobile_ads in pubspec.yaml."""
        pubspec_path = game_info.path / "game" / "pubspec.yaml"

        if not pubspec_path.exists():
            return False, f"pubspec.yaml not found: {pubspec_path}"

        if dry_run:
            return True, f"[DRY RUN] Would enable google_mobile_ads in {pubspec_path}"

        try:
            with open(pubspec_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if already enabled
            if 'google_mobile_ads:' in content and '#' not in content.split('google_mobile_ads:')[0].split('\n')[-1]:
                return True, "google_mobile_ads already enabled"

            # Uncomment if commented
            lines = content.split('\n')
            new_lines = []
            modified = False

            for line in lines:
                if '# google_mobile_ads:' in line or '#google_mobile_ads:' in line:
                    new_lines.append(line.lstrip('#').lstrip())
                    modified = True
                else:
                    new_lines.append(line)

            if modified:
                with open(pubspec_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))
                return True, "Enabled google_mobile_ads dependency"

            # If not found at all, we could add it, but that's more complex
            return False, "google_mobile_ads not found in pubspec.yaml (even commented)"

        except Exception as e:
            return False, str(e)

    def setup_game(self, game_info: GameInfo, test_mode: bool = True,
                   dry_run: bool = False) -> Tuple[bool, str]:
        """Full AdMob setup for a game."""
        results = []

        # Android setup
        success, msg = self.setup_android(game_info, test_mode=test_mode, dry_run=dry_run)
        results.append(f"Android: {msg}")

        # iOS setup
        success, msg = self.setup_ios(game_info, test_mode=test_mode, dry_run=dry_run)
        results.append(f"iOS: {msg}")

        # SKAdNetwork IDs
        success, msg = self.add_skadnetwork_ids(game_info, dry_run=dry_run)
        results.append(f"SKAdNetwork: {msg}")

        # Enable dependency
        success, msg = self.enable_pubspec_deps(game_info, dry_run=dry_run)
        results.append(f"Dependency: {msg}")

        return True, "\n".join(results)

    def get_status(self, game_info: GameInfo) -> dict:
        """Get AdMob configuration status for a game."""
        return {
            'game_id': game_info.game_id,
            'has_config': game_info.has_admob_config,
            'android_app_id': game_info.admob_app_id_android,
            'ios_app_id': game_info.admob_app_id_ios,
        }
