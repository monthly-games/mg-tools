"""
Configuration management for MG-CLI
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

# Default paths
DEFAULT_BASE_PATH = Path(r"d:\mg-games")
DEFAULT_REPOS_PATH = DEFAULT_BASE_PATH / "repos"
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config"

# Game ID patterns
GAME_ID_PATTERN = r"mg-game-(\d{4})"

# Submodule patterns (old vs new)
SUBMODULE_PATHS = {
    "legacy": "common/game",      # MG-0001 ~ MG-0024
    "new": "libs/mg_common_game", # MG-0025+
}

# Firebase test project (development)
FIREBASE_TEST_PROJECT = "mg-games-dev"

# AdMob test IDs
ADMOB_TEST_IDS = {
    "android": {
        "app_id": "ca-app-pub-3940256099942544~3347511713",
        "interstitial": "ca-app-pub-3940256099942544/1033173712",
        "rewarded": "ca-app-pub-3940256099942544/5224354917",
        "banner": "ca-app-pub-3940256099942544/6300978111",
    },
    "ios": {
        "app_id": "ca-app-pub-3940256099942544~1458002511",
        "interstitial": "ca-app-pub-3940256099942544/4411468910",
        "rewarded": "ca-app-pub-3940256099942544/1712485313",
        "banner": "ca-app-pub-3940256099942544/2934735716",
    },
}


class Config:
    """MG-CLI configuration manager"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.base_path = DEFAULT_BASE_PATH
        self.repos_path = DEFAULT_REPOS_PATH
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file"""
        config_file = self.config_path / "mg_cli_config.yaml"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "environment": "dev",
            "firebase": {
                "project_pattern": "mg-game-{game_id}",
                "shared_project": FIREBASE_TEST_PROJECT,
                "use_shared": True,
            },
            "ads": {
                "sdk": "admob",
                "test_mode": True,
                "mediation": False,
            },
            "batch": {
                "parallel": False,
                "max_workers": 4,
                "dry_run": False,
            },
        }

    def save_config(self):
        """Save current configuration to file"""
        self.config_path.mkdir(parents=True, exist_ok=True)
        config_file = self.config_path / "mg_cli_config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    @property
    def environment(self) -> str:
        return self._config.get("environment", "dev")

    @environment.setter
    def environment(self, value: str):
        self._config["environment"] = value

    @property
    def firebase_config(self) -> Dict[str, Any]:
        return self._config.get("firebase", {})

    @property
    def ads_config(self) -> Dict[str, Any]:
        return self._config.get("ads", {})

    @property
    def is_test_mode(self) -> bool:
        return self._config.get("ads", {}).get("test_mode", True)

    @property
    def is_dry_run(self) -> bool:
        return self._config.get("batch", {}).get("dry_run", False)

    def get_admob_ids(self, platform: str) -> Dict[str, str]:
        """Get AdMob IDs for platform (android/ios)"""
        if self.is_test_mode:
            return ADMOB_TEST_IDS.get(platform, {})
        # TODO: Load production IDs from config
        return ADMOB_TEST_IDS.get(platform, {})

    def get_firebase_project_id(self, game_id: str) -> str:
        """Get Firebase project ID for a game"""
        firebase_cfg = self.firebase_config
        if firebase_cfg.get("use_shared", True):
            return firebase_cfg.get("shared_project", FIREBASE_TEST_PROJECT)
        pattern = firebase_cfg.get("project_pattern", "mg-game-{game_id}")
        return pattern.format(game_id=game_id)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(config_path: Optional[Path] = None) -> Config:
    """Initialize config with optional custom path"""
    global _config
    _config = Config(config_path)
    return _config
