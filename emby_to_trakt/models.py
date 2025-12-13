"""Data models for Emby watched items."""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional


@dataclass
class WatchedItem:
    """Represents a watched movie or episode from Emby."""

    emby_id: str
    title: str
    item_type: str  # "movie" or "episode"
    watched_date: datetime
    play_count: int
    is_fully_watched: bool
    completion_percentage: float
    playback_position_ticks: int
    runtime_ticks: int

    # Provider IDs for Trakt matching
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None

    # User data
    user_rating: Optional[float] = None

    # Episode-specific fields
    series_name: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None

    # Full metadata dump
    raw_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        data = asdict(self)
        # Convert datetime to ISO string
        data["watched_date"] = self.watched_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "WatchedItem":
        """Reconstruct from dictionary."""
        # Convert ISO string back to datetime
        if isinstance(data["watched_date"], str):
            data["watched_date"] = datetime.fromisoformat(data["watched_date"])
        return cls(**data)
