import pytest

pytest.importorskip("sqlalchemy")

from auto_dj.config import AutoDjConfig, QueuePolicy, DatabaseConfig
from auto_dj.database.models import Track
from auto_dj.database.session import Database
from auto_dj.services.dj_brain import DjBrain
from auto_dj.services.queue import QueueManager


def build_database() -> Database:
    db = Database(DatabaseConfig(dsn="sqlite+pysqlite:///:memory:"))
    db.create_all()
    return db


def seed_tracks(db: Database, count: int = 3) -> list[Track]:
    tracks: list[Track] = []
    with db.session() as session:
        for index in range(count):
            track = Track(
                path=f"/media/music/seed_{index}.flac",
                artist=f"Artist {index}",
                title=f"Title {index}",
                duration_ms=180_000,
                lufs_i=-9.5,
                true_peak_db=-1.5,
                bpm=128 + index,
                key_camelot="8A",
                genre="house",
                energy_avg=0.6 + index * 0.05,
                cover_path=None,
                flags={},
            )
            session.add(track)
            session.flush()
            tracks.append(track)
    return tracks


def test_brain_plan_next_enqueues_and_rotates_tracks():
    db = build_database()
    tracks = seed_tracks(db, 3)

    config = AutoDjConfig()
    queue_policy = QueuePolicy(max_length=5)
    queue = QueueManager(db, queue_policy)
    brain = DjBrain(config)

    assert brain.plan_next(db, queue) is True
    status = queue.status()
    assert any(entry.status == "pending" for entry in status.entries)
    first_entry = status.entries[0]
    first_track_id = first_entry.track_id

    # Queue already has a pending entry, so no additional track should be added.
    assert brain.plan_next(db, queue) is False

    # Remove the pending entry to simulate playback having consumed it.
    queue.remove(first_entry.id)
    status_after_removal = queue.status()
    assert not status_after_removal.entries

    assert brain.plan_next(db, queue) is True
    second_status = queue.status()
    assert len(second_status.entries) == 1
    second_entry = second_status.entries[0]
    assert second_entry.track_id != first_track_id
    assert second_entry.track_id in {track.id for track in tracks}
