"""Tests for Trakt OAuth2 authentication."""

import responses
import pytest
from emby_to_trakt.trakt_auth import TraktAuth, TraktAuthError


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
