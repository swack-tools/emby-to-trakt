"""Integration tests for end-to-end workflow."""

import responses
from click.testing import CliRunner

from emby_to_trakt.cli import cli


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
        assert "2 items" in result.output
        assert "1 movies" in result.output
        assert "1 episodes" in result.output

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
