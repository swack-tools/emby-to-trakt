"""Tests for unmatched items logging."""

import tempfile
from pathlib import Path
from datetime import datetime

import yaml

from emby_to_trakt.unmatched import UnmatchedLogger
from emby_to_trakt.models import WatchedItem


class TestUnmatchedLogger:
    """Test unmatched item logging."""

    def test_log_unmatched_item(self):
        """Log unmatched item to YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = UnmatchedLogger(data_dir=Path(tmpdir))

            item = WatchedItem(
                emby_id="123",
                title="Unknown Movie",
                item_type="movie",
                watched_date=datetime(2025, 12, 1),
                play_count=1,
                is_fully_watched=True,
                completion_percentage=100.0,
                playback_position_ticks=0,
                runtime_ticks=0,
            )

            logger.log(item, reason="No provider IDs")
            logger.save()

            # Verify file contents
            unmatched_path = Path(tmpdir) / "unmatched.yaml"
            assert unmatched_path.exists()

            with open(unmatched_path) as f:
                data = yaml.safe_load(f)

            assert len(data["items"]) == 1
            assert data["items"][0]["title"] == "Unknown Movie"
            assert data["items"][0]["reason"] == "No provider IDs"

    def test_log_multiple_items(self):
        """Log multiple unmatched items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = UnmatchedLogger(data_dir=Path(tmpdir))

            for i in range(3):
                item = WatchedItem(
                    emby_id=str(i),
                    title=f"Movie {i}",
                    item_type="movie",
                    watched_date=datetime(2025, 12, 1),
                    play_count=1,
                    is_fully_watched=True,
                    completion_percentage=100.0,
                    playback_position_ticks=0,
                    runtime_ticks=0,
                )
                logger.log(item, reason="No IDs")

            logger.save()

            unmatched_path = Path(tmpdir) / "unmatched.yaml"
            with open(unmatched_path) as f:
                data = yaml.safe_load(f)

            assert len(data["items"]) == 3
