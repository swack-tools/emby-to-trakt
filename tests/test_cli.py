"""Tests for CLI commands."""

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
