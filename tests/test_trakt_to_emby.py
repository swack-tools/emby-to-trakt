"""Tests for Trakt to Emby matching and the pull command."""

from datetime import datetime

import responses
from click.testing import CliRunner

from emby_to_trakt.cli import cli
from emby_to_trakt.config import Config
from emby_to_trakt.emby_client import EmbyClient
from emby_to_trakt.trakt_to_emby import build_pull_plan, parse_trakt_date

EMBY = "https://emby.example.com"
ITEMS_URL = f"{EMBY}/Users/user1/Items"


def _movie(id_, name, played=False, **ids):
    return {"Id": id_, "Name": name, "ProviderIds": ids, "UserData": {"Played": played}}


def _episode(id_, series_id, season, number, played=False, end=None):
    ep = {
        "Id": id_,
        "Name": f"Ep {number}",
        "SeriesId": series_id,
        "SeriesName": "Show",
        "ParentIndexNumber": season,
        "IndexNumber": number,
        "ProviderIds": {},
        "UserData": {"Played": played},
    }
    if end:
        ep["IndexNumberEnd"] = end
    return ep


TRAKT_MOVIES = [
    {
        "plays": 1,
        "last_watched_at": "2024-05-01T20:00:00.000Z",
        "movie": {"title": "Alpha", "year": 2000, "ids": {"imdb": "tt001", "tmdb": 1}},
    },
    {
        "plays": 1,
        "last_watched_at": "2024-05-02T20:00:00.000Z",
        "movie": {"title": "Beta", "year": 2001, "ids": {"imdb": "tt002", "tmdb": 2}},
    },
    {
        "plays": 1,
        "last_watched_at": "2024-05-03T20:00:00.000Z",
        "movie": {"title": "Gamma", "year": 2002, "ids": {"imdb": "tt999", "tmdb": 999}},
    },
]

TRAKT_SHOWS = [
    {
        "show": {"title": "Show", "year": 2010, "ids": {"tvdb": 500, "imdb": "tt500"}},
        "seasons": [
            {
                "number": 1,
                "episodes": [
                    {"number": 1, "last_watched_at": "2024-06-01T10:00:00.000Z"},
                    {"number": 2, "last_watched_at": "2024-06-02T10:00:00.000Z"},
                    {"number": 3, "last_watched_at": "2024-06-03T10:00:00.000Z"},
                    {"number": 9, "last_watched_at": "2024-06-04T10:00:00.000Z"},
                ],
            }
        ],
    },
    {
        "show": {"title": "Missing Show", "ids": {"tvdb": 777}},
        "seasons": [{"number": 1, "episodes": [{"number": 1}]}],
    },
]


class TestBuildPullPlan:
    def test_movies_match_skip_played_and_report_missing(self):
        emby_movies = [
            _movie("m1", "Alpha", Imdb="tt001"),
            _movie("m2", "Beta", played=True, Tmdb="2"),
        ]
        plan = build_pull_plan(TRAKT_MOVIES, [], emby_movies, [], [])

        assert [p.emby_id for p in plan.to_mark] == ["m1"]
        assert plan.to_mark[0].watched_at == datetime(2024, 5, 1, 20, 0, 0)
        assert plan.already_played == 1
        assert [u["title"] for u in plan.unmatched] == ["Gamma"]

    def test_movie_falls_back_to_tmdb_and_ignores_key_case(self):
        emby_movies = [_movie("m1", "Alpha", tmdb="1")]
        plan = build_pull_plan(TRAKT_MOVIES[:1], [], emby_movies, [], [])
        assert [p.emby_id for p in plan.to_mark] == ["m1"]

    def test_duplicate_copies_are_all_marked(self):
        emby_movies = [
            _movie("m1", "Alpha", Imdb="tt001"),
            _movie("m1-4k", "Alpha", Imdb="tt001"),
        ]
        plan = build_pull_plan(TRAKT_MOVIES[:1], [], emby_movies, [], [])
        assert sorted(p.emby_id for p in plan.to_mark) == ["m1", "m1-4k"]

    def test_episodes_match_by_show_and_number(self):
        series = [{"Id": "s1", "Name": "Show", "ProviderIds": {"Tvdb": "500"}}]
        episodes = [
            _episode("e1", "s1", 1, 1),
            _episode("e2", "s1", 1, 2, played=True),
            _episode("e3", "s1", 1, 3),
            _episode("other", "s2", 1, 1),
        ]
        plan = build_pull_plan([], TRAKT_SHOWS, [], series, episodes)

        assert [p.emby_id for p in plan.to_mark] == ["e1", "e3"]
        assert plan.to_mark[0].watched_at == datetime(2024, 6, 1, 10, 0, 0)
        assert plan.to_mark[0].season_number == 1
        assert plan.already_played == 1
        reasons = sorted(u["reason"] for u in plan.unmatched)
        assert reasons == ["Episode not found in Emby library", "Show not found in Emby library"]

    def test_multi_episode_file_marked_once(self):
        series = [{"Id": "s1", "Name": "Show", "ProviderIds": {"Tvdb": "500"}}]
        episodes = [_episode("e12", "s1", 1, 1, end=2), _episode("e3", "s1", 1, 3)]
        plan = build_pull_plan([], TRAKT_SHOWS[:1], [], series, episodes)
        assert [p.emby_id for p in plan.to_mark] == ["e12", "e3"]
        # Keeps the latest watch date of the episodes in the file (E02).
        assert plan.to_mark[0].watched_at == datetime(2024, 6, 2, 10, 0, 0)

    def test_copies_with_different_provider_ids_all_marked(self):
        emby_movies = [
            _movie("m-imdb", "Alpha", Imdb="tt001"),
            _movie("m-tmdb", "Alpha", Tmdb="1"),
            _movie("m-both", "Alpha", Imdb="tt001", Tmdb="1"),
        ]
        plan = build_pull_plan(TRAKT_MOVIES[:1], [], emby_movies, [], [])
        assert sorted(p.emby_id for p in plan.to_mark) == ["m-both", "m-imdb", "m-tmdb"]

    def test_episodes_from_every_matching_series(self):
        series = [
            {"Id": "s1", "Name": "Show", "ProviderIds": {"Tvdb": "500"}},
            {"Id": "s2", "Name": "Show", "ProviderIds": {"Imdb": "tt500"}},
        ]
        episodes = [_episode("a1", "s1", 1, 1), _episode("b1", "s2", 1, 1)]
        plan = build_pull_plan([], TRAKT_SHOWS[:1], [], series, episodes)
        assert sorted(p.emby_id for p in plan.to_mark) == ["a1", "b1"]

    def test_parse_trakt_date(self):
        assert parse_trakt_date("2024-01-02T03:04:05.000Z") == datetime(2024, 1, 2, 3, 4, 5)
        assert parse_trakt_date(None) is None
        assert parse_trakt_date("junk") is None


class TestEmbyClientLibrary:
    @responses.activate
    def test_get_library_items_pages(self, monkeypatch):
        monkeypatch.setattr(EmbyClient, "LIBRARY_PAGE_SIZE", 2)
        responses.add(
            responses.GET, ITEMS_URL,
            json={"Items": [{"Id": "1"}, {"Id": "2"}], "TotalRecordCount": 3},
        )
        responses.add(
            responses.GET, ITEMS_URL,
            json={"Items": [{"Id": "3"}], "TotalRecordCount": 3},
        )
        client = EmbyClient(EMBY, access_token="t", user_id="user1")
        items = client.get_library_items("Movie")

        assert [i["Id"] for i in items] == ["1", "2", "3"]
        assert "StartIndex=2" in responses.calls[1].request.url
        assert "IncludeItemTypes=Movie" in responses.calls[0].request.url

    @responses.activate
    def test_mark_played_sends_date(self):
        responses.add(responses.POST, f"{EMBY}/Users/user1/PlayedItems/m1", json={})
        client = EmbyClient(EMBY, access_token="t", user_id="user1")
        client.mark_played("m1", datetime(2024, 5, 1, 20, 0, 0))
        assert "DatePlayed=20240501200000" in responses.calls[0].request.url


def _write_config(tmp_path):
    config = Config(data_dir=tmp_path)
    config.set_emby_credentials(
        server_url=EMBY, user_id="user1", access_token="token1", device_id="device1"
    )
    config.set_trakt_credentials(
        client_id="client1",
        client_secret="secret1",
        access_token="access1",
        refresh_token="refresh1",
        expires_at="2099-01-01T00:00:00",
    )
    config.save()


def _mock_sources():
    responses.add(
        responses.GET, "https://api.trakt.tv/sync/watched/movies", json=TRAKT_MOVIES
    )
    responses.add(responses.GET, "https://api.trakt.tv/sync/watched/shows", json=[])
    responses.add(
        responses.GET,
        ITEMS_URL,
        json={
            "Items": [
                _movie("m1", "Alpha", Imdb="tt001"),
                _movie("m2", "Beta", played=True, Imdb="tt002"),
            ],
            "TotalRecordCount": 2,
        },
    )


class TestPullCommand:
    @responses.activate
    def test_pull_dry_run_changes_nothing(self, tmp_path):
        _write_config(tmp_path)
        _mock_sources()

        result = CliRunner().invoke(
            cli,
            ["pull", "--content", "movies", "--dry-run"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0, result.output
        assert "Alpha" in result.output
        assert "Would mark: 1 movies" in result.output
        assert not any(c.request.method == "POST" for c in responses.calls)
        assert (tmp_path / "unmatched_trakt_to_emby.yaml").exists()

    @responses.activate
    def test_pull_marks_unplayed_only(self, tmp_path):
        _write_config(tmp_path)
        _mock_sources()
        responses.add(responses.POST, f"{EMBY}/Users/user1/PlayedItems/m1", json={})

        result = CliRunner().invoke(
            cli,
            ["pull", "--content", "movies"],
            env={"EMBY_SYNC_DATA_DIR": str(tmp_path)},
        )

        assert result.exit_code == 0, result.output
        posts = [c for c in responses.calls if c.request.method == "POST"]
        assert len(posts) == 1
        assert "/PlayedItems/m1" in posts[0].request.url
        assert "Movies marked played: 1" in result.output
        assert "Already played on Emby: 1" in result.output

    def test_pull_requires_trakt(self, tmp_path):
        config = Config(data_dir=tmp_path)
        config.set_emby_credentials(
            server_url=EMBY, user_id="user1", access_token="t", device_id="d"
        )
        config.save()
        result = CliRunner().invoke(
            cli, ["pull"], env={"EMBY_SYNC_DATA_DIR": str(tmp_path)}
        )
        assert result.exit_code == 1
        assert "trakt-setup" in result.output
