"""FastAPI web application with a modern control frontend."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import or_, select

from ..config import AutoDjConfig
from ..database.models import QueueEntry, Track
from ..database.session import Database
from ..services.queue import QueueManager

app = FastAPI(title="Auto-DJ")

_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
_STATIC_DIR = _PACKAGE_DIR / "static"

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def get_config() -> AutoDjConfig:
    return AutoDjConfig()


def get_database(config: AutoDjConfig = Depends(get_config)) -> Database:
    return Database(config.database)


def get_queue_manager(db: Database = Depends(get_database), config: AutoDjConfig = Depends(get_config)) -> QueueManager:
    return QueueManager(db, config.queue_policy)


class TrackOut(BaseModel):
    id: int
    artist: str
    title: str
    duration_ms: int
    bpm: float
    genre: str
    key_camelot: str
    energy_avg: float

    class Config:
        orm_mode = True


class QueueEntryOut(BaseModel):
    id: int
    track: TrackOut
    source: str
    created_at: datetime
    status: str

    class Config:
        orm_mode = True


class QueueStatusOut(BaseModel):
    entries: List[QueueEntryOut]
    remaining_slots: int


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    queue: QueueManager = Depends(get_queue_manager),
) -> HTMLResponse:
    status = queue.status()
    now_playing = queue.current_track()
    return _TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "queue_status": status,
            "now_playing": now_playing,
        },
    )


@app.get("/queue", response_model=QueueStatusOut)
async def list_queue(queue: QueueManager = Depends(get_queue_manager)) -> QueueStatusOut:
    status = queue.status()
    return QueueStatusOut(entries=status.entries, remaining_slots=status.remaining_slots)


class EnqueueRequest(BaseModel):
    track_id: int
    guest_session: str | None = None


@app.post("/queue", response_model=QueueEntryOut)
async def add_to_queue(payload: EnqueueRequest, queue: QueueManager = Depends(get_queue_manager)) -> QueueEntry:
    db = queue._db  # noqa: SLF001 - temporary until service layer is expanded
    with db.session() as session:
        track = session.get(Track, payload.track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        entry = queue.enqueue(track, "request", payload.guest_session)
        session.refresh(entry)
        return entry


@app.get("/now-playing", response_model=Optional[QueueEntryOut])
async def now_playing(queue: QueueManager = Depends(get_queue_manager)) -> Optional[QueueEntryOut]:
    entry = queue.current_track()
    return entry


class TrackSearchOut(BaseModel):
    id: int
    artist: str
    title: str
    duration_ms: int
    genre: str
    energy_avg: float

    class Config:
        orm_mode = True


@app.get("/tracks/search", response_model=List[TrackSearchOut])
async def search_tracks(
    query: str = Query(..., min_length=2, description="Artist or title search"),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_database),
) -> List[TrackSearchOut]:
    like_pattern = f"%{query}%"
    with db.session() as session:
        stmt = (
            select(Track)
            .where(or_(Track.title.ilike(like_pattern), Track.artist.ilike(like_pattern)))
            .order_by(Track.artist.asc(), Track.title.asc())
            .limit(limit)
        )
        results = session.execute(stmt).scalars().all()
        return list(results)
