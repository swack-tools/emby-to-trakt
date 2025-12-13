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
