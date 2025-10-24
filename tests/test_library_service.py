from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import select

from auto_dj.config import AutoDjConfig, DatabaseConfig, PathsConfig
from auto_dj.database.models import Track
from auto_dj.database.session import Database
from auto_dj.services.library import LibraryService
from auto_dj.services.settings import SettingsService


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


def create_service(tmp_path: Path) -> tuple[LibraryService, Database, AutoDjConfig]:
    config = build_config(tmp_path)
    database = Database(config.database)
    database.create_all()
    settings = SettingsService(database)
    library = LibraryService(database, config, settings)
    config.paths.music_root.mkdir(parents=True, exist_ok=True)
    return library, database, config


def test_library_scan_inserts_tracks(tmp_path: Path) -> None:
    library, database, config = create_service(tmp_path)
    track_path = config.paths.music_root / "Artist One - Track One.mp3"
    track_path.write_bytes(b"not real audio")

    report = library.scan(track_path.parent)

    assert report.inserted == 1
    assert report.total_files == 1

    with database.session() as session:
        track = session.execute(select(Track)).scalars().one()
        assert track.artist == "Artist One"
        assert track.title == "Track One"


def test_library_state_auto_indexes_when_empty(tmp_path: Path) -> None:
    library, _, config = create_service(tmp_path)
    track_path = config.paths.music_root / "Fallback Tune.mp3"
    track_path.write_bytes(b"content")

    state = library.state(auto_index=True)

    assert state.track_count == 1
    assert state.filesystem_count == 1
