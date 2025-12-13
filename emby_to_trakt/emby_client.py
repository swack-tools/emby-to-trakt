"""Emby API client."""

import uuid
from datetime import datetime
from typing import List, Optional

import requests

from emby_to_trakt.models import WatchedItem


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
        # Build authorization header in MediaBrowser format
        auth_parts = [
            f'Client="{self.CLIENT_NAME}"',
            f'Device="emby-sync"',
            f'DeviceId="{self.device_id}"',
            f'Version="{self.CLIENT_VERSION}"',
        ]
        if self.access_token:
            auth_parts.append(f'Token="{self.access_token}"')

        headers = {
            "X-Emby-Authorization": f"MediaBrowser {', '.join(auth_parts)}",
        }
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

    def get_watched_items(
        self,
        content_type: str,
        since: Optional[datetime] = None,
        include_partial: bool = True,
    ) -> List[WatchedItem]:
        """Fetch watched items from Emby.

        Args:
            content_type: "movies" or "episodes"
            since: Only fetch items watched after this date (incremental sync)
            include_partial: Include partially watched items

        Returns:
            List of WatchedItem objects
        """
        if content_type == "movies":
            item_types = "Movie"
        elif content_type == "episodes":
            item_types = "Episode"
        else:
            raise ValueError(f"Invalid content type: {content_type}")

        # Build list of filters to query
        filters_to_query = ["IsPlayed"]
        if include_partial:
            filters_to_query.append("IsResumable")

        all_items = {}  # Use dict to deduplicate by emby_id

        for filter_value in filters_to_query:
            params = {
                "IncludeItemTypes": item_types,
                "Recursive": "true",
                "Fields": "ProviderIds,UserData,RunTimeTicks,Path",
                "Filters": filter_value,
            }

            if since:
                params["MinDateLastSaved"] = since.isoformat()

            url = f"{self.server_url}/Users/{self.user_id}/Items"

            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=60,
                )
            except requests.RequestException as e:
                raise EmbyConnectionError(f"Cannot connect to Emby server: {e}")

            if response.status_code == 401:
                raise EmbyAuthError("Access token expired or invalid")
            if response.status_code != 200:
                raise EmbyConnectionError(
                    f"Emby server error: {response.status_code}"
                )

            data = response.json()

            for raw_item in data.get("Items", []):
                item = self._parse_item(raw_item)
                if item and item.emby_id not in all_items:
                    all_items[item.emby_id] = item

        return list(all_items.values())

    def _parse_item(self, raw: dict) -> Optional[WatchedItem]:
        """Parse Emby API item into WatchedItem."""
        user_data = raw.get("UserData", {})
        provider_ids = raw.get("ProviderIds", {})

        # Parse watched date
        last_played = user_data.get("LastPlayedDate")
        if last_played:
            # Handle Emby's timestamp format
            watched_date = datetime.fromisoformat(
                last_played.replace("Z", "+00:00").split(".")[0]
            )
        else:
            watched_date = datetime.now()

        # Calculate completion percentage
        runtime_ticks = raw.get("RunTimeTicks", 0)
        position_ticks = user_data.get("PlaybackPositionTicks", 0)
        if runtime_ticks > 0:
            completion = (position_ticks / runtime_ticks) * 100
        else:
            completion = 100.0 if user_data.get("Played") else 0.0

        item_type = raw.get("Type", "").lower()
        if item_type not in ("movie", "episode"):
            return None

        return WatchedItem(
            emby_id=raw.get("Id", ""),
            title=raw.get("Name", ""),
            item_type=item_type,
            watched_date=watched_date,
            play_count=user_data.get("PlayCount", 0),
            is_fully_watched=user_data.get("Played", False),
            completion_percentage=round(completion, 2),
            playback_position_ticks=position_ticks,
            runtime_ticks=runtime_ticks,
            imdb_id=provider_ids.get("Imdb"),
            tmdb_id=provider_ids.get("Tmdb"),
            tvdb_id=provider_ids.get("Tvdb"),
            user_rating=user_data.get("Rating"),
            series_name=raw.get("SeriesName") if item_type == "episode" else None,
            season_number=raw.get("ParentIndexNumber") if item_type == "episode" else None,
            episode_number=raw.get("IndexNumber") if item_type == "episode" else None,
            raw_metadata=raw,
        )
