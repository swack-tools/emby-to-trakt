"""Trakt OAuth2 authentication via device code flow."""

import requests


class TraktAuthError(Exception):
    """Authentication error."""
    pass


class TraktAuth:
    """Handle Trakt OAuth2 device code authentication."""

    API_URL = "https://api.trakt.tv"

    def __init__(self, client_id: str):
        """Initialize with Trakt app client ID."""
        self.client_id = client_id

    def _get_headers(self) -> dict:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "trakt-api-key": self.client_id,
            "trakt-api-version": "2",
        }

    def request_device_code(self) -> dict:
        """Request device code for user authorization.

        Returns dict with device_code, user_code, verification_url, interval.
        """
        url = f"{self.API_URL}/oauth/device/code"

        response = requests.post(
            url,
            json={"client_id": self.client_id},
            headers=self._get_headers(),
            timeout=30,
        )

        if response.status_code != 200:
            raise TraktAuthError(f"Failed to get device code: {response.status_code}")

        return response.json()
