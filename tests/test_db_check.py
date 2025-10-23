from pathlib import Path

import pytest
pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, inspect

from auto_dj.config import AutoDjConfig, DatabaseConfig, PathsConfig
from auto_dj.db_check import ensure_database_ready
from auto_dj.database.models import Base


@pytest.mark.parametrize("schema", [None])
def test_ensure_database_ready_creates_tables(tmp_path: Path, schema):
    db_path = tmp_path / "auto_dj.db"
    config = AutoDjConfig(
        paths=PathsConfig(
            music_root=tmp_path / "music",
            covers_root=tmp_path / "covers",
            cache_root=tmp_path / "cache",
            config_root=tmp_path / "config",
            runtime_log_root=tmp_path / "runtime",
            persistent_log_root=tmp_path / "persistent",
        ),
        database=DatabaseConfig(
            dsn=f"sqlite+pysqlite:///{db_path}",
            schema=schema,
        ),
    )

    ensure_database_ready(config)

    engine = create_engine(config.database.dsn, future=True)
    inspector = inspect(engine)
    missing = [table for table in Base.metadata.tables if not inspector.has_table(table)]
    assert not missing
