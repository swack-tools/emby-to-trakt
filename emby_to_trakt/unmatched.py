"""Log unmatched items for review."""

from datetime import datetime
from pathlib import Path
from typing import List

import yaml

from emby_to_trakt.models import WatchedItem


class UnmatchedLogger:
    """Log items that couldn't be matched on Trakt."""

    def __init__(self, data_dir: Path):
        """Initialize logger."""
        self.data_dir = data_dir
        self.unmatched_path = data_dir / "unmatched.yaml"
        self.items: List[dict] = []

    def log(self, item: WatchedItem, reason: str) -> None:
        """Log an unmatched item."""
        self.items.append({
            "title": item.title,
            "item_type": item.item_type,
            "emby_id": item.emby_id,
            "imdb_id": item.imdb_id,
            "tmdb_id": item.tmdb_id,
            "tvdb_id": item.tvdb_id,
            "reason": reason,
        })

    def save(self) -> None:
        """Save unmatched items to YAML."""
        if not self.items:
            return

        self.data_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "logged_at": datetime.now().isoformat(),
            "count": len(self.items),
            "items": self.items,
        }

        with open(self.unmatched_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def count(self) -> int:
        """Return count of unmatched items."""
        return len(self.items)
