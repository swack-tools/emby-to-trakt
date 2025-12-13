"""Trakt API client for syncing watch history."""

import requests
from typing import List, Optional

from emby_to_trakt.models import WatchedItem


class TraktError(Exception):
    """Trakt API error."""
    pass


class TraktClient:
    """Client for Trakt API."""

    API_URL = "https://api.trakt.tv"

    def __init__(self, client_id: str, access_token: str):
        """Initialize Trakt client."""
        self.client_id = client_id
        self.access_token = access_token

    def _get_headers(self) -> dict:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "trakt-api-key": self.client_id,
            "trakt-api-version": "2",
        }

    def test_connection(self) -> bool:
        """Test connection to Trakt.

        Returns True if connected, False otherwise.
        """
        url = f"{self.API_URL}/users/me"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
