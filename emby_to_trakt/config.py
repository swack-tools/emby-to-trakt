"""Configuration management for emby-sync."""

import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


class ConfigError(Exception):
    """Configuration error."""

    pass


class Config:
    """Manages emby-sync configuration."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize config with data directory."""
        if data_dir is None:
            data_dir = Path.cwd() / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = self.data_dir / "config.yaml"
        self.watched_path = self.data_dir / "watched.yaml"
        self.log_path = self.data_dir / "emby-sync.log"

        # Emby credentials
        self.server_url: Optional[str] = None
        self.user_id: Optional[str] = None
        self.access_token: Optional[str] = None
        self.device_id: Optional[str] = None

        # Sync settings
        self.sync_mode: str = "incremental"
        self.last_sync: Optional[datetime] = None

    def exists(self) -> bool:
        """Check if config file exists."""
        return self.config_path.exists()

    def set_emby_credentials(
        self,
        server_url: str,
        user_id: str,
        access_token: str,
        device_id: str,
    ) -> None:
        """Set Emby credentials."""
        self.server_url = server_url
        self.user_id = user_id
        self.access_token = access_token
        self.device_id = device_id

    def set_sync_mode(self, mode: str) -> None:
        """Set sync mode (full or incremental)."""
        if mode not in ("full", "incremental"):
            raise ConfigError(f"Invalid sync mode: {mode}")
        self.sync_mode = mode

    def set_last_sync(self, timestamp: datetime) -> None:
        """Set last sync timestamp."""
        self.last_sync = timestamp

    def save(self) -> None:
        """Save configuration to YAML file."""
        data = {
            "emby": {
                "server_url": self.server_url,
                "user_id": self.user_id,
                "access_token": self.access_token,
                "device_id": self.device_id,
            },
            "sync": {
                "mode": self.sync_mode,
                "last_sync": (
                    self.last_sync.isoformat() if self.last_sync else None
                ),
            },
        }

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        # Set file permissions to 0600 (owner read/write only)
        if os.name != "nt":
            os.chmod(self.config_path, stat.S_IRUSR | stat.S_IWUSR)

    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise ConfigError(
                f"Config file not found: {self.config_path}\n"
                "Run 'emby-sync setup' to configure."
            )

        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        emby = data.get("emby", {})
        self.server_url = emby.get("server_url")
        self.user_id = emby.get("user_id")
        self.access_token = emby.get("access_token")
        self.device_id = emby.get("device_id")

        sync = data.get("sync", {})
        self.sync_mode = sync.get("mode", "incremental")
        last_sync_str = sync.get("last_sync")
        if last_sync_str:
            self.last_sync = datetime.fromisoformat(last_sync_str)
