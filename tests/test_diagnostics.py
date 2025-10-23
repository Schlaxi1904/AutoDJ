from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from auto_dj.config import AutoDjConfig, DatabaseConfig, PathsConfig
from auto_dj.database.models import Track
from auto_dj.database.session import Database
from auto_dj.tools.diagnostics import run_diagnostics


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
        database=DatabaseConfig(dsn=f"sqlite+pysqlite:///{tmp_path/'diag.db'}"),
    )


def seed_tracks(database: Database, count: int = 3) -> None:
    with database.session() as session:
        for index in range(count):
            track = Track(
                path=f"/media/music/diag_{index}.flac",
                artist=f"Diagnostic Artist {index}",
                title=f"Diagnostic Title {index}",
                duration_ms=180_000 + index * 5000,
                lufs_i=-8.0,
                true_peak_db=-1.0,
                bpm=120.0 + index,
                key_camelot="8A",
                genre="house",
                energy_avg=0.6 + index * 0.1,
                cover_path=None,
                flags={},
            )
            session.add(track)


def test_run_diagnostics_succeeds(tmp_path):
    config = build_config(tmp_path)
    database = Database(config.database)
    database.create_all()
    seed_tracks(database, count=3)

    exit_code, results = run_diagnostics(config)

    assert exit_code == 0
    assert all(result.success for result in results)
    assert {result.name for result in results} == {"music_library", "queue_flow", "dj_brain"}
