"""Playlist management and autoplay helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database.models import Playlist, PlaylistTrack, Setting, Track
from ..database.session import Database

_AUTOPLAY_STATE_KEY = "playlists.autoplay_state"


@dataclass
class PlaylistSummary:
    id: int
    name: str
    description: Optional[str]
    track_count: int
    is_fallback: bool


@dataclass
class PlaylistDetail(PlaylistSummary):
    tracks: List[Track]


class PlaylistService:
    """Manage playlists and provide autoplay candidates."""

    def __init__(self, database: Database) -> None:
        self._db = database

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_playlists(self) -> List[PlaylistSummary]:
        with self._db.session() as session:
            fallback_id = self._load_state(session).get("fallback_playlist_id")
            stmt = (
                select(Playlist, func.count(PlaylistTrack.track_id))
                .outerjoin(PlaylistTrack)
                .group_by(Playlist.id)
                .order_by(Playlist.created_at.asc())
            )
            results = session.execute(stmt).all()
            summaries: List[PlaylistSummary] = []
            for playlist, track_count in results:
                summaries.append(
                    PlaylistSummary(
                        id=playlist.id,
                        name=playlist.name,
                        description=playlist.description,
                        track_count=int(track_count or 0),
                        is_fallback=bool(fallback_id and playlist.id == fallback_id),
                    )
                )
            return summaries

    def create_playlist(self, name: str, description: Optional[str] = None) -> PlaylistDetail:
        normalized_name = self._normalize_name(name)
        normalized_description = description.strip() if description else None
        with self._db.session() as session:
            if not normalized_name:
                raise ValueError("Der Playlistname darf nicht leer sein")
            if self._name_exists(session, normalized_name):
                raise ValueError("Es existiert bereits eine Playlist mit diesem Namen")
            playlist = Playlist(name=normalized_name, description=normalized_description)
            session.add(playlist)
            session.flush()
            return self._detail_from_playlist(session, playlist, track_count=0)

    def update_playlist(
        self,
        playlist_id: int,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> PlaylistDetail:
        with self._db.session() as session:
            playlist = session.get(Playlist, playlist_id)
            if not playlist:
                raise ValueError("Playlist nicht gefunden")

            if name is not None:
                normalized_name = self._normalize_name(name)
                if not normalized_name:
                    raise ValueError("Der Playlistname darf nicht leer sein")
                if normalized_name != playlist.name and self._name_exists(
                    session, normalized_name
                ):
                    raise ValueError("Es existiert bereits eine Playlist mit diesem Namen")
                playlist.name = normalized_name

            if description is not None:
                playlist.description = description.strip() or None

            playlist.updated_at = datetime.utcnow()
            session.add(playlist)
            session.flush()
            return self._detail_from_playlist(session, playlist)

    def delete_playlist(self, playlist_id: int) -> None:
        with self._db.session() as session:
            playlist = session.get(Playlist, playlist_id)
            if not playlist:
                raise ValueError("Playlist nicht gefunden")

            state = self._load_state(session)
            fallback_id = state.get("fallback_playlist_id")
            if fallback_id == playlist_id:
                state.pop("fallback_playlist_id", None)
                positions = state.get("positions", {})
                positions.pop(str(playlist_id), None)
                self._save_state(session, state)

            session.delete(playlist)

    def get_playlist(self, playlist_id: int) -> PlaylistDetail:
        with self._db.session() as session:
            playlist = session.get(Playlist, playlist_id)
            if not playlist:
                raise ValueError("Playlist nicht gefunden")
            return self._detail_from_playlist(session, playlist)

    def add_track(self, playlist_id: int, track_id: int) -> PlaylistDetail:
        with self._db.session() as session:
            playlist = session.get(Playlist, playlist_id)
            if not playlist:
                raise ValueError("Playlist nicht gefunden")

            track = session.get(Track, track_id)
            if not track:
                raise ValueError("Track nicht gefunden")

            existing = session.get(PlaylistTrack, {"playlist_id": playlist_id, "track_id": track_id})
            if existing:
                return self._detail_from_playlist(session, playlist)

            position = session.execute(
                select(func.max(PlaylistTrack.position)).where(
                    PlaylistTrack.playlist_id == playlist_id
                )
            ).scalar()
            next_position = int(position + 1) if position is not None else 0
            session.add(
                PlaylistTrack(
                    playlist_id=playlist_id,
                    track_id=track_id,
                    position=next_position,
                )
            )

            playlist.updated_at = datetime.utcnow()
            session.add(playlist)

            state = self._load_state(session)
            if state.get("fallback_playlist_id") == playlist_id:
                self._ensure_pointer_bounds(session, state, playlist_id)
                self._save_state(session, state)

            session.flush()
            return self._detail_from_playlist(session, playlist)

    def remove_track(self, playlist_id: int, track_id: int) -> PlaylistDetail:
        with self._db.session() as session:
            playlist = session.get(Playlist, playlist_id)
            if not playlist:
                raise ValueError("Playlist nicht gefunden")

            entry = session.get(PlaylistTrack, {"playlist_id": playlist_id, "track_id": track_id})
            if not entry:
                raise ValueError("Track nicht in Playlist vorhanden")

            session.delete(entry)
            session.flush()

            remaining = session.execute(
                select(PlaylistTrack)
                .where(PlaylistTrack.playlist_id == playlist_id)
                .order_by(PlaylistTrack.position.asc())
            ).scalars().all()
            for index, track_entry in enumerate(remaining):
                if track_entry.position != index:
                    track_entry.position = index
                    session.add(track_entry)

            playlist.updated_at = datetime.utcnow()
            session.add(playlist)

            state = self._load_state(session)
            if state.get("fallback_playlist_id") == playlist_id:
                self._ensure_pointer_bounds(session, state, playlist_id)
                self._save_state(session, state)

            session.flush()
            return self._detail_from_playlist(session, playlist)

    def set_fallback_playlist(self, playlist_id: Optional[int]) -> Optional[int]:
        with self._db.session() as session:
            state = self._load_state(session)
            positions = state.setdefault("positions", {})

            if playlist_id is None:
                state.pop("fallback_playlist_id", None)
            else:
                playlist = session.get(Playlist, playlist_id)
                if not playlist:
                    raise ValueError("Playlist nicht gefunden")
                state["fallback_playlist_id"] = playlist_id
                self._ensure_pointer_bounds(session, state, playlist_id)

            # Remove dangling pointers
            for key in list(positions.keys()):
                if not session.get(Playlist, int(key)):
                    positions.pop(key, None)

            self._save_state(session, state)
            return state.get("fallback_playlist_id")

    def get_fallback_playlist_id(self) -> Optional[int]:
        with self._db.session() as session:
            return self._load_state(session).get("fallback_playlist_id")

    def next_autoplay_track(self) -> Optional[int]:
        with self._db.session() as session:
            state = self._load_state(session)
            fallback_id = state.get("fallback_playlist_id")
            if not fallback_id:
                return None

            playlist_exists = session.get(Playlist, fallback_id)
            if not playlist_exists:
                state.pop("fallback_playlist_id", None)
                state.get("positions", {}).pop(str(fallback_id), None)
                self._save_state(session, state)
                return None

            tracks = session.execute(
                select(PlaylistTrack.track_id)
                .where(PlaylistTrack.playlist_id == fallback_id)
                .order_by(PlaylistTrack.position.asc())
            ).scalars().all()
            if not tracks:
                return None

            positions = state.setdefault("positions", {})
            pointer = int(positions.get(str(fallback_id), 0))
            pointer %= len(tracks)
            track_id = int(tracks[pointer])
            positions[str(fallback_id)] = (pointer + 1) % len(tracks)
            self._save_state(session, state)
            return track_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _detail_from_playlist(
        self, session: Session, playlist: Playlist, *, track_count: Optional[int] = None
    ) -> PlaylistDetail:
        tracks = session.execute(
            select(Track)
            .join(PlaylistTrack, PlaylistTrack.track_id == Track.id)
            .where(PlaylistTrack.playlist_id == playlist.id)
            .order_by(PlaylistTrack.position.asc())
        ).scalars().all()

        if track_count is None:
            track_count = len(tracks)

        fallback_id = self._load_state(session).get("fallback_playlist_id")
        return PlaylistDetail(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            track_count=int(track_count),
            is_fallback=bool(fallback_id and playlist.id == fallback_id),
            tracks=list(tracks),
        )

    def _name_exists(self, session: Session, name: str) -> bool:
        stmt = select(Playlist.id).where(func.lower(Playlist.name) == name.lower())
        return session.execute(stmt).scalar_one_or_none() is not None

    def _normalize_name(self, name: str) -> str:
        return name.strip()

    def _load_state(self, session: Session) -> dict:
        record = session.get(Setting, _AUTOPLAY_STATE_KEY)
        if not record or not isinstance(record.value_json, dict):
            return {}
        return dict(record.value_json)

    def _save_state(self, session: Session, state: dict) -> None:
        record = session.get(Setting, _AUTOPLAY_STATE_KEY)
        if record is None:
            session.add(Setting(key=_AUTOPLAY_STATE_KEY, value_json=state))
        else:
            record.value_json = state
            session.add(record)

    def _ensure_pointer_bounds(self, session: Session, state: dict, playlist_id: int) -> None:
        positions = state.setdefault("positions", {})
        total = session.execute(
            select(func.count(PlaylistTrack.track_id)).where(
                PlaylistTrack.playlist_id == playlist_id
            )
        ).scalar()
        count = int(total or 0)
        if count <= 0:
            positions.pop(str(playlist_id), None)
            return
        pointer = int(positions.get(str(playlist_id), 0))
        if pointer >= count or pointer < 0:
            positions[str(playlist_id)] = 0


__all__ = [
    "PlaylistService",
    "PlaylistSummary",
    "PlaylistDetail",
]

