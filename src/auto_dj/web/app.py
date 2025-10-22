"""FastAPI web application with a modern control frontend."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select

from ..config import AutoDjConfig, load_config
from ..database.models import AdminUser, QueueEntry, Track
from ..database.session import Database
from ..services.admin import AdminService
from ..services.queue import QueueManager
from .security import SessionManager

app = FastAPI(title="Auto-DJ")

_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
_STATIC_DIR = _PACKAGE_DIR / "static"
_CONFIG = load_config()

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def get_config() -> AutoDjConfig:
    return _CONFIG


def get_database(config: AutoDjConfig = Depends(get_config)) -> Database:
    return Database(config.database)


def get_queue_manager(db: Database = Depends(get_database), config: AutoDjConfig = Depends(get_config)) -> QueueManager:
    return QueueManager(db, config.queue_policy)


def get_admin_service(
    db: Database = Depends(get_database), config: AutoDjConfig = Depends(get_config)
) -> AdminService:
    return AdminService(db, config)


def get_session_manager(config: AutoDjConfig = Depends(get_config)) -> SessionManager:
    return SessionManager(config)


def require_admin(
    request: Request,
    admin_service: AdminService = Depends(get_admin_service),
    session_manager: SessionManager = Depends(get_session_manager),
) -> AdminUser:
    token = request.cookies.get(session_manager.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    admin_id = session_manager.verify(token)
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")
    admin = admin_service.get_account(admin_id)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account missing")
    return admin


def optional_admin(
    request: Request,
    admin_service: AdminService = Depends(get_admin_service),
    session_manager: SessionManager = Depends(get_session_manager),
) -> Optional[AdminUser]:
    token = request.cookies.get(session_manager.cookie_name)
    if not token:
        return None
    admin_id = session_manager.verify(token)
    if not admin_id:
        return None
    return admin_service.get_account(admin_id)


class TrackOut(BaseModel):
    id: int
    artist: str
    title: str
    duration_ms: int
    bpm: float
    genre: str
    key_camelot: str
    energy_avg: float

    model_config = ConfigDict(from_attributes=True)


class QueueEntryOut(BaseModel):
    id: int
    track: TrackOut
    source: str
    created_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class QueueStatusOut(BaseModel):
    entries: List[QueueEntryOut]
    remaining_slots: int


class AdminAccountOut(BaseModel):
    id: int
    username: str
    created_at: datetime
    last_login_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    new_password: str


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


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin: Optional[AdminUser] = Depends(optional_admin),
) -> HTMLResponse:
    return _TEMPLATES.TemplateResponse("admin.html", {"request": request, "admin": admin})


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

    model_config = ConfigDict(from_attributes=True)


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


@app.post("/admin/login")
async def admin_login(
    payload: AdminLoginRequest,
    admin_service: AdminService = Depends(get_admin_service),
    session_manager: SessionManager = Depends(get_session_manager),
    config: AutoDjConfig = Depends(get_config),
) -> JSONResponse:
    user = admin_service.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Zugangsdaten")
    response = JSONResponse({"message": "ok"})
    response.set_cookie(
        session_manager.cookie_name,
        session_manager.create(user.id),
        httponly=True,
        secure=config.web_security.ssl_enabled,
        samesite="lax",
        max_age=session_manager.max_age,
    )
    return response


@app.post("/admin/logout")
async def admin_logout(
    config: AutoDjConfig = Depends(get_config),
    session_manager: SessionManager = Depends(get_session_manager),
) -> JSONResponse:
    response = JSONResponse({"message": "logged_out"})
    response.delete_cookie(
        session_manager.cookie_name,
        httponly=True,
        secure=config.web_security.ssl_enabled,
        samesite="lax",
    )
    return response


@app.get("/admin/accounts", response_model=List[AdminAccountOut])
async def admin_accounts(
    admin_service: AdminService = Depends(get_admin_service),
    _: AdminUser = Depends(require_admin),
) -> List[AdminAccountOut]:
    accounts = admin_service.list_accounts()
    return list(accounts)


@app.post("/admin/accounts/{account_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def admin_change_password(
    account_id: int,
    payload: PasswordChangeRequest,
    admin_service: AdminService = Depends(get_admin_service),
    _: AdminUser = Depends(require_admin),
) -> Response:
    try:
        admin_service.change_password(account_id, payload.new_password)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
