"""Tests for Emby API client."""

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
