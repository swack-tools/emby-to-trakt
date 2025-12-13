"""Tests for configuration management."""

import os
import stat

import pytest

from emby_to_trakt.config import Config, ConfigError


def test_config_default_paths(tmp_path):
    """Config uses data directory for storage."""
    config = Config(data_dir=tmp_path)
    assert config.config_path == tmp_path / "config.yaml"
    assert config.watched_path == tmp_path / "watched.yaml"
    assert config.log_path == tmp_path / "emby-sync.log"


def test_config_save_and_load(tmp_path):
    """Config saves and loads settings."""
    config = Config(data_dir=tmp_path)
    config.set_emby_credentials(
        server_url="https://emby.example.com",
        user_id="user123",
        access_token="token456",
        device_id="device789",
    )
    config.save()

    # Load in new instance
    config2 = Config(data_dir=tmp_path)
    config2.load()
    assert config2.server_url == "https://emby.example.com"
    assert config2.user_id == "user123"
    assert config2.access_token == "token456"
    assert config2.device_id == "device789"


def test_config_file_permissions(tmp_path):
    """Config file has restricted permissions (0600)."""
    config = Config(data_dir=tmp_path)
    config.set_emby_credentials(
        server_url="https://emby.example.com",
        user_id="user123",
        access_token="token456",
        device_id="device789",
    )
    config.save()

    # Check permissions (Unix only)
    if os.name != "nt":
        mode = stat.S_IMODE(os.stat(config.config_path).st_mode)
        assert mode == 0o600


def test_config_load_missing_file(tmp_path):
    """Config raises error when file missing."""
    config = Config(data_dir=tmp_path)
    with pytest.raises(ConfigError, match="not found"):
        config.load()


def test_config_exists(tmp_path):
    """Config.exists() checks for config file."""
    config = Config(data_dir=tmp_path)
    assert config.exists() is False

    config.set_emby_credentials(
        server_url="https://emby.example.com",
        user_id="user123",
        access_token="token456",
        device_id="device789",
    )
    config.save()
    assert config.exists() is True


def test_config_sync_settings(tmp_path):
    """Config manages sync settings."""
    config = Config(data_dir=tmp_path)
    config.set_emby_credentials(
        server_url="https://emby.example.com",
        user_id="user123",
        access_token="token456",
        device_id="device789",
    )
    config.set_sync_mode("full")
    config.save()

    config2 = Config(data_dir=tmp_path)
    config2.load()
    assert config2.sync_mode == "full"


def test_config_last_sync(tmp_path):
    """Config tracks last sync timestamp."""
    from datetime import datetime

    config = Config(data_dir=tmp_path)
    config.set_emby_credentials(
        server_url="https://emby.example.com",
        user_id="user123",
        access_token="token456",
        device_id="device789",
    )

    assert config.last_sync is None

    now = datetime(2025, 12, 12, 10, 30, 0)
    config.set_last_sync(now)
    config.save()

    config2 = Config(data_dir=tmp_path)
    config2.load()
    assert config2.last_sync == now


class TestTraktConfig:
    """Test Trakt configuration."""

    def test_set_trakt_credentials(self, tmp_path):
        """Set Trakt credentials."""
        config = Config(data_dir=tmp_path)

        config.set_trakt_credentials(
            client_id="client123",
            client_secret="secret456",
            access_token="access789",
            refresh_token="refresh012",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Reload and verify
        config2 = Config(data_dir=tmp_path)
        config2.load()

        assert config2.trakt_client_id == "client123"
        assert config2.trakt_client_secret == "secret456"
        assert config2.trakt_access_token == "access789"
        assert config2.trakt_refresh_token == "refresh012"
        assert config2.trakt_expires_at == "2025-12-20T00:00:00"

    def test_trakt_configured(self, tmp_path):
        """Check if Trakt is configured."""
        config = Config(data_dir=tmp_path)

        assert config.trakt_configured is False

        config.set_trakt_credentials(
            client_id="client123",
            client_secret="secret456",
            access_token="access789",
            refresh_token="refresh012",
            expires_at="2025-12-20T00:00:00",
        )

        assert config.trakt_configured is True
