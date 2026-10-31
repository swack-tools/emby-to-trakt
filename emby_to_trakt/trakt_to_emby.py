"""Match Trakt watched history to Emby library items."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# Provider ID keys as they appear in Trakt "ids" objects, mapped to Emby's
# ProviderIds keys. Checked in this order.
PROVIDERS = (("imdb", "Imdb"), ("tmdb", "Tmdb"), ("tvdb", "Tvdb"))


@dataclass
class PlannedPlay:
    """An Emby item that should be marked played."""

    emby_id: str
    title: str
    item_type: str  # "movie" or "episode"
    watched_at: Optional[datetime]
    series_name: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None


@dataclass
class PullPlan:
    """Result of matching Trakt history against the Emby library."""

    to_mark: List[PlannedPlay] = field(default_factory=list)
    already_played: int = 0
    unmatched: List[dict] = field(default_factory=list)

    @property
    def movies(self) -> List[PlannedPlay]:
        return [p for p in self.to_mark if p.item_type == "movie"]

    @property
    def episodes(self) -> List[PlannedPlay]:
        return [p for p in self.to_mark if p.item_type == "episode"]


def parse_trakt_date(value: Optional[str]) -> Optional[datetime]:
    """Parse a Trakt timestamp (e.g. 2025-01-02T03:04:05.000Z) as naive UTC."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").split(".")[0])
    except (ValueError, AttributeError):
        return None


def _keys_for_emby(item: dict) -> List[Tuple[str, str]]:
    provider_ids = item.get("ProviderIds") or {}
    # Emby's casing of provider keys is not always consistent.
    lowered = {k.lower(): v for k, v in provider_ids.items() if v}
    keys = []
    for trakt_key, emby_key in PROVIDERS:
        value = lowered.get(emby_key.lower())
        if value:
            keys.append((trakt_key, str(value).strip().lower()))
    return keys


def _keys_for_trakt(ids: dict) -> List[Tuple[str, str]]:
    keys = []
    for trakt_key, _ in PROVIDERS:
        value = (ids or {}).get(trakt_key)
        if value:
            keys.append((trakt_key, str(value).strip().lower()))
    return keys


def _build_index(items: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    """Index Emby items by every provider ID they carry.

    A key can map to several items, e.g. the same movie in two libraries.
    """
    index: Dict[Tuple[str, str], List[dict]] = {}
    for item in items:
        for key in _keys_for_emby(item):
            index.setdefault(key, []).append(item)
    return index


def _lookup(index: Dict[Tuple[str, str], List[dict]], ids: dict) -> List[dict]:
    for key in _keys_for_trakt(ids):
        if key in index:
            return index[key]
    return []


def _is_played(item: dict) -> bool:
    return bool((item.get("UserData") or {}).get("Played"))


def build_pull_plan(
    trakt_movies: List[dict],
    trakt_shows: List[dict],
    emby_movies: List[dict],
    emby_series: List[dict],
    emby_episodes: List[dict],
) -> PullPlan:
    """Work out which Emby items to mark played from Trakt watched data.

    Args:
        trakt_movies: Response of Trakt GET /sync/watched/movies
        trakt_shows: Response of Trakt GET /sync/watched/shows
        emby_movies: Raw Emby Movie items
        emby_series: Raw Emby Series items
        emby_episodes: Raw Emby Episode items

    Items already played on Emby are skipped. Nothing is ever unmarked.
    """
    plan = PullPlan()

    # Movies
    movie_index = _build_index(emby_movies)
    for entry in trakt_movies:
        movie = entry.get("movie", {})
        matches = _lookup(movie_index, movie.get("ids", {}))
        if not matches:
            plan.unmatched.append(
                {
                    "type": "movie",
                    "title": movie.get("title"),
                    "year": movie.get("year"),
                    "ids": movie.get("ids", {}),
                    "reason": "Not found in Emby library",
                }
            )
            continue

        watched_at = parse_trakt_date(entry.get("last_watched_at"))
        for item in matches:
            if _is_played(item):
                plan.already_played += 1
                continue
            plan.to_mark.append(
                PlannedPlay(
                    emby_id=item["Id"],
                    title=item.get("Name") or movie.get("title") or "",
                    item_type="movie",
                    watched_at=watched_at,
                )
            )

    # Episodes: match the show by provider ID, then episodes by number.
    series_index = _build_index(emby_series)
    episodes_by_series: Dict[str, Dict[Tuple[int, int], List[dict]]] = {}
    for ep in emby_episodes:
        series_id = ep.get("SeriesId")
        season = ep.get("ParentIndexNumber")
        number = ep.get("IndexNumber")
        if series_id is None or season is None or number is None:
            continue
        by_number = episodes_by_series.setdefault(series_id, {})
        by_number.setdefault((season, number), []).append(ep)
        # Multi-episode files (e.g. S01E01-E02) carry IndexNumberEnd.
        end = ep.get("IndexNumberEnd")
        if end and end > number:
            for extra in range(number + 1, end + 1):
                by_number.setdefault((season, extra), []).append(ep)

    for entry in trakt_shows:
        show = entry.get("show", {})
        series_matches = _lookup(series_index, show.get("ids", {}))
        if not series_matches:
            plan.unmatched.append(
                {
                    "type": "show",
                    "title": show.get("title"),
                    "year": show.get("year"),
                    "ids": show.get("ids", {}),
                    "reason": "Show not found in Emby library",
                }
            )
            continue

        seen_ids = set()
        for season in entry.get("seasons", []):
            season_number = season.get("number")
            for episode in season.get("episodes", []):
                episode_number = episode.get("number")
                watched_at = parse_trakt_date(episode.get("last_watched_at"))

                found = []
                for series in series_matches:
                    found.extend(
                        episodes_by_series.get(series["Id"], {}).get(
                            (season_number, episode_number), []
                        )
                    )

                if not found:
                    plan.unmatched.append(
                        {
                            "type": "episode",
                            "title": show.get("title"),
                            "season": season_number,
                            "episode": episode_number,
                            "ids": show.get("ids", {}),
                            "reason": "Episode not found in Emby library",
                        }
                    )
                    continue

                for item in found:
                    if item["Id"] in seen_ids:
                        continue
                    seen_ids.add(item["Id"])
                    if _is_played(item):
                        plan.already_played += 1
                        continue
                    plan.to_mark.append(
                        PlannedPlay(
                            emby_id=item["Id"],
                            title=item.get("Name") or "",
                            item_type="episode",
                            watched_at=watched_at,
                            series_name=item.get("SeriesName") or show.get("title"),
                            season_number=season_number,
                            episode_number=episode_number,
                        )
                    )

    return plan


def save_unmatched(data_dir: Path, unmatched: List[dict]) -> Path:
    """Write Trakt items with no Emby match to a YAML report."""
    path = Path(data_dir) / "unmatched_trakt_to_emby.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "logged_at": datetime.now().isoformat(),
        "count": len(unmatched),
        "items": unmatched,
    }
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path
