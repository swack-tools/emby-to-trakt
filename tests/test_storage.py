"""Tests for YAML storage layer."""

from datetime import datetime
from pathlib import Path

import pytest
import yaml

from emby_to_trakt.models import WatchedItem
from emby_to_trakt.storage import DataStore


@pytest.fixture
def sample_items():
    """Create sample watched items for testing."""
    return [
        WatchedItem(
            emby_id="movie1",
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
        ),
        WatchedItem(
            emby_id="ep1",
            title="Pilot",
            item_type="episode",
            watched_date=datetime(2025, 12, 1, 21, 0),
            play_count=1,
            is_fully_watched=True,
            completion_percentage=100.0,
            playback_position_ticks=0,
            runtime_ticks=3600000000,
            imdb_id=None,
            tmdb_id=None,
            tvdb_id="123456",
            user_rating=None,
            series_name="Breaking Bad",
            season_number=1,
            episode_number=1,
            raw_metadata={"Name": "Pilot"},
        ),
    ]


def test_save_watched_items(tmp_path, sample_items):
    """DataStore saves watched items to YAML."""
    store = DataStore(data_dir=tmp_path)
    store.save_watched_items(sample_items)

    # Verify file exists
    assert (tmp_path / "watched.yaml").exists()

    # Verify content
    with open(tmp_path / "watched.yaml") as f:
        data = yaml.safe_load(f)

    assert "sync_metadata" in data
    assert data["sync_metadata"]["total_items"] == 2
    assert "watched_items" in data
    assert len(data["watched_items"]) == 2
    assert data["watched_items"][0]["title"] == "Inception"


def test_load_watched_items(tmp_path, sample_items):
    """DataStore loads watched items from YAML."""
    store = DataStore(data_dir=tmp_path)
    store.save_watched_items(sample_items)

    # Load in new instance
    store2 = DataStore(data_dir=tmp_path)
    loaded = store2.load_watched_items()

    assert len(loaded) == 2
    assert loaded[0].emby_id == "movie1"
    assert loaded[0].title == "Inception"
    assert loaded[1].series_name == "Breaking Bad"


def test_load_empty_file(tmp_path):
    """DataStore returns empty list for missing file."""
    store = DataStore(data_dir=tmp_path)
    items = store.load_watched_items()
    assert items == []


def test_sync_metadata_timestamp(tmp_path, sample_items):
    """DataStore records sync timestamp in metadata."""
    store = DataStore(data_dir=tmp_path)
    store.save_watched_items(sample_items)

    with open(tmp_path / "watched.yaml") as f:
        data = yaml.safe_load(f)

    # Verify timestamp is recent
    last_updated = datetime.fromisoformat(data["sync_metadata"]["last_updated"])
    assert (datetime.now() - last_updated).total_seconds() < 10


def test_watched_yaml_is_human_readable(tmp_path, sample_items):
    """YAML output is formatted for readability."""
    store = DataStore(data_dir=tmp_path)
    store.save_watched_items(sample_items)

    content = (tmp_path / "watched.yaml").read_text()

    # Check for readable formatting (not inline)
    assert "watched_items:" in content
    assert "- emby_id:" in content
    assert "  title:" in content
