"""Configuration management for mg-cli."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import yaml


@dataclass
class FirebaseConfig:
    """Firebase project configuration."""
    project_id_pattern: str = "mg-game-{game_id}"
    dev_project: str = "mg-games-dev"
    staging_project: str = "mg-games-stg"
    prod_project: str = "mg-games-prod"


@dataclass
class AdsConfig:
    """Ads SDK configuration."""
    # Test IDs (for development)
    android_app_id_test: str = "ca-app-pub-3940256099942544~3347511713"
    ios_app_id_test: str = "ca-app-pub-3940256099942544~1458002511"
    android_interstitial_test: str = "ca-app-pub-3940256099942544/1033173712"
    android_rewarded_test: str = "ca-app-pub-3940256099942544/5224354917"
    ios_interstitial_test: str = "ca-app-pub-3940256099942544/4411468910"
    ios_rewarded_test: str = "ca-app-pub-3940256099942544/1712485313"


@dataclass
class CLIConfig:
    """Main CLI configuration."""
    repos_path: Path = field(default_factory=lambda: Path("d:/mg-games/repos"))
    config_path: Path = field(default_factory=lambda: Path("d:/mg-games/config"))
    game_id_range: tuple = (1, 52)
    excluded_games: list = field(default_factory=lambda: [35] + list(range(39, 48)))
    firebase: FirebaseConfig = field(default_factory=FirebaseConfig)
    ads: AdsConfig = field(default_factory=AdsConfig)
    env: str = "dev"  # dev, staging, prod

    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> "CLIConfig":
        """Load configuration from YAML file."""
        config = cls()

        if config_file is None:
            config_file = config.config_path / "mg_cli_config.yaml"

        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            if 'repos_path' in data:
                config.repos_path = Path(data['repos_path'])
            if 'env' in data:
                config.env = data['env']
            if 'excluded_games' in data:
                config.excluded_games = data['excluded_games']

        return config

    def save(self, config_file: Optional[Path] = None):
        """Save configuration to YAML file."""
        if config_file is None:
            config_file = self.config_path / "mg_cli_config.yaml"

        config_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'repos_path': str(self.repos_path),
            'env': self.env,
            'excluded_games': self.excluded_games,
            'game_id_range': list(self.game_id_range),
        }

        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_game_ids(self) -> list:
        """Get list of valid game IDs."""
        start, end = self.game_id_range
        return [i for i in range(start, end + 1) if i not in self.excluded_games]

    def get_game_path(self, game_id: int) -> Path:
        """Get path to a specific game repository."""
        return self.repos_path / f"mg-game-{game_id:04d}"

    def get_firebase_project_id(self, game_id: int) -> str:
        """Get Firebase project ID for a game."""
        if self.env == "dev":
            return self.firebase.dev_project
        elif self.env == "staging":
            return self.firebase.staging_project
        elif self.env == "prod":
            return self.firebase.project_id_pattern.format(game_id=f"{game_id:04d}")
        return self.firebase.dev_project
