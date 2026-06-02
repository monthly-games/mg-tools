"""
Game Scanner Service

Scans and collects information about all MG games in the repository.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Sequence
from enum import Enum

from ..config import DEFAULT_REPOS_PATH, SUBMODULE_PATHS


class SubmoduleType(Enum):
    """Type of mg_common_game submodule structure"""
    NONE = "none"
    LEGACY = "legacy"  # common/game
    NEW = "new"        # libs/mg_common_game


@dataclass
class GameInfo:
    """Information about a single game"""
    game_id: str                    # "0001", "0025", etc.
    name: str                       # Full name "mg-game-0001"
    path: Path                      # Full path to game repo
    exists: bool = True

    # Structure info
    submodule_type: SubmoduleType = SubmoduleType.NONE
    has_game_dir: bool = False
    has_pubspec: bool = False

    # Firebase status
    has_firebase_json: bool = False
    has_firebase_options: bool = False
    has_google_services: bool = False
    has_google_service_info: bool = False
    firebase_deps_enabled: bool = False

    # Ads status
    has_admob_android: bool = False
    has_admob_ios: bool = False
    ads_deps_enabled: bool = False

    # Metadata
    game_type: str = ""             # "casual", "jrpg", etc.
    document_count: int = 0

    def __post_init__(self):
        # Derive game type from ID
        game_num = int(self.game_id)
        if game_num <= 24:
            self.game_type = "original"
        elif game_num <= 36:
            self.game_type = "jrpg_level_a"
        else:
            self.game_type = "casual"

    @property
    def firebase_ready(self) -> bool:
        """Check if Firebase is fully configured"""
        return (
            self.has_firebase_options and
            self.has_google_services and
            self.firebase_deps_enabled
        )

    @property
    def ads_ready(self) -> bool:
        """Check if Ads SDK is fully configured"""
        return (
            self.has_admob_android and
            self.ads_deps_enabled
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting"""
        return {
            "game_id": self.game_id,
            "name": self.name,
            "exists": self.exists,
            "submodule": self.submodule_type.value,
            "firebase_ready": self.firebase_ready,
            "ads_ready": self.ads_ready,
            "game_type": self.game_type,
        }


class GameScanner:
    """Scans MG games repository for game information"""

    # Known game IDs (from existing scripts)
    ALL_GAME_IDS = [f"{game_id:04d}" for game_id in range(1, 53)]

    def __init__(self, repos_path: Optional[Path] = None):
        self.repos_path = repos_path or DEFAULT_REPOS_PATH
        self._games: Dict[str, GameInfo] = {}

    def _normalize_game_id(self, game_id: int | str) -> str:
        """Normalize numeric and string game IDs to four digits."""
        return str(game_id).zfill(4)

    def scan_all(
        self,
        game_ids: Optional[Sequence[int | str]] = None,
        force_refresh: bool = False,
    ) -> List[GameInfo]:
        """Scan all known games and return info list"""
        if isinstance(game_ids, bool):
            force_refresh = game_ids
            game_ids = None

        target_ids = [self._normalize_game_id(game_id) for game_id in (game_ids or self.ALL_GAME_IDS)]

        if game_ids is None and self._games and not force_refresh:
            return list(self._games.values())

        if game_ids is None:
            self._games.clear()

        games = []
        for game_id in target_ids:
            game_info = self._scan_game(game_id)
            self._games[game_id] = game_info
            games.append(game_info)

        return games

    def scan_game(self, game_id: int | str) -> Optional[GameInfo]:
        """Scan a single game by ID"""
        game_id = self._normalize_game_id(game_id)
        return self._scan_game(game_id)

    def get_game(self, game_id: int | str) -> Optional[GameInfo]:
        """Get cached game info or scan if not cached"""
        game_id = self._normalize_game_id(game_id)
        if game_id not in self._games:
            self._games[game_id] = self._scan_game(game_id)
        return self._games.get(game_id)

    def _scan_game(self, game_id: str) -> GameInfo:
        """Internal method to scan a single game"""
        name = f"mg-game-{game_id}"
        path = self.repos_path / name

        # Check if exists
        if not path.exists():
            return GameInfo(
                game_id=game_id,
                name=name,
                path=path,
                exists=False,
            )

        game_info = GameInfo(
            game_id=game_id,
            name=name,
            path=path,
            exists=True,
        )

        # Check structure
        game_dir = path / "game"
        game_info.has_game_dir = game_dir.exists()

        pubspec = game_dir / "pubspec.yaml"
        game_info.has_pubspec = pubspec.exists()

        # Check submodule type
        game_info.submodule_type = self._detect_submodule_type(path)

        # Check Firebase status
        self._check_firebase_status(game_info, game_dir)

        # Check Ads status
        self._check_ads_status(game_info, game_dir)

        # Count documents
        docs_dir = path / "docs"
        if docs_dir.exists():
            game_info.document_count = len(list(docs_dir.glob("*.md")))

        return game_info

    def _detect_submodule_type(self, game_path: Path) -> SubmoduleType:
        """Detect which submodule structure is used"""
        legacy_path = game_path / SUBMODULE_PATHS["legacy"]
        new_path = game_path / SUBMODULE_PATHS["new"]

        if new_path.exists():
            return SubmoduleType.NEW
        elif legacy_path.exists():
            return SubmoduleType.LEGACY
        return SubmoduleType.NONE

    def _check_firebase_status(self, game_info: GameInfo, game_dir: Path):
        """Check Firebase configuration status"""
        # firebase.json
        game_info.has_firebase_json = (game_dir / "firebase.json").exists()

        # firebase_options.dart
        lib_dir = game_dir / "lib"
        game_info.has_firebase_options = (lib_dir / "firebase_options.dart").exists()

        # google-services.json (Android)
        android_app = game_dir / "android" / "app"
        game_info.has_google_services = (android_app / "google-services.json").exists()

        # GoogleService-Info.plist (iOS)
        ios_runner = game_dir / "ios" / "Runner"
        game_info.has_google_service_info = (ios_runner / "GoogleService-Info.plist").exists()

        # Check pubspec for Firebase deps
        if game_info.has_pubspec:
            game_info.firebase_deps_enabled = self._check_firebase_deps(game_dir / "pubspec.yaml")

    def _check_ads_status(self, game_info: GameInfo, game_dir: Path):
        """Check Ads SDK configuration status"""
        # Check AndroidManifest for AdMob App ID
        manifest = game_dir / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        if manifest.exists():
            content = manifest.read_text(encoding="utf-8")
            game_info.has_admob_android = "com.google.android.gms.ads.APPLICATION_ID" in content

        # Check Info.plist for GADApplicationIdentifier
        info_plist = game_dir / "ios" / "Runner" / "Info.plist"
        if info_plist.exists():
            content = info_plist.read_text(encoding="utf-8")
            game_info.has_admob_ios = "GADApplicationIdentifier" in content

        # Check pubspec for ads deps
        if game_info.has_pubspec:
            game_info.ads_deps_enabled = self._check_ads_deps(game_dir / "pubspec.yaml")

    def _check_firebase_deps(self, pubspec_path: Path) -> bool:
        """Check if Firebase dependencies are enabled (not commented)"""
        try:
            content = pubspec_path.read_text(encoding="utf-8")
            # Look for uncommented firebase_core
            lines = content.split("\n")
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("firebase_core:") and not stripped.startswith("#"):
                    return True
            return False
        except Exception:
            return False

    def _check_ads_deps(self, pubspec_path: Path) -> bool:
        """Check if Ads dependencies are enabled (not commented)"""
        try:
            content = pubspec_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("google_mobile_ads:") and not stripped.startswith("#"):
                    return True
            return False
        except Exception:
            return False

    def get_summary(self, games: Optional[List[GameInfo]] = None) -> Dict[str, Any]:
        """Get summary statistics"""
        games = games or self.scan_all()

        existing = [g for g in games if g.exists]
        firebase_ready = [g for g in existing if g.firebase_ready]
        ads_ready = [g for g in existing if g.ads_ready]

        by_type = {}
        for g in existing:
            by_type.setdefault(g.game_type, []).append(g)

        by_submodule = {}
        for g in existing:
            by_submodule.setdefault(g.submodule_type.value, []).append(g)

        return {
            "total_registered": len(self.ALL_GAME_IDS),
            "total_configured": len(games),
            "existing": len(existing),
            "missing": len(games) - len(existing),
            "firebase_ready": len(firebase_ready),
            "ads_ready": len(ads_ready),
            "firebase": {
                "with_options": sum(1 for g in existing if g.has_firebase_options),
                "with_google_services": sum(1 for g in existing if g.has_google_services),
                "deps_enabled": sum(1 for g in existing if g.firebase_deps_enabled),
            },
            "ads": {
                "with_admob": sum(1 for g in existing if g.has_admob_android),
            },
            "by_type": {k: len(v) for k, v in by_type.items()},
            "by_submodule": {k: len(v) for k, v in by_submodule.items()},
        }

    def filter_games(
        self,
        game_type: Optional[str] = None,
        firebase_ready: Optional[bool] = None,
        ads_ready: Optional[bool] = None,
        exists_only: bool = True,
    ) -> List[GameInfo]:
        """Filter games by criteria"""
        games = self.scan_all()

        if exists_only:
            games = [g for g in games if g.exists]

        if game_type:
            games = [g for g in games if g.game_type == game_type]

        if firebase_ready is not None:
            games = [g for g in games if g.firebase_ready == firebase_ready]

        if ads_ready is not None:
            games = [g for g in games if g.ads_ready == ads_ready]

        return games
