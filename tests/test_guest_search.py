from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from auto_dj.config import AutoDjConfig, DatabaseConfig, PathsConfig
from auto_dj.database.models import Track
from auto_dj.database.session import Database
from auto_dj.services.playlists import PlaylistService
from auto_dj.services.queue import QueueManager
from auto_dj.web.app import (
    app,
    get_config,
    get_database,
    get_playlist_service,
    get_queue_manager,
)


def build_config(tmp_path: Path) -> AutoDjConfig:
    return AutoDjConfig(
        paths=PathsConfig(
            music_root=tmp_path / "music",
            covers_root=tmp_path / "covers",
            cache_root=tmp_path / "cache",
            config_root=tmp_path / "config",
            runtime_log_root=tmp_path / "runtime",
            persistent_log_root=tmp_path / "persistent",
        ),
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path/'auto_dj.db'}"),
    )


def seed_track(
    database: Database,
    *,
    artist: str,
    title: str,
    path: str | None = None,
    genre: str = "house",
    energy: float = 0.7,
) -> Track:
    track_path = path or f"/media/music/{artist.replace(' ', '_')}-{title.replace(' ', '_')}.flac"
    with database.session() as session:
        track = Track(
            path=track_path,
            artist=artist,
            title=title,
            duration_ms=180_000,
            lufs_i=-9.0,
            true_peak_db=-1.5,
            bpm=124.0,
            key_camelot="8A",
            genre=genre,
            energy_avg=energy,
            cover_path=None,
            flags={},
        )
        session.add(track)
        session.flush()
        session.refresh(track)
        return track


@pytest.fixture
def test_client(tmp_path):
    config = build_config(tmp_path)
    database = Database(config.database)
    database.create_all()

    playlist_service = PlaylistService(database)
    queue_manager = QueueManager(database, config.queue_policy, playlist_service)

    overrides = {
        get_config: lambda: config,
        get_database: lambda: database,
        get_playlist_service: lambda: playlist_service,
        get_queue_manager: lambda: queue_manager,
    }

    for dependency, provider in overrides.items():
        app.dependency_overrides[dependency] = provider

    try:
        with TestClient(app) as client:
            yield client, database
    finally:
        for dependency in list(overrides):
            app.dependency_overrides.pop(dependency, None)


def test_guest_search_returns_results(test_client):
    client, database = test_client
    seed_track(database, artist="Search Artist", title="Search Title")

    response = client.get("/tracks/search", params={"query": "Search"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["artist"] == "Search Artist"
    assert payload[0]["title"] == "Search Title"


def test_guest_search_supports_q_alias_and_url_encoding(test_client):
    client, database = test_client
    seed_track(database, artist="Massive", title="Attack")

    response = client.get("/tracks/search", params={"q": "massive"})
    assert response.status_code == 200
    assert response.json()

    encoded = "Massive Attack".replace(" ", "%20")
    response_encoded = client.get(f"/tracks/search?q={encoded}")
    assert response_encoded.status_code == 200
    payload = response_encoded.json()
    assert payload
    assert payload[0]["title"] == "Attack"


def test_guest_search_is_case_insensitive_and_accent_agnostic(test_client):
    client, database = test_client
    seed_track(database, artist="Tiësto", title="Adagio For Strings")

    response = client.get("/tracks/search", params={"query": "tiesto"})
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["artist"] == "Tiësto"

    partial_response = client.get("/tracks/search", params={"query": "adagio str"})
    assert partial_response.status_code == 200
    partial_payload = partial_response.json()
    assert partial_payload
    assert partial_payload[0]["title"] == "Adagio For Strings"


def test_guest_search_limits_to_five_results(test_client):
    client, database = test_client
    for index in range(6):
        seed_track(
            database,
            artist=f"Artist {index}",
            title=f"Track {index}",
            energy=0.5 + index * 0.05,
        )

    response = client.get("/tracks/search", params={"query": "Track"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 5


def test_admin_can_request_larger_search_batches(test_client):
    client, database = test_client
    for index in range(30):
        seed_track(
            database,
            artist=f"Artist {index}",
            title=f"Playlist Track {index}",
        )

    response = client.get("/tracks/search", params={"query": "Playlist", "limit": 25})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 25


def test_guest_search_handles_punctuation_tokens(test_client):
    client, database = test_client
    seed_track(database, artist="Imagine Dragons", title="Believer")

    response = client.get(
        "/tracks/search",
        params={"query": "Imagine Dragons - believer"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["title"] == "Believer"

    punctuation_response = client.get(
        "/tracks/search",
        params={"query": "Believer,"},
    )
    assert punctuation_response.status_code == 200
    punctuation_payload = punctuation_response.json()
    assert punctuation_payload
    assert punctuation_payload[0]["artist"] == "Imagine Dragons"
