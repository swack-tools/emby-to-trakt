"""Tests for Trakt API client."""

import responses
import requests
from datetime import datetime
from emby_to_trakt.trakt_client import TraktClient, TraktError
from emby_to_trakt.models import WatchedItem


class TestTraktConnection:
    """Test Trakt connection."""

    @responses.activate
    def test_test_connection_success(self):
        """Test connection returns True on success."""
        responses.add(
            responses.GET,
            "https://api.trakt.tv/users/me",
            json={"username": "testuser"},
            status=200,
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        assert client.test_connection() is True

    @responses.activate
    def test_test_connection_invalid_token(self):
        """Test connection returns False on 401."""
        responses.add(
            responses.GET,
            "https://api.trakt.tv/users/me",
            status=401,
        )

        client = TraktClient(
            client_id="test-client",
            access_token="bad-token",
        )

        assert client.test_connection() is False

    @responses.activate
    def test_test_connection_network_error(self):
        """Test connection returns False on network error."""
        responses.add(
            responses.GET,
            "https://api.trakt.tv/users/me",
            body=requests.exceptions.ConnectionError("Network error"),
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        assert client.test_connection() is False

    @responses.activate
    def test_test_connection_timeout(self):
        """Test connection returns False on timeout."""
        responses.add(
            responses.GET,
            "https://api.trakt.tv/users/me",
            body=requests.exceptions.Timeout("Request timeout"),
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        assert client.test_connection() is False


class TestSyncHistory:
    """Test syncing watch history."""

    @responses.activate
    def test_sync_history_movies(self):
        """Sync movies to Trakt history."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 2, "episodes": 0}},
            status=201,
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        items = [
            WatchedItem(
                emby_id="1",
                title="Movie 1",
                item_type="movie",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                imdb_id="tt1234567",
            ),
            WatchedItem(
                emby_id="2",
                title="Movie 2",
                item_type="movie",
                watched_date=datetime(2025, 12, 2),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                tmdb_id="12345",
            ),
        ]

        result = client.sync_history(items)

        assert result["added"]["movies"] == 2

    @responses.activate
    def test_sync_history_episodes(self):
        """Sync episodes to Trakt history."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 0, "episodes": 1}},
            status=201,
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        items = [
            WatchedItem(
                emby_id="3",
                title="Episode 1",
                item_type="episode",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                tvdb_id="123",
                series_name="Test Show",
                season_number=1,
                episode_number=1,
            ),
        ]

        result = client.sync_history(items)

        assert result["added"]["episodes"] == 1

    @responses.activate
    def test_sync_history_mixed_content(self):
        """Sync both movies and episodes."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"added": {"movies": 1, "episodes": 1}},
            status=201,
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        items = [
            WatchedItem(
                emby_id="1",
                title="Movie 1",
                item_type="movie",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                imdb_id="tt1234567",
            ),
            WatchedItem(
                emby_id="2",
                title="Episode 1",
                item_type="episode",
                watched_date=datetime(2025, 12, 2),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                tvdb_id="123",
                series_name="Test Show",
                season_number=1,
                episode_number=1,
            ),
        ]

        result = client.sync_history(items)

        assert result["added"]["movies"] == 1
        assert result["added"]["episodes"] == 1

    def test_sync_history_empty_list(self):
        """Sync with empty list returns zeros."""
        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        result = client.sync_history([])

        assert result["added"]["movies"] == 0
        assert result["added"]["episodes"] == 0

    def test_sync_history_no_provider_ids(self):
        """Sync skips items without provider IDs."""
        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        items = [
            WatchedItem(
                emby_id="1",
                title="Unknown Movie",
                item_type="movie",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
            ),
        ]

        result = client.sync_history(items)

        assert result["added"]["movies"] == 0
        assert result["added"]["episodes"] == 0

    @responses.activate
    def test_sync_history_network_error(self):
        """Sync handles network errors."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            body=requests.exceptions.ConnectionError("Network error"),
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        items = [
            WatchedItem(
                emby_id="1",
                title="Movie 1",
                item_type="movie",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                imdb_id="tt1234567",
            ),
        ]

        try:
            client.sync_history(items)
            assert False, "Should have raised TraktError"
        except TraktError as e:
            assert "network" in str(e).lower() or "connection" in str(e).lower()

    @responses.activate
    def test_sync_history_api_error(self):
        """Sync handles API errors."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/sync/history",
            json={"error": "invalid_request"},
            status=400,
        )

        client = TraktClient(
            client_id="test-client",
            access_token="test-token",
        )

        items = [
            WatchedItem(
                emby_id="1",
                title="Movie 1",
                item_type="movie",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
                imdb_id="tt1234567",
            ),
        ]

        try:
            client.sync_history(items)
            assert False, "Should have raised TraktError"
        except TraktError as e:
            assert "400" in str(e) or "sync failed" in str(e).lower()
