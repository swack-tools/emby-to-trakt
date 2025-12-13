"""Trakt OAuth2 authentication via device code flow."""

import requests


class TraktAuthError(Exception):
    """Authentication error."""

    pass


class TraktAuth:
    """Handle Trakt OAuth2 device code authentication."""

    API_URL = "https://api.trakt.tv"

    def __init__(self, client_id: str, client_secret: str = None):
        """Initialize with Trakt app credentials.

        Args:
            client_id: The Trakt application client ID.
            client_secret: The Trakt application client secret (required for token exchange).

        Raises:
            ValueError: If client_id is empty or None.
        """
        if not client_id:
            raise ValueError("client_id cannot be empty")
        self.client_id = client_id
        self.client_secret = client_secret

    def _get_headers(self) -> dict:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "trakt-api-key": self.client_id,
            "trakt-api-version": "2",
        }

    def request_device_code(self) -> dict:
        """Request device code for user authorization.

        Returns:
            dict: Contains device_code, user_code, verification_url, expires_in, and interval.

        Raises:
            TraktAuthError: If the API request fails or returns a non-200 status.
        """
        url = f"{self.API_URL}/oauth/device/code"

        try:
            response = requests.post(
                url,
                json={"client_id": self.client_id},
                headers=self._get_headers(),
                timeout=30,
            )
        except requests.RequestException as e:
            raise TraktAuthError(f"Cannot connect to Trakt API: {e}")

        if response.status_code != 200:
            raise TraktAuthError(f"Failed to get device code: {response.status_code}")

        return response.json()

    def poll_for_token(self, device_code: str) -> dict | None:
        """Poll for access token.

        Args:
            device_code: The device code returned from request_device_code().

        Returns:
            dict: Token data with access_token and refresh_token if authorized.
            None: If authorization is still pending.

        Raises:
            TraktAuthError: If the user denies access or the token is expired.
        """
        url = f"{self.API_URL}/oauth/device/token"

        try:
            payload = {
                "code": device_code,
                "client_id": self.client_id,
            }
            if self.client_secret:
                payload["client_secret"] = self.client_secret

            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )
        except requests.RequestException as e:
            raise TraktAuthError(f"Cannot connect to Trakt API: {e}")

        if response.status_code == 200:
            try:
                return response.json()
            except requests.exceptions.JSONDecodeError:
                raise TraktAuthError("Invalid response from Trakt API")

        if response.status_code == 400:
            # Try to parse error, but handle empty responses
            try:
                data = response.json()
                error = data.get("error", "")
            except requests.exceptions.JSONDecodeError:
                # Empty body, treat as pending
                return None

            if error == "authorization_pending":
                return None

            if error in ("access_denied", "expired_token"):
                raise TraktAuthError(f"Authorization denied: {error}")

        # 409 = already used, 410 = expired, 418 = denied
        if response.status_code == 409:
            raise TraktAuthError("Device code already used")
        if response.status_code == 410:
            raise TraktAuthError("Device code expired")
        if response.status_code == 418:
            raise TraktAuthError("User denied authorization")
        if response.status_code == 429:
            # Rate limited, treat as pending (will retry)
            return None

        raise TraktAuthError(f"Token poll failed: {response.status_code}")

    def refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token.

        Args:
            refresh_token: The refresh token to use for obtaining a new access token.

        Returns:
            dict: New token data with access_token and refresh_token.

        Raises:
            TraktAuthError: If the refresh fails or network error occurs.
        """
        url = f"{self.API_URL}/oauth/token"

        try:
            payload = {
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "grant_type": "refresh_token",
            }
            if self.client_secret:
                payload["client_secret"] = self.client_secret

            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )
        except requests.RequestException as e:
            raise TraktAuthError(f"Cannot connect to Trakt API: {e}")

        if response.status_code == 200:
            return response.json()

        raise TraktAuthError(f"Token refresh failed: {response.status_code}")
