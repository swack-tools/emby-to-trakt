"""Tests for Trakt API client."""

import responses
import requests
from emby_to_trakt.trakt_client import TraktClient


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
