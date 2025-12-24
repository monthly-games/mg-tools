"""Game repository scanner for mg-cli."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import json
import yaml


@dataclass
class GameInfo:
    """Information about a game repository."""
    game_id: str  # e.g., "0001"
    path: Path
    title_kr: str = ""
    title_en: str = ""
    genre_tags: List[str] = field(default_factory=list)

    # Firebase status
    has_firebase_options: bool = False
    has_google_services_json: bool = False
    has_google_service_info_plist: bool = False
    firebase_deps_enabled: bool = False

    # Ads status
    has_admob_config: bool = False
    admob_app_id_android: Optional[str] = None
    admob_app_id_ios: Optional[str] = None

    # General status
    exists: bool = True
    has_pubspec: bool = False
    has_docs: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'game_id': self.game_id,
            'path': str(self.path),
            'title_kr': self.title_kr,
            'title_en': self.title_en,
            'genre_tags': self.genre_tags,
            'firebase': {
                'has_options': self.has_firebase_options,
                'has_google_services': self.has_google_services_json,
                'has_plist': self.has_google_service_info_plist,
                'deps_enabled': self.firebase_deps_enabled,
            },
            'ads': {
                'has_config': self.has_admob_config,
                'android_app_id': self.admob_app_id_android,
                'ios_app_id': self.admob_app_id_ios,
            },
            'status': {
                'exists': self.exists,
                'has_pubspec': self.has_pubspec,
                'has_docs': self.has_docs,
            }
        }


class GameScanner:
    """Scans game repositories for status information."""

    def __init__(self, repos_path: Path):
        self.repos_path = repos_path

    def scan_game(self, game_id: int) -> GameInfo:
        """Scan a single game repository."""
        game_id_str = f"{game_id:04d}"
        game_path = self.repos_path / f"mg-game-{game_id_str}"

        info = GameInfo(
            game_id=game_id_str,
            path=game_path,
            exists=game_path.exists()
        )

        if not info.exists:
            return info

        game_dir = game_path / "game"

        # Check pubspec.yaml
        pubspec_path = game_dir / "pubspec.yaml"
        info.has_pubspec = pubspec_path.exists()

        if info.has_pubspec:
            self._parse_pubspec(pubspec_path, info)

        # Check docs
        docs_path = game_path / "docs"
        info.has_docs = docs_path.exists() and any(docs_path.iterdir())

        # Parse production_design.md for metadata
        prod_design = docs_path / "production_design.md"
        if prod_design.exists():
            self._parse_production_design(prod_design, info)

        # Check Firebase files
        info.has_firebase_options = (game_dir / "lib" / "firebase_options.dart").exists()
        info.has_google_services_json = (game_dir / "android" / "app" / "google-services.json").exists()
        info.has_google_service_info_plist = (game_dir / "ios" / "Runner" / "GoogleService-Info.plist").exists()

        # Check AdMob config in AndroidManifest.xml
        manifest_path = game_dir / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        if manifest_path.exists():
            self._check_admob_manifest(manifest_path, info)

        return info

    def scan_all(self, game_ids: List[int]) -> List[GameInfo]:
        """Scan multiple games."""
        return [self.scan_game(gid) for gid in game_ids]

    def _parse_pubspec(self, pubspec_path: Path, info: GameInfo):
        """Parse pubspec.yaml for dependency info."""
        try:
            with open(pubspec_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check for Firebase dependencies (not commented out)
            firebase_deps = ['firebase_core', 'firebase_analytics', 'firebase_crashlytics']
            for dep in firebase_deps:
                # Check if dependency exists and is not commented
                if f'{dep}:' in content:
                    lines = content.split('\n')
                    for line in lines:
                        if dep in line and not line.strip().startswith('#'):
                            info.firebase_deps_enabled = True
                            break

            # Check for google_mobile_ads
            if 'google_mobile_ads:' in content:
                lines = content.split('\n')
                for line in lines:
                    if 'google_mobile_ads' in line and not line.strip().startswith('#'):
                        info.has_admob_config = True
                        break

        except Exception as e:
            print(f"Error parsing pubspec: {e}")

    def _parse_production_design(self, md_path: Path, info: GameInfo):
        """Parse production_design.md for metadata."""
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            for line in lines:
                if line.startswith('> title_kr:'):
                    info.title_kr = line.split(':', 1)[1].strip()
                elif line.startswith('> title_en:'):
                    info.title_en = line.split(':', 1)[1].strip()
                elif line.startswith('> genre_tags:'):
                    tags = line.split(':', 1)[1].strip()
                    info.genre_tags = [t.strip() for t in tags.split(',')]

        except Exception as e:
            print(f"Error parsing production_design: {e}")

    def _check_admob_manifest(self, manifest_path: Path, info: GameInfo):
        """Check AndroidManifest.xml for AdMob app ID."""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'com.google.android.gms.ads.APPLICATION_ID' in content:
                info.has_admob_config = True
                # Extract app ID if present
                import re
                match = re.search(r'android:value="(ca-app-pub-[^"]+)"', content)
                if match:
                    info.admob_app_id_android = match.group(1)

        except Exception as e:
            print(f"Error checking manifest: {e}")

    def get_summary(self, games: List[GameInfo]) -> Dict[str, Any]:
        """Get summary statistics for scanned games."""
        total = len(games)
        existing = sum(1 for g in games if g.exists)
        with_firebase = sum(1 for g in games if g.has_firebase_options)
        with_admob = sum(1 for g in games if g.has_admob_config)
        with_docs = sum(1 for g in games if g.has_docs)

        return {
            'total_configured': total,
            'existing': existing,
            'missing': total - existing,
            'firebase': {
                'with_options': with_firebase,
                'with_google_services': sum(1 for g in games if g.has_google_services_json),
                'deps_enabled': sum(1 for g in games if g.firebase_deps_enabled),
            },
            'ads': {
                'with_admob': with_admob,
            },
            'docs': {
                'with_docs': with_docs,
            }
        }
