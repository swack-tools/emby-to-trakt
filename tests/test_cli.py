"""Tests for CLI commands."""

import responses
from click.testing import CliRunner

from emby_to_trakt.cli import cli


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
    assert "0.1.0" in result.output


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
    def test_setup_invalid_credentials(self):
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
