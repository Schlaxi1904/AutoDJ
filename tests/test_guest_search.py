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


def seed_track(database: Database) -> Track:
    with database.session() as session:
        track = Track(
            path="/media/music/sample.flac",
            artist="Search Artist",
            title="Search Title",
            duration_ms=180_000,
            lufs_i=-9.0,
            true_peak_db=-1.5,
            bpm=124.0,
            key_camelot="8A",
            genre="house",
            energy_avg=0.7,
            cover_path=None,
            flags={},
        )
        session.add(track)
        session.flush()
        session.refresh(track)
        return track


def test_guest_search_returns_results(tmp_path):
    config = build_config(tmp_path)
    database = Database(config.database)
    database.create_all()
    seed_track(database)

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
            response = client.get("/tracks/search", params={"query": "Search"})
            assert response.status_code == 200
            payload = response.json()
            assert len(payload) == 1
            assert payload[0]["artist"] == "Search Artist"
            assert payload[0]["title"] == "Search Title"
    finally:
        for dependency in list(overrides):
            app.dependency_overrides.pop(dependency, None)
