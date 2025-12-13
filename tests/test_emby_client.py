"""Tests for Emby API client."""

from datetime import datetime

import pytest
import responses

from emby_to_trakt.emby_client import EmbyClient, EmbyAuthError, EmbyConnectionError


class TestEmbyAuthentication:
    """Tests for Emby authentication."""

    @responses.activate
    def test_authenticate_success(self):
        """Successful authentication returns token and user ID."""
        responses.add(
            responses.POST,
            "https://emby.example.com/Users/AuthenticateByName",
            json={
                "AccessToken": "abc123token",
                "User": {"Id": "user456"},
            },
            status=200,
        )

        client = EmbyClient(server_url="https://emby.example.com")
        result = client.authenticate("testuser", "testpass")

        assert result["access_token"] == "abc123token"
        assert result["user_id"] == "user456"
        assert "device_id" in result

    @responses.activate
    def test_authenticate_invalid_credentials(self):
        """Invalid credentials raise EmbyAuthError."""
        responses.add(
            responses.POST,
            "https://emby.example.com/Users/AuthenticateByName",
            status=401,
        )

        client = EmbyClient(server_url="https://emby.example.com")
        with pytest.raises(EmbyAuthError, match="Invalid username or password"):
            client.authenticate("baduser", "badpass")

    @responses.activate
    def test_authenticate_server_error(self):
        """Server error raises EmbyConnectionError."""
        responses.add(
            responses.POST,
            "https://emby.example.com/Users/AuthenticateByName",
            status=500,
        )

        client = EmbyClient(server_url="https://emby.example.com")
        with pytest.raises(EmbyConnectionError):
            client.authenticate("user", "pass")

    def test_authenticate_connection_error(self):
        """Connection failure raises EmbyConnectionError."""
        client = EmbyClient(server_url="https://nonexistent.example.com")
        with pytest.raises(EmbyConnectionError, match="Cannot connect"):
            client.authenticate("user", "pass")


class TestEmbyConnection:
    """Tests for connection validation."""

    @responses.activate
    def test_test_connection_success(self):
        """test_connection returns True for valid connection."""
        responses.add(
            responses.GET,
            "https://emby.example.com/System/Info",
            json={"ServerName": "My Emby"},
            status=200,
        )

        client = EmbyClient(
            server_url="https://emby.example.com",
            access_token="token123",
            user_id="user456",
            device_id="device789",
        )
        assert client.test_connection() is True

    @responses.activate
    def test_test_connection_invalid_token(self):
        """test_connection returns False for invalid token."""
        responses.add(
            responses.GET,
            "https://emby.example.com/System/Info",
            status=401,
        )

        client = EmbyClient(
            server_url="https://emby.example.com",
            access_token="badtoken",
            user_id="user456",
            device_id="device789",
        )
        assert client.test_connection() is False


class TestFetchWatchedItems:
    """Tests for fetching watched items."""

    @responses.activate
    def test_get_watched_movies(self):
        """Fetch watched movies from Emby."""
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
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        client = EmbyClient(
            server_url="https://emby.example.com",
            access_token="token123",
            user_id="user456",
            device_id="device789",
        )
        items = client.get_watched_items(content_type="movies")

        assert len(items) == 1
        assert items[0].emby_id == "movie1"
        assert items[0].title == "Inception"
        assert items[0].item_type == "movie"
        assert items[0].imdb_id == "tt1375666"
        assert items[0].tmdb_id == "27205"

    @responses.activate
    def test_get_watched_episodes(self):
        """Fetch watched episodes from Emby."""
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
                        "ProviderIds": {
                            "Tvdb": "123456",
                        },
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        client = EmbyClient(
            server_url="https://emby.example.com",
            access_token="token123",
            user_id="user456",
            device_id="device789",
        )
        items = client.get_watched_items(content_type="episodes")

        assert len(items) == 1
        assert items[0].item_type == "episode"
        assert items[0].series_name == "Breaking Bad"
        assert items[0].season_number == 1
        assert items[0].episode_number == 1
        assert items[0].tvdb_id == "123456"

    @responses.activate
    def test_get_watched_items_incremental(self):
        """Incremental sync uses since parameter."""
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={"Items": [], "TotalRecordCount": 0},
            status=200,
        )

        client = EmbyClient(
            server_url="https://emby.example.com",
            access_token="token123",
            user_id="user456",
            device_id="device789",
        )
        since = datetime(2025, 12, 1, 0, 0, 0)
        client.get_watched_items(content_type="movies", since=since)

        # Verify the request included the date filter
        assert "MinDateLastSaved" in responses.calls[0].request.url

    @responses.activate
    def test_get_watched_partial_progress(self):
        """Track partially watched items."""
        responses.add(
            responses.GET,
            "https://emby.example.com/Users/user456/Items",
            json={
                "Items": [
                    {
                        "Id": "movie2",
                        "Name": "Long Movie",
                        "Type": "Movie",
                        "UserData": {
                            "Played": False,
                            "PlayCount": 1,
                            "LastPlayedDate": "2025-12-10T20:00:00.0000000Z",
                            "PlaybackPositionTicks": 4000000000000,
                        },
                        "RunTimeTicks": 8800000000000,
                        "ProviderIds": {},
                    }
                ],
                "TotalRecordCount": 1,
            },
            status=200,
        )

        client = EmbyClient(
            server_url="https://emby.example.com",
            access_token="token123",
            user_id="user456",
            device_id="device789",
        )
        items = client.get_watched_items(content_type="movies", include_partial=True)

        assert len(items) == 1
        assert items[0].is_fully_watched is False
        assert items[0].completion_percentage == pytest.approx(45.45, rel=0.1)
