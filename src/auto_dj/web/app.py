"""FastAPI web application with a modern control frontend."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select

from ..config import AutoDjConfig, load_config
from ..database.models import AdminUser, QueueEntry, Track
from ..database.session import Database
from ..services.admin import AdminService
from ..services.audio_devices import AudioDeviceScanner
from ..services.queue import QueueManager
from ..services.osc import OscService
from ..services.settings import SettingsService
from ..services.system import SystemMonitor
from .security import SessionManager

app = FastAPI(title="Auto-DJ")

_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
_STATIC_DIR = _PACKAGE_DIR / "static"
_CONFIG = load_config()

_SYSTEM_TOGGLE_KEY = "system.toggles"
_AUDIO_OUTPUT_KEY = "audio.output_device"
_AUDIO_MIXER_KEY = "audio.mixer"
_LIBRARY_SETTINGS_KEY = "library.settings"
_LIGHT_SETTINGS_KEY = "light.settings"
_ANALYSIS_SETTINGS_KEY = "analysis.settings"

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


def get_settings_service(db: Database = Depends(get_database)) -> SettingsService:
    return SettingsService(db)


def get_system_monitor(
    config: AutoDjConfig = Depends(get_config),
    settings: SettingsService = Depends(get_settings_service),
) -> SystemMonitor:
    return SystemMonitor(config, settings)


def get_audio_device_scanner() -> AudioDeviceScanner:
    return AudioDeviceScanner()


def get_osc_service(config: AutoDjConfig = Depends(get_config)) -> OscService:
    return OscService(config.osc)


def _merge_system_toggles(settings: SettingsService, config: AutoDjConfig) -> SystemToggleState:
    default = {
        "fog_enabled": False,
        "superscenes_enabled": False,
        "public_enabled": config.web_security.public_enabled,
    }
    stored = settings.get_dict(_SYSTEM_TOGGLE_KEY, default)
    merged: Dict[str, bool] = {**default, **stored}
    return SystemToggleState(
        fog_enabled=bool(merged.get("fog_enabled", False)),
        superscenes_enabled=bool(merged.get("superscenes_enabled", False)),
        public_enabled=bool(merged.get("public_enabled", default["public_enabled"])),
    )


def _load_mixer_settings(settings: SettingsService) -> MixerSettingsOut:
    defaults = {
        "crossfade_seconds": 8.0,
        "volume_curve": "s-curve",
        "bass_crossover_hz": 120,
        "bass_curve": "lr24",
        "filter_hp_to_lp": True,
        "filter_lp_to_hp": True,
        "time_stretch_mode": "auto",
    }
    stored = settings.get_dict(_AUDIO_MIXER_KEY, defaults)
    merged = {**defaults, **stored}
    return MixerSettingsOut(**merged)


def _load_light_settings(
    settings: SettingsService, config: AutoDjConfig, toggles: SystemToggleState
) -> LightSettingsOut:
    defaults = {
        "target_host": config.osc.target_host,
        "target_port": config.osc.target_port,
    }
    stored = settings.get_dict(_LIGHT_SETTINGS_KEY, defaults)
    merged = {**defaults, **stored}
    return LightSettingsOut(
        target_host=str(merged.get("target_host", defaults["target_host"])),
        target_port=int(merged.get("target_port", defaults["target_port"])),
        superscenes_enabled=toggles.superscenes_enabled,
        fog_enabled=toggles.fog_enabled,
    )


def _load_analysis_settings(settings: SettingsService, config: AutoDjConfig) -> AnalysisSettingsOut:
    defaults = {
        "key_weight": config.brain_weights.key,
        "bpm_weight": config.brain_weights.bpm,
        "energy_weight": config.brain_weights.energy,
        "genre_weight": config.brain_weights.genre,
        "recency_weight": config.brain_weights.recency,
        "request_weight": config.brain_weights.request,
        "soft_spacing": config.queue_policy.preferred_spacing,
    }
    stored = settings.get_dict(_ANALYSIS_SETTINGS_KEY, defaults)
    merged = {**defaults, **stored}
    return AnalysisSettingsOut(**merged)


def _network_mode_label(config: AutoDjConfig, toggles: SystemToggleState) -> str:
    if config.web_security.ssl_enabled:
        return "Öffentlich (SSL)"
    if toggles.public_enabled:
        return "Öffentlich (HTTP)"
    return "Lokal (HTTP)"


def _library_state(
    db: Database, settings: SettingsService, config: AutoDjConfig
) -> LibraryStateOut:
    defaults = {
        "music_path": str(config.paths.music_root),
        "database_dsn": config.database.dsn,
    }
    stored = settings.get_dict(_LIBRARY_SETTINGS_KEY, defaults)
    merged = {**defaults, **stored}
    with db.session() as session:
        track_count = session.execute(select(func.count(Track.id))).scalar_one()
    quarantine = config.paths.music_root / "_quarantine"
    return LibraryStateOut(
        music_path=str(merged.get("music_path", defaults["music_path"])),
        database_dsn=str(merged.get("database_dsn", defaults["database_dsn"])),
        track_count=int(track_count or 0),
        quarantine_path=str(quarantine),
    )


def _discover_music_locations(
    settings: SettingsService, config: AutoDjConfig
) -> List[MusicLocationOut]:
    defaults = {
        "music_path": str(config.paths.music_root),
        "database_dsn": config.database.dsn,
    }
    stored = settings.get_dict(_LIBRARY_SETTINGS_KEY, defaults)
    current_path = str(stored.get("music_path", defaults["music_path"]))

    seen: set[str] = set()
    locations: List[MusicLocationOut] = []

    def register(path: Path, label: str, kind: str, include_if_missing: bool = False) -> None:
        try:
            resolved = path.expanduser()
        except Exception:
            return
        if not include_if_missing and not resolved.exists():
            return
        normalized = str(resolved)
        if normalized in seen:
            return
        seen.add(normalized)
        locations.append(
            MusicLocationOut(
                path=normalized,
                label=label,
                kind=kind,
                available=resolved.exists(),
            )
        )

    register(config.paths.music_root, "Standard (System)", "default", include_if_missing=True)
    if current_path:
        register(Path(current_path), "Aktuelle Auswahl", "current", include_if_missing=True)

    home = Path.home()
    for folder_name in ("Music", "Musik"):
        register(home / folder_name, f"Interner Speicher – {folder_name}", "internal")
        register(
            home / "AutoDJ" / folder_name,
            f"Interner Speicher – AutoDJ/{folder_name}",
            "internal",
        )

    external_roots = [Path("/media"), Path("/mnt"), Path("/run/media"), Path("/Volumes")]
    for root in external_roots:
        if not root.exists():
            continue
        for candidate in sorted(root.iterdir()):
            if not candidate.is_dir():
                continue
            register(
                candidate,
                f"Externer Datenträger – {candidate.name}",
                "external",
            )
            for child in (candidate / "Music", candidate / "Musik"):
                register(
                    child,
                    f"Externer Datenträger – {candidate.name}/{child.name}",
                    "external",
                )

    cloud_roots = [
        ("Nextcloud", home / "Nextcloud"),
        ("Nextcloud", home / "NextcloudDrive"),
        ("Dropbox", home / "Dropbox"),
        ("OneDrive", home / "OneDrive"),
        ("Google Drive", home / "Google Drive"),
        ("Google Drive", home / "GoogleDrive"),
    ]
    for provider, root in cloud_roots:
        if not root.exists():
            continue
        register(root, f"Cloud ({provider})", "cloud")
        for child in (root / "Music", root / "Musik"):
            if child.exists():
                register(child, f"Cloud ({provider}) – {child.name}", "cloud")

    return locations


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


class QueueStatusOut(BaseModel):
    entries: List[QueueEntryOut]
    remaining_slots: int


class AdminDashboardStateOut(BaseModel):
    now_playing: Optional[QueueEntryOut]
    queue: List[QueueEntryOut]
    remaining_slots: int


class SystemToggleState(BaseModel):
    fog_enabled: bool = False
    superscenes_enabled: bool = False
    public_enabled: bool = False


class SystemOverviewOut(BaseModel):
    now_playing: Optional[QueueEntryOut]
    next_entry: Optional[QueueEntryOut]
    queue_length: int
    remaining_slots: int
    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    temperature_c: Optional[float]
    xrun_count: int
    osc_connected: bool
    network_mode: str
    toggles: SystemToggleState


class SystemToggleUpdate(BaseModel):
    fog_enabled: Optional[bool] = None
    superscenes_enabled: Optional[bool] = None
    public_enabled: Optional[bool] = None


class AudioDeviceOut(BaseModel):
    identifier: str
    label: str
    kind: str


class AudioOutputStateOut(BaseModel):
    active_device_id: Optional[str]
    devices: List[AudioDeviceOut]


class AudioOutputUpdate(BaseModel):
    device_id: str


class MixerSettingsOut(BaseModel):
    crossfade_seconds: float = Field(ge=0)
    volume_curve: str
    bass_crossover_hz: int
    bass_curve: str
    filter_hp_to_lp: bool
    filter_lp_to_hp: bool
    time_stretch_mode: str


class MixerSettingsUpdate(BaseModel):
    crossfade_seconds: Optional[float] = Field(default=None, ge=0)
    volume_curve: Optional[str] = None
    bass_crossover_hz: Optional[int] = None
    bass_curve: Optional[str] = None
    filter_hp_to_lp: Optional[bool] = None
    filter_lp_to_hp: Optional[bool] = None
    time_stretch_mode: Optional[str] = None


class LibraryStateOut(BaseModel):
    music_path: str
    database_dsn: str
    track_count: int
    quarantine_path: str


class LibraryUpdateRequest(BaseModel):
    music_path: Optional[str] = None
    database_dsn: Optional[str] = None


class MusicLocationOut(BaseModel):
    path: str
    label: str
    kind: str
    available: bool


class LightSettingsOut(BaseModel):
    target_host: str
    target_port: int
    superscenes_enabled: bool
    fog_enabled: bool


class LightSettingsUpdate(BaseModel):
    target_host: Optional[str] = None
    target_port: Optional[int] = Field(default=None, ge=1, le=65535)
    superscenes_enabled: Optional[bool] = None
    fog_enabled: Optional[bool] = None


class AnalysisSettingsOut(BaseModel):
    key_weight: float
    bpm_weight: float
    energy_weight: float
    genre_weight: float
    recency_weight: float
    request_weight: float
    soft_spacing: int


class AnalysisSettingsUpdate(BaseModel):
    key_weight: Optional[float] = None
    bpm_weight: Optional[float] = None
    energy_weight: Optional[float] = None
    genre_weight: Optional[float] = None
    recency_weight: Optional[float] = None
    request_weight: Optional[float] = None
    soft_spacing: Optional[int] = Field(default=None, ge=0)


class DiagnosticsOut(BaseModel):
    runtime_log_path: str
    persistent_log_path: str
    cache_path: str
    config_path: str
    last_error: Optional[str]


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


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(
    request: Request,
    admin: Optional[AdminUser] = Depends(optional_admin),
) -> Response:
    if admin:
        return RedirectResponse(
            url=request.url_for("admin_dashboard"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _TEMPLATES.TemplateResponse("admin_login.html", {"request": request})


@app.get("/queue", response_model=QueueStatusOut)
async def list_queue(queue: QueueManager = Depends(get_queue_manager)) -> QueueStatusOut:
    status = queue.status()
    return QueueStatusOut(entries=status.entries, remaining_slots=status.remaining_slots)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    admin: AdminUser = Depends(require_admin),
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


@app.get("/admin/state", response_model=AdminDashboardStateOut)
async def admin_state(
    queue: QueueManager = Depends(get_queue_manager),
    _: AdminUser = Depends(require_admin),
) -> AdminDashboardStateOut:
    status_snapshot = queue.status()
    now_playing = queue.current_track()
    return AdminDashboardStateOut(
        now_playing=now_playing,
        queue=status_snapshot.entries,
        remaining_slots=status_snapshot.remaining_slots,
    )


@app.get("/admin/system/overview", response_model=SystemOverviewOut)
async def admin_system_overview(
    queue: QueueManager = Depends(get_queue_manager),
    monitor: SystemMonitor = Depends(get_system_monitor),
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> SystemOverviewOut:
    toggles = _merge_system_toggles(settings, config)
    status_snapshot = queue.status()
    now_playing = queue.current_track()
    next_entry = next(
        (entry for entry in status_snapshot.entries if entry.status == "pending"),
        None,
    )
    queue_length = len(status_snapshot.entries)
    host_snapshot = monitor.snapshot()

    return SystemOverviewOut(
        now_playing=now_playing,
        next_entry=next_entry,
        queue_length=queue_length,
        remaining_slots=status_snapshot.remaining_slots,
        cpu_percent=host_snapshot.cpu_percent,
        memory_percent=host_snapshot.memory_percent,
        temperature_c=host_snapshot.temperature_c,
        xrun_count=host_snapshot.xrun_count,
        osc_connected=host_snapshot.osc_connected,
        network_mode=_network_mode_label(config, toggles),
        toggles=toggles,
    )


@app.post("/admin/system/toggles", response_model=SystemToggleState)
async def admin_update_system_toggles(
    payload: SystemToggleUpdate,
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> SystemToggleState:
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_none=True).items()
        if isinstance(value, bool)
    }
    if updates:
        settings.update_dict(_SYSTEM_TOGGLE_KEY, updates)
    return _merge_system_toggles(settings, config)


@app.get("/admin/audio/output", response_model=AudioOutputStateOut)
async def admin_audio_output_state(
    scanner: AudioDeviceScanner = Depends(get_audio_device_scanner),
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> AudioOutputStateOut:
    devices = [AudioDeviceOut(**device.__dict__) for device in scanner.scan()]
    stored = settings.get_dict(_AUDIO_OUTPUT_KEY, {})
    active_device_id = stored.get("device_id") if isinstance(stored, dict) else None
    if active_device_id is None and devices:
        active_device_id = devices[0].identifier
    return AudioOutputStateOut(active_device_id=active_device_id, devices=devices)


@app.post("/admin/audio/output", response_model=AudioOutputStateOut)
async def admin_update_audio_output(
    payload: AudioOutputUpdate,
    scanner: AudioDeviceScanner = Depends(get_audio_device_scanner),
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> AudioOutputStateOut:
    available = {device.identifier for device in scanner.scan()}
    if payload.device_id not in available and available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unbekanntes Gerät")
    settings.set(_AUDIO_OUTPUT_KEY, {"device_id": payload.device_id})
    devices = [AudioDeviceOut(**device.__dict__) for device in scanner.scan()]
    return AudioOutputStateOut(active_device_id=payload.device_id, devices=devices)


@app.get("/admin/audio/mixer", response_model=MixerSettingsOut)
async def admin_mixer_settings(
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> MixerSettingsOut:
    return _load_mixer_settings(settings)


@app.post("/admin/audio/mixer", response_model=MixerSettingsOut)
async def admin_update_mixer_settings(
    payload: MixerSettingsUpdate,
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> MixerSettingsOut:
    updates = payload.model_dump(exclude_none=True)
    if updates:
        settings.update_dict(_AUDIO_MIXER_KEY, updates)
    return _load_mixer_settings(settings)


@app.get("/admin/library/settings", response_model=LibraryStateOut)
async def admin_library_settings(
    db: Database = Depends(get_database),
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> LibraryStateOut:
    return _library_state(db, settings, config)


@app.get("/admin/library/locations", response_model=List[MusicLocationOut])
async def admin_library_locations(
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> List[MusicLocationOut]:
    return _discover_music_locations(settings, config)


@app.post("/admin/library/settings", response_model=LibraryStateOut)
async def admin_update_library_settings(
    payload: LibraryUpdateRequest,
    db: Database = Depends(get_database),
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> LibraryStateOut:
    updates = payload.model_dump(exclude_none=True)
    if updates:
        settings.update_dict(_LIBRARY_SETTINGS_KEY, updates)
    return _library_state(db, settings, config)


@app.get("/admin/light/settings", response_model=LightSettingsOut)
async def admin_light_settings(
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> LightSettingsOut:
    toggles = _merge_system_toggles(settings, config)
    return _load_light_settings(settings, config, toggles)


@app.post("/admin/light/settings", response_model=LightSettingsOut)
async def admin_update_light_settings(
    payload: LightSettingsUpdate,
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> LightSettingsOut:
    updates = payload.model_dump(exclude_none=True)
    if updates:
        toggle_updates = {
            key: updates.pop(key)
            for key in list(updates.keys())
            if key in {"superscenes_enabled", "fog_enabled"}
        }
        if updates:
            settings.update_dict(_LIGHT_SETTINGS_KEY, updates)
        if toggle_updates:
            settings.update_dict(_SYSTEM_TOGGLE_KEY, toggle_updates)
    toggles = _merge_system_toggles(settings, config)
    return _load_light_settings(settings, config, toggles)


@app.post("/admin/light/resync", status_code=status.HTTP_204_NO_CONTENT)
async def admin_light_resync(
    osc: OscService = Depends(get_osc_service),
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> Response:
    try:
        osc.reset_bar()
    except Exception as exc:  # pragma: no cover - network failure branch
        settings.update_dict(SystemMonitor.OSC_STATUS_KEY, {"connected": False})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OSC-ReSync fehlgeschlagen",
        ) from exc
    settings.update_dict(SystemMonitor.OSC_STATUS_KEY, {"connected": True})
    # Refresh merged toggles to ensure they stay in sync with the stored state.
    _merge_system_toggles(settings, config)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/admin/analysis/settings", response_model=AnalysisSettingsOut)
async def admin_analysis_settings(
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> AnalysisSettingsOut:
    return _load_analysis_settings(settings, config)


@app.post("/admin/analysis/settings", response_model=AnalysisSettingsOut)
async def admin_update_analysis_settings(
    payload: AnalysisSettingsUpdate,
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> AnalysisSettingsOut:
    updates = payload.model_dump(exclude_none=True)
    if updates:
        settings.update_dict(_ANALYSIS_SETTINGS_KEY, updates)
    return _load_analysis_settings(settings, config)


@app.get("/admin/logs/diagnostics", response_model=DiagnosticsOut)
async def admin_diagnostics(
    settings: SettingsService = Depends(get_settings_service),
    config: AutoDjConfig = Depends(get_config),
    _: AdminUser = Depends(require_admin),
) -> DiagnosticsOut:
    last_error = settings.get("system.last_error")
    return DiagnosticsOut(
        runtime_log_path=str(config.paths.runtime_log_root),
        persistent_log_path=str(config.paths.persistent_log_root),
        cache_path=str(config.paths.cache_root),
        config_path=str(config.paths.config_root),
        last_error=last_error if isinstance(last_error, str) else None,
    )


@app.delete("/admin/queue/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_remove_queue_entry(
    entry_id: int,
    queue: QueueManager = Depends(get_queue_manager),
    _: AdminUser = Depends(require_admin),
) -> Response:
    try:
        queue.remove(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/admin/queue/{entry_id}/promote", response_model=QueueEntryOut)
async def admin_promote_queue_entry(
    entry_id: int,
    queue: QueueManager = Depends(get_queue_manager),
    _: AdminUser = Depends(require_admin),
) -> QueueEntry:
    try:
        entry = queue.promote(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return entry


@app.post("/admin/queue/{entry_id}/play", response_model=QueueEntryOut)
async def admin_mark_playing_queue_entry(
    entry_id: int,
    queue: QueueManager = Depends(get_queue_manager),
    _: AdminUser = Depends(require_admin),
) -> QueueEntry:
    try:
        entry = queue.mark_playing(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return entry
