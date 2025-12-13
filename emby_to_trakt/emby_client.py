"""Emby API client."""

import uuid
from typing import Optional

import requests


class EmbyAuthError(Exception):
    """Authentication error."""

    pass


class EmbyConnectionError(Exception):
    """Connection error."""

    pass


class EmbyClient:
    """Client for Emby REST API."""

    CLIENT_NAME = "emby-sync-cli"
    CLIENT_VERSION = "0.1.0"

    def __init__(
        self,
        server_url: str,
        access_token: Optional[str] = None,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ):
        """Initialize Emby client."""
        self.server_url = server_url.rstrip("/")
        self.access_token = access_token
        self.user_id = user_id
        self.device_id = device_id or str(uuid.uuid4())

    def _get_headers(self) -> dict:
        """Build request headers."""
        headers = {
            "X-Emby-Client": self.CLIENT_NAME,
            "X-Emby-Client-Version": self.CLIENT_VERSION,
            "X-Emby-Device-Id": self.device_id,
            "X-Emby-Device-Name": "emby-sync",
        }
        if self.access_token:
            headers["X-Emby-Token"] = self.access_token
        return headers

    def authenticate(self, username: str, password: str) -> dict:
        """Authenticate with Emby server.

        Returns dict with access_token, user_id, and device_id.
        """
        url = f"{self.server_url}/Users/AuthenticateByName"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        try:
            response = requests.post(
                url,
                json={"Username": username, "Pw": password},
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as e:
            raise EmbyConnectionError(f"Cannot connect to Emby server: {e}")

        if response.status_code == 401:
            raise EmbyAuthError("Invalid username or password")
        if response.status_code != 200:
            raise EmbyConnectionError(
                f"Emby server error: {response.status_code}"
            )

        data = response.json()
        self.access_token = data["AccessToken"]
        self.user_id = data["User"]["Id"]

        return {
            "access_token": self.access_token,
            "user_id": self.user_id,
            "device_id": self.device_id,
        }

    def test_connection(self) -> bool:
        """Test connection to Emby server.

        Returns True if connection is valid, False otherwise.
        """
        url = f"{self.server_url}/System/Info"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
