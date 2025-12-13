"""Integration tests for end-to-end workflow."""

import responses
from click.testing import CliRunner

from emby_to_trakt.cli import cli
from emby_to_trakt.config import Config


class TestEndToEndWorkflow:
    """Test complete setup -> download -> status workflow."""

    @responses.activate
    def test_full_workflow(self, tmp_path):
        """Complete workflow: setup, download, status."""
        runner = CliRunner()
        env = {"EMBY_SYNC_DATA_DIR": str(tmp_path)}

        # 1. Setup
        responses.add(
            responses.POST,
            "https://emby.example.com/Users/AuthenticateByName",
            json={
                "AccessToken": "token123",
                "User": {"Id": "user456"},
            },
            status=200,
        )

        result = runner.invoke(
            cli,
            ["setup"],
            input="https://emby.example.com\ntestuser\ntestpass\n",
            env=env,
        )
        assert result.exit_code == 0
        assert (tmp_path / "config.yaml").exists()

        # 2. Download - Mock API for both movies and episodes
        # First call for movies
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "movie1",
                        "Name": "Inception",
                        "Type": "Movie",
                        "UserData": {
                            "Played": True,
                            "PlayCount": 2,
                            "LastPlayedDate": "2025-11-15T20:30:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 8880000000000,
                        "ProviderIds": {
                            "Imdb": "tt1375666",
                            "Tmdb": "27205",
                        },
                    },
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )
        # Second call for episodes
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "ep1",
                        "Name": "Pilot",
                        "Type": "Episode",
                        "SeriesName": "Breaking Bad",
                        "ParentIndexNumber": 1,
                        "IndexNumber": 1,
                        "UserData": {
                            "Played": True,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-01T21:00:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 3600000000000,
                        "ProviderIds": {"Tvdb": "123456"},
                    },
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        result = runner.invoke(cli, ["download"], env=env)
        assert result.exit_code == 0
        assert (tmp_path / "watched.yaml").exists()
        assert "Downloaded" in result.output
        assert "items" in result.output

        # 3. Status
        result = runner.invoke(cli, ["status"], env=env)
        assert result.exit_code == 0
        assert "2" in result.output  # Total items

        # 4. Validate
        responses.add(
            responses.GET,
            "https://emby.example.com/System/Info",
            json={"ServerName": "My Emby"},
            status=200,
        )

        result = runner.invoke(cli, ["validate"], env=env)
        assert result.exit_code == 0


class TestDownloadAndPushWorkflow:
    """Test download -> push workflow with Trakt."""

    @responses.activate
    def test_download_then_push_workflow(self, tmp_path, monkeypatch):
        """Full workflow: download from Emby, push to Trakt."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))
        runner = CliRunner()

        # Setup config with both Emby and Trakt credentials
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

        # Mock Emby API - movies
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "movie1",
                        "Name": "Inception",
                        "Type": "Movie",
                        "UserData": {
                            "Played": True,
                            "PlayCount": 2,
                            "LastPlayedDate": "2025-11-15T20:30:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 8880000000000,
                        "ProviderIds": {
                            "Imdb": "tt1375666",
                            "Tmdb": "27205",
                        },
                    },
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        # Mock Emby API - episodes
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "ep1",
                        "Name": "Pilot",
                        "Type": "Episode",
                        "SeriesName": "Breaking Bad",
                        "ParentIndexNumber": 1,
                        "IndexNumber": 1,
                        "UserData": {
                            "Played": True,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-01T21:00:00.0000000Z",
                            "PlaybackPositionTicks": 0,
                        },
                        "RunTimeTicks": 3600000000000,
                        "ProviderIds": {"Tvdb": "123456"},
                    },
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        # 1. Download from Emby
        result = runner.invoke(cli, ["download"])
        assert result.exit_code == 0
        assert "Downloaded" in result.output
        assert (tmp_path / "watched.yaml").exists()

        # Mock Trakt API
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 1, "episodes": 1}},
            status=201,
        )

        # 2. Push to Trakt
        result = runner.invoke(cli, ["push"])
        assert result.exit_code == 0
        assert "Pushed" in result.output or "pushed" in result.output.lower()

        # 3. Check status shows data
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "2" in result.output  # Total items
        assert "trakt" in result.output.lower()

    @responses.activate
    def test_download_with_push_flag(self, tmp_path, monkeypatch):
        """Download with --push flag downloads and pushes in one command."""
        monkeypatch.setenv("EMBY_SYNC_DATA_DIR", str(tmp_path))
        runner = CliRunner()

        # Setup config
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
                        "ProviderIds": {"Imdb": "tt0000001"},
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        # Mock Trakt API
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 1, "episodes": 0}},
            status=201,
        )

        # Download with --push flag
        result = runner.invoke(cli, ["download", "--content", "movies", "--push"])

        assert result.exit_code == 0
        assert "Downloaded" in result.output
        assert "Pushed" in result.output or "pushed" in result.output.lower()
