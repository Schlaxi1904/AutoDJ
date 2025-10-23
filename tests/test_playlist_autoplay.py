import pytest

pytest.importorskip("sqlalchemy")

from auto_dj.config import DatabaseConfig, QueuePolicy
from auto_dj.database.models import Track
from auto_dj.database.session import Database
from auto_dj.services.playlists import PlaylistService
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
                path=f"/media/music/track_{index}.flac",
                artist=f"Artist {index}",
                title=f"Title {index}",
                duration_ms=180_000 + index * 1000,
                lufs_i=-9.5,
                true_peak_db=-1.5,
                bpm=128 + index,
                key_camelot="8A",
                genre="house",
                energy_avg=0.65 + index * 0.05,
                cover_path=None,
                flags={},
            )
            session.add(track)
            session.flush()
            tracks.append(track)
    return tracks


def test_autoplay_rotation_and_pointer_reset():
    db = build_database()
    tracks = seed_tracks(db, 2)
    service = PlaylistService(db)

    detail = service.create_playlist("Fallback")
    playlist_id = detail.id
    service.add_track(playlist_id, tracks[0].id)
    service.add_track(playlist_id, tracks[1].id)
    service.set_fallback_playlist(playlist_id)

    assert service.get_fallback_playlist_id() == playlist_id

    # The playlist cycles through tracks in order and wraps around.
    assert service.next_autoplay_track() == tracks[0].id
    assert service.next_autoplay_track() == tracks[1].id
    assert service.next_autoplay_track() == tracks[0].id

    # Removing a track resets the pointer so playback restarts cleanly.
    service.remove_track(playlist_id, tracks[1].id)
    assert service.next_autoplay_track() == tracks[0].id

    # Clearing the fallback disables autoplay selection.
    service.set_fallback_playlist(None)
    assert service.get_fallback_playlist_id() is None
    assert service.next_autoplay_track() is None


def test_queue_manager_uses_autoplay_when_queue_empty():
    db = build_database()
    tracks = seed_tracks(db, 2)
    service = PlaylistService(db)
    playlist = service.create_playlist("Rotation")
    service.add_track(playlist.id, tracks[0].id)
    service.add_track(playlist.id, tracks[1].id)
    service.set_fallback_playlist(playlist.id)

    queue = QueueManager(db, QueuePolicy(max_length=5), playlist_service=service)

    first_entry = queue.next_track()
    assert first_entry is not None
    assert first_entry.track.id == tracks[0].id
    assert first_entry.source == "autoplay"

    second_entry = queue.next_track()
    assert second_entry is not None
    assert second_entry.track.id == tracks[1].id
    assert second_entry.source == "autoplay"
