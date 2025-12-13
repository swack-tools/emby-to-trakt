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

    def sync_history(self, items: List[WatchedItem]) -> dict:
        """Sync watched items to Trakt history.

        Returns dict with added counts.
        """
        movies = []
        episodes = []

        for item in items:
            if item.item_type == "movie":
                movie_data = self._build_movie_data(item)
                if movie_data:
                    movies.append(movie_data)
            elif item.item_type == "episode":
                episode_data = self._build_episode_data(item)
                if episode_data:
                    episodes.append(episode_data)

        payload = {}
        if movies:
            payload["movies"] = movies
        if episodes:
            payload["episodes"] = episodes

        if not payload:
            return {"added": {"movies": 0, "episodes": 0}}

        url = f"{self.API_URL}/sync/history"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=60,
            )

            if response.status_code not in (200, 201):
                raise TraktError(f"Sync failed: {response.status_code}")

            return response.json()
        except requests.RequestException as e:
            raise TraktError(f"Network error during sync: {e}")

    def _build_movie_data(self, item: WatchedItem) -> dict | None:
        """Build Trakt movie object from WatchedItem."""
        ids = {}
        if item.imdb_id:
            ids["imdb"] = item.imdb_id
        elif item.tmdb_id:
            ids["tmdb"] = int(item.tmdb_id)

        if not ids:
            return None

        return {
            "watched_at": item.watched_date.isoformat() + "Z",
            "ids": ids,
        }

    def _build_episode_data(self, item: WatchedItem) -> dict | None:
        """Build Trakt episode object from WatchedItem."""
        ids = {}
        if item.tvdb_id:
            ids["tvdb"] = int(item.tvdb_id)
        elif item.imdb_id:
            ids["imdb"] = item.imdb_id

        if not ids:
            return None

        return {
            "watched_at": item.watched_date.isoformat() + "Z",
            "ids": ids,
        }
