"""YAML storage for watched items."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

import yaml

from emby_to_trakt.models import WatchedItem


class DataStore:
    """Manages watched items storage in YAML format."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize data store."""
        if data_dir is None:
            data_dir = Path.cwd() / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.watched_path = self.data_dir / "watched.yaml"
        self.synced_path = self.data_dir / "synced_to_trakt.yaml"

    def save_watched_items(self, items: List[WatchedItem]) -> None:
        """Save watched items to YAML file."""
        data = {
            "sync_metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_items": len(items),
            },
            "watched_items": [item.to_dict() for item in items],
        }

        with open(self.watched_path, "w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
            )

    def load_watched_items(self) -> List[WatchedItem]:
        """Load watched items from YAML file."""
        if not self.watched_path.exists():
            return []

        with open(self.watched_path) as f:
            data = yaml.safe_load(f)

        if not data or "watched_items" not in data:
            return []

        return [WatchedItem.from_dict(item_data) for item_data in data["watched_items"]]

    def get_last_sync_time(self) -> Optional[datetime]:
        """Get timestamp of last sync."""
        if not self.watched_path.exists():
            return None

        with open(self.watched_path) as f:
            data = yaml.safe_load(f)

        if not data or "sync_metadata" not in data:
            return None

        last_updated = data["sync_metadata"].get("last_updated")
        if last_updated:
            return datetime.fromisoformat(last_updated)
        return None

    def load_synced_ids(self) -> Set[str]:
        """Load set of emby_ids that have been pushed to Trakt."""
        if not self.synced_path.exists():
            return set()

        with open(self.synced_path) as f:
            data = yaml.safe_load(f)

        if not data or "synced_ids" not in data:
            return set()

        return set(data["synced_ids"])

    def mark_as_synced(self, items: List[WatchedItem]) -> None:
        """Mark items as synced to Trakt."""
        synced_ids = self.load_synced_ids()
        for item in items:
            synced_ids.add(item.emby_id)

        data = {
            "last_push": datetime.now().isoformat(),
            "total_synced": len(synced_ids),
            "synced_ids": sorted(synced_ids),
        }

        with open(self.synced_path, "w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
            )

    def filter_unsynced(self, items: List[WatchedItem]) -> List[WatchedItem]:
        """Return only items that haven't been synced to Trakt yet."""
        synced_ids = self.load_synced_ids()
        return [item for item in items if item.emby_id not in synced_ids]

    def get_synced_count(self) -> int:
        """Get count of items synced to Trakt."""
        return len(self.load_synced_ids())
