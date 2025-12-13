"""Tests for CLI commands."""

from importlib.metadata import version

import responses
import yaml
from click.testing import CliRunner

from emby_to_trakt.cli import cli
from emby_to_trakt.config import Config


def test_cli_help():
    """CLI shows help message."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Emby to Trakt sync tool" in result.output


def test_cli_version():
    """CLI shows version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert version("emby-to-trakt") in result.output


def test_cli_setup_command_exists():
    """setup command is available."""
    runner = CliRunner()
    result = runner.invoke(cli, ["setup", "--help"])
    assert result.exit_code == 0
    assert "setup" in result.output.lower()


def test_cli_download_command_exists():
    """download command is available."""
    runner = CliRunner()
    result = runner.invoke(cli, ["download", "--help"])
    assert result.exit_code == 0


def test_cli_status_command_exists():
    """status command is available."""
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--help"])
    assert result.exit_code == 0


def test_cli_validate_command_exists():
    """validate command is available."""
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", "--help"])
    assert result.exit_code == 0


class TestSetupCommand:
    """Tests for setup command."""

    @responses.activate
    def test_setup_success(self, tmp_path):
        """Setup authenticates and saves config."""
        responses.add(
            responses.POST,
            "https://emby.example.com/Users/AuthenticateByName",
            json={
                "AccessToken": "token123",
                "User": {"Id": "user456"},
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["setup"],
            input="https://emby.example.com\ntestuser\ntestpass\n",
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0
        assert "Setup complete" in result.output
        assert (tmp_path / "config.yaml").exists()

    @responses.activate
    def test_setup_invalid_credentials(self, tmp_path):
        """Setup shows error for invalid credentials."""
        responses.add(
            responses.POST,
            "https://emby.example.com/Users/AuthenticateByName",
            status=401,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["setup"],
            input="https://emby.example.com\nbaduser\nbadpass\n",
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code != 0
        assert "Invalid username or password" in result.output

    def test_setup_warn_overwrite(self, tmp_path):
        """Setup warns when config exists."""
        # Create existing config
        (tmp_path / "config.yaml").write_text("emby:\n  server_url: test")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["setup"],
            input="n\n",  # Say no to overwrite
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert "already exists" in result.output.lower()


class TestDownloadCommand:
    """Tests for download command."""

    def test_download_no_config(self, tmp_path):
        """Download fails without config."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["download"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "setup" in result.output.lower()

    @responses.activate
    def test_download_success(self, tmp_path):
        """Download fetches and saves watched items."""
        # Create config
        config_content = """
emby:
  server_url: https://emby.example.com
  user_id: user456
  access_token: token123
  device_id: device789
sync:
  mode: full
"""
        (tmp_path / "config.yaml").write_text(config_content)

        # Mock API response
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "movie1",
                        "Name": "Test Movie",
                        "Type": "Movie",
                        "UserData": {
                            "Played": True,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-01T20:00:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 7200000000000,
                        "ProviderIds": {"Imdb": "tt0000001"},
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["download", "--content", "movies"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0
        assert "Downloaded" in result.output
        assert (tmp_path / "watched.yaml").exists()

    @responses.activate
    def test_download_shows_summary(self, tmp_path):
        """Download displays item count summary."""
        # Create config
        config_content = """
emby:
  server_url: https://emby.example.com
  user_id: user456
  access_token: token123
  device_id: device789
sync:
  mode: full
"""
        (tmp_path / "config.yaml").write_text(config_content)

        # Mock API response with multiple items
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": f"movie{i}",
                        "Name": f"Movie {i}",
                        "Type": "Movie",
                        "UserData": {
                            "Played": True,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-01T20:00:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 7200000000000,
                        "ProviderIds": {},
                    }
                    for i in range(5)
                ],
                "TotalRecordCount": 5,
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["download", "--content", "movies"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert "5" in result.output  # Should show count


class TestStatusCommand:
    """Tests for status command."""

    def test_status_no_data(self, tmp_path):
        """Status shows message when no data exists."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["status"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert "No watched data" in result.output or "not found" in result.output.lower()

    def test_status_shows_counts(self, tmp_path):
        """Status displays item counts."""
        # Create watched data
        watched_content = """
sync_metadata:
  last_updated: "2025-12-12T14:30:00"
  total_items: 10
watched_items:
  - emby_id: "1"
    title: "Movie 1"
    item_type: "movie"
    watched_date: "2025-12-01T00:00:00"
    play_count: 1
    is_fully_watched: true
    completion_percentage: 100.0
    playback_position_ticks: 0
    runtime_ticks: 1000
    raw_metadata: {}
"""
        (tmp_path / "watched.yaml").write_text(watched_content)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["status"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0
        assert "1" in result.output  # Item count

    def test_status_shows_trakt_status(self, tmp_path, monkeypatch):
        """Status shows Trakt configuration status."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config with Trakt
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="http://emby.local",
            user_id="user1",
            access_token="token1",
            device_id="device1",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Create watched data
        watched_content = """
sync_metadata:
  last_updated: "2025-12-12T14:30:00"
watched_items:
  - emby_id: "1"
    title: "Movie 1"
    item_type: "movie"
    watched_date: "2025-12-01T00:00:00"
    play_count: 1
    is_fully_watched: true
    completion_percentage: 100.0
    playback_position_ticks: 0
    runtime_ticks: 1000
    raw_metadata: {}
"""
        (tmp_path / "watched.yaml").write_text(watched_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "trakt" in result.output.lower()

    def test_status_shows_unmatched_count(self, tmp_path, monkeypatch):
        """Status shows unmatched item count."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create watched data
        watched_content = """
sync_metadata:
  last_updated: "2025-12-12T14:30:00"
watched_items:
  - emby_id: "1"
    title: "Movie 1"
    item_type: "movie"
    watched_date: "2025-12-01T00:00:00"
    play_count: 1
    is_fully_watched: true
    completion_percentage: 100.0
    playback_position_ticks: 0
    runtime_ticks: 1000
    raw_metadata: {}
"""
        (tmp_path / "watched.yaml").write_text(watched_content)

        # Create unmatched.yaml
        unmatched_content = """
- title: "Unknown Movie"
  item_type: movie
  emby_id: "123"
  reason: "No provider IDs"
"""
        (tmp_path / "unmatched.yaml").write_text(unmatched_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "unmatched" in result.output.lower()


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_no_config(self, tmp_path):
        """Validate fails without config."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code != 0

    @responses.activate
    def test_validate_success(self, tmp_path):
        """Validate shows success for valid config."""
        # Create config
        config_content = """
emby:
  server_url: https://emby.example.com
  user_id: user456
  access_token: token123
  device_id: device789
sync:
  mode: incremental
"""
        (tmp_path / "config.yaml").write_text(config_content)

        responses.add(
            responses.GET,
            "https://emby.example.com/System/Info",
            json={"ServerName": "My Emby"},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["validate"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "success" in result.output.lower()

    @responses.activate
    def test_validate_checks_trakt_connection(self, tmp_path, monkeypatch):
        """Validate checks Trakt connection when configured."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config with both Emby and Trakt
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="https://emby.example.com",
            user_id="user456",
            access_token="token123",
            device_id="device789",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Mock Emby connection
        responses.add(
            responses.GET,
            "https://emby.example.com/System/Info",
            json={"ServerName": "My Emby"},
            status=200,
        )

        # Mock Trakt connection
        responses.add(
            responses.GET,
            "https://api.trakt.tv/users/me",
            json={"username": "testuser"},
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])

        assert result.exit_code == 0
        assert "trakt" in result.output.lower()
        assert "valid" in result.output.lower() or "connected" in result.output.lower()


class TestTraktSetupCommand:
    """Test trakt-setup command."""

    @responses.activate
    def test_trakt_setup_success(self, tmp_path, monkeypatch):
        """Trakt setup completes successfully."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Mock device code request
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/code",
            json={
                "device_code": "device123",
                "user_code": "TESTCODE",
                "verification_url": "https://trakt.tv/activate",
                "expires_in": 600,
                "interval": 1,
            },
            status=200,
        )

        # Mock token poll (immediate success)
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/token",
            json={
                "access_token": "access123",
                "refresh_token": "refresh456",
                "expires_in": 7776000,
                "created_at": 1734048000,
            },
            status=200,
        )

        runner = CliRunner()
        # Provide input: y (ready), client_id, client_secret
        result = runner.invoke(
            cli,
            ["trakt-setup"],
            input="y\ntest-client-id\ntest-client-secret\n",
        )

        assert result.exit_code == 0
        assert "TESTCODE" in result.output
        assert "connected" in result.output.lower()


class TestPushCommand:
    """Test push command."""

    @responses.activate
    def test_push_dry_run(self, tmp_path, monkeypatch):
        """Push with dry-run shows preview."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="http://emby.local",
            user_id="user1",
            access_token="token1",
            device_id="device1",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Create watched.yaml with test data
        watched_data = {
            "sync_metadata": {"last_updated": "2025-12-12T00:00:00"},
            "watched_items": [
                {
                    "emby_id": "1",
                    "title": "Test Movie",
                    "item_type": "movie",
                    "watched_date": "2025-12-01T00:00:00",
                    "play_count": 1,
                    "is_fully_watched": True,
                    "completion_percentage": 100.0,
                    "playback_position_ticks": 0,
                    "runtime_ticks": 0,
                    "imdb_id": "tt1234567",
                },
            ],
        }
        watched_path = tmp_path / "watched.yaml"
        with open(watched_path, "w") as f:
            yaml.dump(watched_data, f)

        runner = CliRunner()
        result = runner.invoke(cli, ["push", "--dry-run"])

        assert result.exit_code == 0
        assert "dry run" in result.output.lower()
        assert "1" in result.output  # 1 movie

    @responses.activate
    def test_push_syncs_to_trakt(self, tmp_path, monkeypatch):
        """Push syncs items to Trakt."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="http://emby.local",
            user_id="user1",
            access_token="token1",
            device_id="device1",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Create watched.yaml
        watched_data = {
            "sync_metadata": {"last_updated": "2025-12-12T00:00:00"},
            "watched_items": [
                {
                    "emby_id": "1",
                    "title": "Test Movie",
                    "item_type": "movie",
                    "watched_date": "2025-12-01T00:00:00",
                    "play_count": 1,
                    "is_fully_watched": True,
                    "completion_percentage": 100.0,
                    "playback_position_ticks": 0,
                    "runtime_ticks": 0,
                    "imdb_id": "tt1234567",
                },
            ],
        }
        watched_path = tmp_path / "watched.yaml"
        with open(watched_path, "w") as f:
            yaml.dump(watched_data, f)

        # Mock Trakt sync
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 1, "episodes": 0}},
            status=201,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        assert "pushed" in result.output.lower() or "synced" in result.output.lower()

    @responses.activate
    def test_push_logs_unmatched_items(self, tmp_path, monkeypatch):
        """Push logs items without provider IDs."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="http://emby.local",
            user_id="user1",
            access_token="token1",
            device_id="device1",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Create watched.yaml with unmatched item
        watched_data = {
            "sync_metadata": {"last_updated": "2025-12-12T00:00:00"},
            "watched_items": [
                {
                    "emby_id": "1",
                    "title": "Unknown Movie",
                    "item_type": "movie",
                    "watched_date": "2025-12-01T00:00:00",
                    "play_count": 1,
                    "is_fully_watched": True,
                    "completion_percentage": 100.0,
                    "playback_position_ticks": 0,
                    "runtime_ticks": 0,
                    # No provider IDs
                },
            ],
        }
        watched_path = tmp_path / "watched.yaml"
        with open(watched_path, "w") as f:
            yaml.dump(watched_data, f)

        # Mock Trakt sync (will get empty payload)
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 0, "episodes": 0}},
            status=201,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["push"])

        assert result.exit_code == 0
        assert "unmatched" in result.output.lower()
        # Check unmatched.yaml was created
        assert (tmp_path / "unmatched.yaml").exists()

    def test_push_no_config(self, tmp_path, monkeypatch):
        """Push fails without Trakt config."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["push"])

        assert result.exit_code != 0
        assert "not configured" in result.output.lower() or "not found" in result.output.lower()

    @responses.activate
    def test_push_content_filter_movies(self, tmp_path, monkeypatch):
        """Push with --content movies filters episodes."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="http://emby.local",
            user_id="user1",
            access_token="token1",
            device_id="device1",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Create watched.yaml with both movies and episodes
        watched_data = {
            "sync_metadata": {"last_updated": "2025-12-12T00:00:00"},
            "watched_items": [
                {
                    "emby_id": "1",
                    "title": "Test Movie",
                    "item_type": "movie",
                    "watched_date": "2025-12-01T00:00:00",
                    "play_count": 1,
                    "is_fully_watched": True,
                    "completion_percentage": 100.0,
                    "playback_position_ticks": 0,
                    "runtime_ticks": 0,
                    "imdb_id": "tt1234567",
                },
                {
                    "emby_id": "2",
                    "title": "Test Episode",
                    "item_type": "episode",
                    "watched_date": "2025-12-01T00:00:00",
                    "play_count": 1,
                    "is_fully_watched": True,
                    "completion_percentage": 100.0,
                    "playback_position_ticks": 0,
                    "runtime_ticks": 0,
                    "tvdb_id": "12345",
                    "series_name": "Test Show",
                    "season_number": 1,
                    "episode_number": 1,
                },
            ],
        }
        watched_path = tmp_path / "watched.yaml"
        with open(watched_path, "w") as f:
            yaml.dump(watched_data, f)

        # Mock Trakt sync - should only receive movies
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 1, "episodes": 0}},
            status=201,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["push", "--content", "movies"])

        assert result.exit_code == 0


class TestDownloadPushFlag:
    """Test --push flag on download command."""

    @responses.activate
    def test_download_push_flag_syncs_after_download(self, tmp_path, monkeypatch):
        """Download with --push runs push after download."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config with both Emby and Trakt
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url="https://emby.example.com",
            user_id="user456",
            access_token="token123",
            device_id="device789",
        )
        config.set_trakt_credentials(
            client_id="client1",
            client_secret="secret1",
            access_token="access1",
            refresh_token="refresh1",
            expires_at="2025-12-20T00:00:00",
        )
        config.save()

        # Mock Emby API - return movie with provider ID
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "movie1",
                        "Name": "Test Movie",
                        "Type": "Movie",
                        "UserData": {
                            "Played": True,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-01T20:00:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 7200000000000,
                        "ProviderIds": {"Imdb": "tt0000001"},
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        # Mock Trakt sync
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 1, "episodes": 0}},
            status=201,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "--content", "movies", "--push"])

        assert result.exit_code == 0
        assert "Downloaded" in result.output
        assert "Pushed" in result.output or "pushed" in result.output.lower()

    @responses.activate
    def test_download_push_flag_without_trakt_config(self, tmp_path, monkeypatch):
        """Download with --push fails gracefully without Trakt config."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))

        # Create config with only Emby (no Trakt)
        config_content = """
emby:
  server_url: https://emby.example.com
  user_id: user456
  access_token: token123
  device_id: device789
sync:
  mode: full
"""
        (tmp_path / "config.yaml").write_text(config_content)

        # Mock Emby API
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "movie1",
                        "Name": "Test Movie",
                        "Type": "Movie",
                        "UserData": {
                            "Played": True,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-01T20:00:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 7200000000000,
                        "ProviderIds": {},
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "--content", "movies", "--push"])

        # Should download but warn about push
        assert "Downloaded" in result.output
        assert "trakt" in result.output.lower()
