"""Tests for Trakt OAuth2 authentication."""

import requests
import responses
import pytest
from emby_to_trakt.trakt_auth import TraktAuth, TraktAuthError


class TestTraktAuthInit:
    """Test TraktAuth initialization."""

    def test_init_with_valid_client_id(self):
        """Initialize with valid client ID."""
        auth = TraktAuth(client_id="test-client-id")
        assert auth.client_id == "test-client-id"

    def test_init_with_empty_client_id(self):
        """Initialize with empty client ID raises ValueError."""
        with pytest.raises(ValueError, match="client_id cannot be empty"):
            TraktAuth(client_id="")

    def test_init_with_none_client_id(self):
        """Initialize with None client ID raises ValueError."""
        with pytest.raises(ValueError, match="client_id cannot be empty"):
            TraktAuth(client_id=None)


class TestDeviceCodeRequest:
    """Test device code request."""

    @responses.activate
    def test_request_device_code_success(self):
        """Request device code returns code and URL."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/code",
            json={
                "device_code": "device123",
                "user_code": "A1B2C3D4",
                "verification_url": "https://trakt.tv/activate",
                "expires_in": 600,
                "interval": 5,
            },
            status=200,
        )

        auth = TraktAuth(client_id="test-client-id")
        result = auth.request_device_code()

        assert result["user_code"] == "A1B2C3D4"
        assert result["verification_url"] == "https://trakt.tv/activate"
        assert result["device_code"] == "device123"
        assert result["interval"] == 5

    @responses.activate
    def test_request_device_code_api_error(self):
        """Request device code with API error raises TraktAuthError."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/code",
            json={"error": "invalid_client"},
            status=401,
        )

        auth = TraktAuth(client_id="test-client-id")
        with pytest.raises(TraktAuthError, match="Failed to get device code: 401"):
            auth.request_device_code()

    @responses.activate
    def test_request_device_code_network_error(self):
        """Request device code with network error raises TraktAuthError."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/code",
            body=requests.exceptions.ConnectionError("Network error"),
        )

        auth = TraktAuth(client_id="test-client-id")
        with pytest.raises(TraktAuthError, match="Cannot connect to Trakt API"):
            auth.request_device_code()


class TestPollForToken:
    """Test polling for access token."""

    @responses.activate
    def test_poll_token_success(self):
        """Poll returns tokens on success."""
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

        auth = TraktAuth(client_id="test-client-id")
        result = auth.poll_for_token("device123")

        assert result["access_token"] == "access123"
        assert result["refresh_token"] == "refresh456"

    @responses.activate
    def test_poll_token_pending(self):
        """Poll returns None when authorization pending."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/token",
            json={"error": "authorization_pending"},
            status=400,
        )

        auth = TraktAuth(client_id="test-client-id")
        result = auth.poll_for_token("device123")

        assert result is None

    @responses.activate
    def test_poll_token_denied(self):
        """Poll raises error when user denies."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/token",
            json={"error": "access_denied"},
            status=400,
        )

        auth = TraktAuth(client_id="test-client-id")

        with pytest.raises(TraktAuthError, match="denied"):
            auth.poll_for_token("device123")

    @responses.activate
    def test_poll_token_network_error(self):
        """Poll raises error on network failure."""
        responses.add(
            responses.POST,
            "https://api.trakt.tv/oauth/device/token",
            body=requests.exceptions.ConnectionError("Network error"),
        )

        auth = TraktAuth(client_id="test-client-id")

        with pytest.raises(TraktAuthError, match="Cannot connect to Trakt API"):
            auth.poll_for_token("device123")
