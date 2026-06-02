"""
Ads Service

Handles Ads SDK configuration for MG Games projects.
- Adds google_mobile_ads dependency
- Configures AndroidManifest.xml with AdMob App ID
- Configures Info.plist with GADApplicationIdentifier
- Adds SKAdNetwork IDs for iOS
"""

import re
from pathlib import Path
from typing import Optional, Tuple
import xml.etree.ElementTree as ET

from ..config import get_config, Config, ADMOB_TEST_IDS
from .game_scanner import GameInfo


class AdsService:
    """Ads SDK configuration service"""

    # SKAdNetwork IDs for Google AdMob
    SKADNETWORK_IDS = [
        "cstr6suwn9.skadnetwork",  # Google
        "4fzdc2evr5.skadnetwork",
        "4pfyvq9l8r.skadnetwork",
        "2fnua5tdw4.skadnetwork",
        "ydx93a7ass.skadnetwork",
        "5a6flpkh64.skadnetwork",
        "p78axxw29g.skadnetwork",
        "v72qych5uu.skadnetwork",
        "ludvb6z3bs.skadnetwork",
        "cp8zw746q7.skadnetwork",
        "c6k4g5qg8m.skadnetwork",
        "s39g8k73mm.skadnetwork",
        "3qy4746246.skadnetwork",
        "3sh42y64q3.skadnetwork",
        "f38h382jlk.skadnetwork",
        "hs6bdukanm.skadnetwork",
        "prcb7njmu6.skadnetwork",
        "v4nxqhlyqp.skadnetwork",
        "wzmmz9fp6w.skadnetwork",
        "yclnxrl5pm.skadnetwork",
        "t38b2kh725.skadnetwork",
        "7ug5zh24hu.skadnetwork",
        "9rd848q2bz.skadnetwork",
        "y5ghdn5j9k.skadnetwork",
        "n6fk4nfna4.skadnetwork",
        "v9wttpbfk9.skadnetwork",
        "n38lu8286q.skadnetwork",
        "47vhws6wlr.skadnetwork",
        "kbd757ywx3.skadnetwork",
        "9t245vhmpl.skadnetwork",
        "a2p9lx4jpn.skadnetwork",
        "22mmun2rn5.skadnetwork",
        "4468km3ulz.skadnetwork",
        "2u9pt9hc89.skadnetwork",
        "8s468mfl3y.skadnetwork",
        "av6w8kgt66.skadnetwork",
        "klf5c3l5u5.skadnetwork",
        "ppxm28t8ap.skadnetwork",
        "424m5254lk.skadnetwork",
        "ecpz2srf59.skadnetwork",
        "uw77j35x4d.skadnetwork",
        "mlmmfzh3r3.skadnetwork",
        "578prtvx9j.skadnetwork",
        "4dzt52r2t5.skadnetwork",
        "gta9lk7p23.skadnetwork",
        "e5fvkxwrpn.skadnetwork",
        "8c4e2ghe7u.skadnetwork",
        "zq492l623r.skadnetwork",
        "3rd42ekr43.skadnetwork",
        "3qcr597p9d.skadnetwork",
    ]

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()

    def setup_ads(self, game_info: GameInfo, force: bool = False) -> Tuple[bool, str]:
        """Setup AdMob for a game

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

        # 1. Enable ads dependencies in pubspec.yaml
        success, msg = self._enable_ads_deps(game_dir)
        results.append(f"pubspec: {msg}")

        # 2. Configure AndroidManifest.xml
        success, msg = self._configure_android_manifest(game_info, game_dir)
        results.append(f"Android: {msg}")

        # 3. Configure Info.plist
        success, msg = self._configure_info_plist(game_info, game_dir)
        results.append(f"iOS: {msg}")

        return True, "; ".join(results)

    def setup_game(
        self,
        game_info: GameInfo,
        test_mode: Optional[bool] = None,
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """Compatibility wrapper used by the click commands."""
        if dry_run:
            return True, f"[DRY RUN] Would setup AdMob for MG-{game_info.game_id}"
        return self.setup_ads(game_info)

    def _enable_ads_deps(self, game_dir: Path) -> Tuple[bool, str]:
        """Enable google_mobile_ads dependency in pubspec.yaml"""
        pubspec_path = game_dir / "pubspec.yaml"
        if not pubspec_path.exists():
            return False, "pubspec.yaml not found"

        content = pubspec_path.read_text(encoding="utf-8")
        original_content = content

        # Uncomment google_mobile_ads
        content = re.sub(
            r"#\s*(google_mobile_ads:\s*\^[\d.]+)",
            r"\1",
            content
        )

        # If not found as commented, check if it exists or add it
        if "google_mobile_ads:" not in content:
            # Add after dependencies:
            content = re.sub(
                r"(dependencies:\s*\n)",
                r"\1  google_mobile_ads: ^5.2.0\n",
                content
            )

        if content == original_content:
            return True, "already enabled"

        pubspec_path.write_text(content, encoding="utf-8")
        return True, "enabled"

    def _configure_android_manifest(
        self, game_info: GameInfo, game_dir: Path
    ) -> Tuple[bool, str]:
        """Add AdMob App ID to AndroidManifest.xml"""
        manifest_path = game_dir / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        if not manifest_path.exists():
            return False, "manifest not found"

        content = manifest_path.read_text(encoding="utf-8")

        # Check if already configured
        if "com.google.android.gms.ads.APPLICATION_ID" in content:
            return True, "already configured"

        # Get AdMob App ID
        admob_ids = self.config.get_admob_ids("android")
        app_id = admob_ids.get("app_id", ADMOB_TEST_IDS["android"]["app_id"])

        # Add meta-data before closing application tag
        meta_data = f'''
        <meta-data
            android:name="com.google.android.gms.ads.APPLICATION_ID"
            android:value="{app_id}"/>'''

        content = content.replace(
            "</application>",
            f"{meta_data}\n    </application>"
        )

        manifest_path.write_text(content, encoding="utf-8")
        return True, "configured"

    def _configure_info_plist(
        self, game_info: GameInfo, game_dir: Path
    ) -> Tuple[bool, str]:
        """Add GADApplicationIdentifier to Info.plist and SKAdNetwork IDs"""
        plist_path = game_dir / "ios" / "Runner" / "Info.plist"
        if not plist_path.exists():
            return False, "Info.plist not found"

        content = plist_path.read_text(encoding="utf-8")

        # Check if already configured
        if "GADApplicationIdentifier" in content:
            return True, "already configured"

        # Get AdMob App ID
        admob_ids = self.config.get_admob_ids("ios")
        app_id = admob_ids.get("app_id", ADMOB_TEST_IDS["ios"]["app_id"])

        # Build SKAdNetwork items
        skad_items = "\n".join([
            f"        <dict>\n            <key>SKAdNetworkIdentifier</key>\n            <string>{sid}</string>\n        </dict>"
            for sid in self.SKADNETWORK_IDS
        ])

        # Add before closing dict tag
        additions = f'''
    <key>GADApplicationIdentifier</key>
    <string>{app_id}</string>
    <key>SKAdNetworkItems</key>
    <array>
{skad_items}
    </array>'''

        # Find the last </dict> and insert before it
        content = content.replace(
            "</dict>\n</plist>",
            f"{additions}\n</dict>\n</plist>"
        )

        plist_path.write_text(content, encoding="utf-8")
        return True, "configured"

    def get_status(self, game_info: GameInfo) -> dict:
        """Get AdMob configuration status for a game."""
        android_id = None
        manifest_path = game_info.path / "game" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        if manifest_path.exists():
            content = manifest_path.read_text(encoding="utf-8")
            match = re.search(
                r'android:name="com\.google\.android\.gms\.ads\.APPLICATION_ID"\s+android:value="([^"]+)"',
                content,
            )
            if match:
                android_id = match.group(1)

        return {
            "game_id": game_info.game_id,
            "has_config": game_info.has_admob_android,
            "android_app_id": android_id,
            "deps_enabled": game_info.ads_deps_enabled,
            "ready": game_info.ads_ready,
        }
