"""Tests for data models."""

from datetime import datetime
from emby_to_trakt.models import WatchedItem


def test_watched_item_movie():
    """WatchedItem represents a watched movie."""
    item = WatchedItem(
        emby_id="12345",
        title="Inception",
        item_type="movie",
        watched_date=datetime(2025, 11, 15, 20, 30),
        play_count=2,
        is_fully_watched=True,
        completion_percentage=100.0,
        playback_position_ticks=0,
        runtime_ticks=8880000000,
        imdb_id="tt1375666",
        tmdb_id="27205",
        tvdb_id=None,
        user_rating=9.0,
        series_name=None,
        season_number=None,
        episode_number=None,
        raw_metadata={"Name": "Inception"},
    )
    assert item.emby_id == "12345"
    assert item.title == "Inception"
    assert item.item_type == "movie"
    assert item.is_fully_watched is True
    assert item.imdb_id == "tt1375666"


def test_watched_item_episode():
    """WatchedItem represents a watched episode."""
    item = WatchedItem(
        emby_id="67890",
        title="Pilot",
        item_type="episode",
        watched_date=datetime(2025, 12, 1, 21, 0),
        play_count=1,
        is_fully_watched=True,
        completion_percentage=100.0,
        playback_position_ticks=0,
        runtime_ticks=3600000000,
        imdb_id="tt1234567",
        tmdb_id=None,
        tvdb_id="123456",
        user_rating=None,
        series_name="Breaking Bad",
        season_number=1,
        episode_number=1,
        raw_metadata={"Name": "Pilot"},
    )
    assert item.item_type == "episode"
    assert item.series_name == "Breaking Bad"
    assert item.season_number == 1
    assert item.episode_number == 1


def test_watched_item_partial():
    """WatchedItem tracks partial watch progress."""
    item = WatchedItem(
        emby_id="99999",
        title="Long Movie",
        item_type="movie",
        watched_date=datetime(2025, 12, 10),
        play_count=1,
        is_fully_watched=False,
        completion_percentage=45.5,
        playback_position_ticks=4000000000,
        runtime_ticks=8800000000,
        imdb_id=None,
        tmdb_id=None,
        tvdb_id=None,
        user_rating=None,
        series_name=None,
        season_number=None,
        episode_number=None,
        raw_metadata={},
    )
    assert item.is_fully_watched is False
    assert item.completion_percentage == 45.5


def test_watched_item_to_dict():
    """WatchedItem converts to dictionary."""
    item = WatchedItem(
        emby_id="12345",
        title="Test",
        item_type="movie",
        watched_date=datetime(2025, 1, 1),
        play_count=1,
        is_fully_watched=True,
        completion_percentage=100.0,
        playback_position_ticks=0,
        runtime_ticks=1000,
        imdb_id=None,
        tmdb_id=None,
        tvdb_id=None,
        user_rating=None,
        series_name=None,
        season_number=None,
        episode_number=None,
        raw_metadata={},
    )
    d = item.to_dict()
    assert d["emby_id"] == "12345"
    assert d["title"] == "Test"
    assert d["watched_date"] == "2025-01-01T00:00:00"


def test_watched_item_from_dict():
    """WatchedItem reconstructs from dictionary."""
    data = {
        "emby_id": "12345",
        "title": "Test",
        "item_type": "movie",
        "watched_date": "2025-01-01T00:00:00",
        "play_count": 1,
        "is_fully_watched": True,
        "completion_percentage": 100.0,
        "playback_position_ticks": 0,
        "runtime_ticks": 1000,
        "imdb_id": None,
        "tmdb_id": None,
        "tvdb_id": None,
        "user_rating": None,
        "series_name": None,
        "season_number": None,
        "episode_number": None,
        "raw_metadata": {},
    }
    item = WatchedItem.from_dict(data)
    assert item.emby_id == "12345"
    assert item.watched_date == datetime(2025, 1, 1)
