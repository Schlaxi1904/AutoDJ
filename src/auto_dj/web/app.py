"""FastAPI web application with a modern control frontend."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import re
import unicodedata
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from ..audio.analyzer import summarize_music_directory
from ..config import AutoDjConfig, load_config
from ..database.models import AdminUser, QueueEntry, Track
from ..database.session import Database
from ..db_check import ensure_database_ready
from ..services.admin import AdminService
from ..services.audio_devices import AudioDeviceScanner
from ..services.bluetooth import BluetoothDevice, BluetoothError, BluetoothManager
from ..services.playlists import PlaylistDetail, PlaylistService, PlaylistSummary
from ..services.queue import QueueManager
from ..services.osc import OscService
from ..services.settings import SettingsService
from ..services.system import SystemMonitor
from ..tools.diagnostics import DiagnosticResult as DiagnosticResultModel, run_diagnostics
from .security import SessionManager

app = FastAPI(title="Auto-DJ")

BASE_DIR = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
_STATIC_DIR = BASE_DIR / "static"
_CONFIG = load_config()


@app.on_event("startup")
async def _startup_db_check() -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, ensure_database_ready, _CONFIG)

_SYSTEM_TOGGLE_KEY = "system.toggles"
_AUDIO_OUTPUT_KEY = "audio.output_device"
_AUDIO_MIXER_KEY = "audio.mixer"
_LIBRARY_SETTINGS_KEY = "library.settings"
_LIGHT_SETTINGS_KEY = "light.settings"
_ANALYSIS_SETTINGS_KEY = "analysis.settings"

_LIGHT_GENRE_META = {
    "techno": {"label": "Techno", "bank": 1},
    "hardstyle": {"label": "Hardstyle", "bank": 2},
    "house": {"label": "House", "bank": 3},
    "pop": {"label": "Pop", "bank": 4},
}
_LIGHT_ACTION_LABELS = {
    "idle": "Idle / Ambient (Slot 1)",
    "break": "Break (Slot 2)",
    "build": "Build (Slot 3)",
    "drop": "Drop (Slot 4)",
    "outro": "Outro (Slot 5)",
}
_LIGHT_ACTION_ORDER = tuple(_LIGHT_ACTION_LABELS.keys())

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def get_config() -> AutoDjConfig:
    return _CONFIG


def get_database(config: AutoDjConfig = Depends(get_config)) -> Database:
    return Database(config.database)


def get_playlist_service(db: Database = Depends(get_database)) -> PlaylistService:
    return PlaylistService(db)


def get_queue_manager(
    db: Database = Depends(get_database),
    config: AutoDjConfig = Depends(get_config),
    playlists: PlaylistService = Depends(get_playlist_service),
) -> QueueManager:
    return QueueManager(db, config.queue_policy, playlists)


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


def get_bluetooth_manager() -> BluetoothManager:
    return BluetoothManager()


def get_osc_service(config: AutoDjConfig = Depends(get_config)) -> OscService:
    return OscService(config.osc)


def get_diagnostics_runner() -> Callable[[], Tuple[int, List[DiagnosticResultModel]]]:
    return run_diagnostics


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


_TOKEN_ALNUM_RE = re.compile(r"[^0-9a-z]+")
_SQL_PUNCTUATION_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    (" ", ""),
    ("-", ""),
    ("_", ""),
    ("/", ""),
    ("\\", ""),
    (".", ""),
    (",", ""),
    ("!", ""),
    ("?", ""),
    (":", ""),
    (";", ""),
    ("(", ""),
    (")", ""),
    ("[", ""),
    ("]", ""),
    ("{", ""),
    ("}", ""),
    ("'", ""),
    ("\"", ""),
    ("&", ""),
    ("+", ""),
)
_SQL_ACCENT_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("ä", "a"),
    ("á", "a"),
    ("à", "a"),
    ("â", "a"),
    ("ã", "a"),
    ("å", "a"),
    ("æ", "ae"),
    ("ç", "c"),
    ("é", "e"),
    ("è", "e"),
    ("ê", "e"),
    ("ë", "e"),
    ("í", "i"),
    ("ì", "i"),
    ("î", "i"),
    ("ï", "i"),
    ("ñ", "n"),
    ("ó", "o"),
    ("ò", "o"),
    ("ô", "o"),
    ("õ", "o"),
    ("ö", "o"),
    ("ø", "o"),
    ("œ", "oe"),
    ("ú", "u"),
    ("ù", "u"),
    ("û", "u"),
    ("ü", "u"),
    ("ý", "y"),
    ("ÿ", "y"),
    ("ß", "ss"),
)


def _normalize_sql_column(column: ColumnElement) -> ColumnElement:
    normalized = func.lower(column)
    for source, target in _SQL_PUNCTUATION_REPLACEMENTS:
        normalized = func.replace(normalized, source, target)
    for source, target in _SQL_ACCENT_REPLACEMENTS:
        normalized = func.replace(normalized, source, target)
    return normalized


def _sanitize_token(value: str) -> str:
    return _TOKEN_ALNUM_RE.sub("", _normalize_text(value))



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


def _bluetooth_device_to_out(device: BluetoothDevice) -> BluetoothDeviceOut:
    return BluetoothDeviceOut(
        address=device.address,
        name=device.name,
        paired=device.paired,
        trusted=device.trusted,
        connected=device.connected,
    )


def _bluetooth_scan_response(manager: BluetoothManager) -> BluetoothScanOut:
    try:
        devices = manager.scan()
    except BluetoothError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return BluetoothScanOut(devices=[_bluetooth_device_to_out(device) for device in devices])


def _bluetooth_connect_action(
    manager: BluetoothManager,
    scanner: AudioDeviceScanner,
    settings: SettingsService,
    payload: "BluetoothConnectRequest",
) -> BluetoothActionOut:
    try:
        if payload.connect:
            device = manager.connect_device(payload.address)
        else:
            device = manager.disconnect_device(payload.address)
    except BluetoothError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audio_device_id: Optional[str] = None
    if payload.connect and payload.set_default:
        audio_device_id = _find_matching_audio_device(scanner, device.address, device.name)
        if audio_device_id:
            settings.set(_AUDIO_OUTPUT_KEY, {"device_id": audio_device_id})

    if payload.connect:
        message = "Bluetooth-Gerät verbunden"
        if payload.set_default and not audio_device_id:
            message = "Verbunden – bitte Ausgabegerät auswählen"
    else:
        message = "Bluetooth-Gerät getrennt"

    return BluetoothActionOut(
        device=_bluetooth_device_to_out(device),
        audio_device_id=audio_device_id,
        message=message,
    )


def _find_matching_audio_device(
    scanner: AudioDeviceScanner, address: str, name: str
) -> Optional[str]:
    normalized_address = re.sub(r"[^0-9a-f]", "", address.casefold())
    normalized_name = _normalize_text(name)
    best_match: Optional[str] = None
    for candidate in scanner.scan():
        haystack_identifier = re.sub(
            r"[^0-9a-f]", "", candidate.identifier.casefold()
        )
        haystack_label = _normalize_text(candidate.label)
        if normalized_address and normalized_address in haystack_identifier:
            return candidate.identifier
        if normalized_name and normalized_name in haystack_label:
            if candidate.kind == "bluetooth":
                return candidate.identifier
            best_match = candidate.identifier
    return best_match


def _sanitize_scene_bindings(raw: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    sanitized: Dict[str, Dict[str, int]] = {}
    for genre, actions in raw.items():
        if not isinstance(actions, dict):
            continue
        cleaned: Dict[str, int] = {}
        for action, value in actions.items():
            if action not in _LIGHT_ACTION_ORDER or value is None:
                continue
            try:
                number = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if number < 0 or number > 99:
                continue
            cleaned[action] = number
        if cleaned:
            sanitized[genre] = cleaned
    return sanitized


def _merge_scene_bindings(
    base: Dict[str, Dict[str, int]], *overrides: Dict[str, Dict[str, int]]
) -> Dict[str, Dict[str, int]]:
    merged: Dict[str, Dict[str, int]] = {
        genre: dict(actions) for genre, actions in base.items()
    }
    for override in overrides:
        for genre, actions in override.items():
            if not isinstance(actions, dict):
                continue
            target = merged.setdefault(genre, {})
            for action, value in actions.items():
                if action not in _LIGHT_ACTION_ORDER:
                    continue
                target[action] = int(value)
    return merged


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
        "scene_bindings": config.osc.scene_bindings,
    }
    stored = settings.get_dict(_LIGHT_SETTINGS_KEY, defaults)
    merged = {**defaults, **stored}
    stored_bindings_raw = merged.get("scene_bindings", {})
    sanitized_bindings = (
        _sanitize_scene_bindings(stored_bindings_raw)
        if isinstance(stored_bindings_raw, dict)
        else {}
    )
    combined_bindings = _merge_scene_bindings(
        config.osc.scene_bindings,
        sanitized_bindings,
    )

    binding_outputs: List[LightGenreBindingOut] = []
    for genre, meta in _LIGHT_GENRE_META.items():
        actions = combined_bindings.get(genre, {})
        binding_outputs.append(
            LightGenreBindingOut(
                genre=genre,
                label=meta["label"],
                bank=meta["bank"],
                actions={
                    action: actions.get(action)
                    for action in _LIGHT_ACTION_ORDER
                },
            )
        )
    for genre, actions in combined_bindings.items():
        if genre in _LIGHT_GENRE_META:
            continue
        binding_outputs.append(
            LightGenreBindingOut(
                genre=genre,
                label=genre.title(),
                bank=0,
                actions={
                    action: actions.get(action)
                    for action in _LIGHT_ACTION_ORDER
                },
            )
        )

    return LightSettingsOut(
        target_host=str(merged.get("target_host", defaults["target_host"])),
        target_port=int(merged.get("target_port", defaults["target_port"])),
        superscenes_enabled=toggles.superscenes_enabled,
        fog_enabled=toggles.fog_enabled,
        scene_bindings=binding_outputs,
        action_labels=dict(_LIGHT_ACTION_LABELS),
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
    music_path = str(merged.get("music_path", defaults["music_path"]))
    filesystem_count, filesystem_preview = summarize_music_directory(Path(music_path))

    return LibraryStateOut(
        music_path=music_path,
        database_dsn=str(merged.get("database_dsn", defaults["database_dsn"])),
        track_count=int(track_count or 0),
        quarantine_path=str(quarantine),
        filesystem_count=filesystem_count,
        filesystem_preview=filesystem_preview,
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


def _playlist_summary_to_out(summary: PlaylistSummary) -> PlaylistSummaryOut:
    return PlaylistSummaryOut(
        id=summary.id,
        name=summary.name,
        description=summary.description,
        track_count=summary.track_count,
        is_fallback=summary.is_fallback,
    )


def _playlist_detail_to_out(detail: PlaylistDetail) -> PlaylistDetailOut:
    return PlaylistDetailOut(
        id=detail.id,
        name=detail.name,
        description=detail.description,
        track_count=detail.track_count,
        is_fallback=detail.is_fallback,
        tracks=list(detail.tracks),
    )


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


class PasswordResetRequest(BaseModel):
    username: str
    new_password: str
    reset_code: str


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


class BluetoothDeviceOut(BaseModel):
    address: str
    name: str
    paired: bool
    trusted: bool
    connected: bool


class BluetoothScanOut(BaseModel):
    devices: List[BluetoothDeviceOut]


class BluetoothPairRequest(BaseModel):
    address: str
    set_default: bool = True


class BluetoothConnectRequest(BaseModel):
    address: str
    connect: bool = True
    set_default: bool = False


class BluetoothActionOut(BaseModel):
    device: BluetoothDeviceOut
    audio_device_id: Optional[str] = None
    message: str


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
    filesystem_count: int
    filesystem_preview: List[str]


class LibraryUpdateRequest(BaseModel):
    music_path: Optional[str] = None
    database_dsn: Optional[str] = None


class MusicLocationOut(BaseModel):
    path: str
    label: str
    kind: str
    available: bool


class PlaylistSummaryOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    track_count: int
    is_fallback: bool


class PlaylistDetailOut(PlaylistSummaryOut):
    tracks: List[TrackOut]


class PlaylistCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class PlaylistUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PlaylistTrackAddRequest(BaseModel):
    track_id: int


class PlaylistFallbackUpdate(BaseModel):
    playlist_id: Optional[int] = Field(default=None, ge=1)


class PlaylistFallbackOut(BaseModel):
    playlist_id: Optional[int]


class LightGenreBindingOut(BaseModel):
    genre: str
    label: str
    bank: int
    actions: Dict[str, Optional[int]]


class LightSettingsOut(BaseModel):
    target_host: str
    target_port: int
    superscenes_enabled: bool
    fog_enabled: bool
    scene_bindings: List[LightGenreBindingOut]
    action_labels: Dict[str, str]


class LightSettingsUpdate(BaseModel):
    target_host: Optional[str] = None
    target_port: Optional[int] = Field(default=None, ge=1, le=65535)
    superscenes_enabled: Optional[bool] = None
    fog_enabled: Optional[bool] = None
    scene_bindings: Optional[Dict[str, Dict[str, int]]] = None


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


class DiagnosticResultOut(BaseModel):
    name: str
    success: bool
    detail: str


class DiagnosticRunOut(BaseModel):
    exit_code: int
    results: List[DiagnosticResultOut]


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
    q: Optional[str] = Query(
        None, min_length=2, description="Artist or title search", alias="q"
    ),
    query: Optional[str] = Query(None, min_length=2, description="Artist or title search"),
    limit: int = Query(5, ge=1, le=50),
    db: Database = Depends(get_database),
) -> List[TrackSearchOut]:
    raw_query = query or q
    if not raw_query:
        return []

    normalized_query = re.sub(r"\s+", " ", raw_query).strip()
    if not normalized_query:
        return []

    raw_tokens = [token for token in re.split(r"\s+", normalized_query) if token]
    sanitized_tokens = [_sanitize_token(token) for token in raw_tokens]
    sanitized_tokens = [token for token in sanitized_tokens if token]
    if not sanitized_tokens:
        return []

    normalized_title = _normalize_sql_column(Track.title)
    normalized_artist = _normalize_sql_column(Track.artist)
    filters = [
        or_(
            normalized_title.like(f"%{token}%"),
            normalized_artist.like(f"%{token}%"),
        )
        for token in sanitized_tokens
    ]

    with db.session() as session:
        stmt = (
            select(Track)
            .where(and_(*filters))
            .order_by(Track.artist.asc(), Track.title.asc())
            .limit(max(25, limit * 5))
        )
        candidates = session.execute(stmt).scalars().all()

    results: List[Track] = []
    for track in candidates:
        haystack = _sanitize_token(f"{track.artist} {track.title}")
        if all(token in haystack for token in sanitized_tokens):
            results.append(track)
        if len(results) >= limit:
            break
    return results


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


@app.post("/admin/password-reset")
async def admin_password_reset(
    payload: PasswordResetRequest,
    admin_service: AdminService = Depends(get_admin_service),
) -> JSONResponse:
    try:
        admin_service.reset_password(
            payload.username, payload.new_password, payload.reset_code
        )
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return JSONResponse({"message": "reset"})


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


@app.get("/admin/audio/bluetooth", response_model=BluetoothScanOut)
async def admin_list_bluetooth_devices(
    manager: BluetoothManager = Depends(get_bluetooth_manager),
    _: AdminUser = Depends(require_admin),
) -> BluetoothScanOut:
    try:
        devices = manager.list_devices()
    except BluetoothError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return BluetoothScanOut(devices=[_bluetooth_device_to_out(device) for device in devices])


@app.post("/admin/audio/bluetooth/scan", response_model=BluetoothScanOut)
async def admin_scan_bluetooth_devices(
    manager: BluetoothManager = Depends(get_bluetooth_manager),
    _: AdminUser = Depends(require_admin),
) -> BluetoothScanOut:
    return _bluetooth_scan_response(manager)


@app.post("/admin/bluetooth/scan", response_model=BluetoothScanOut)
async def admin_scan_bluetooth_devices_root(
    manager: BluetoothManager = Depends(get_bluetooth_manager),
    _: AdminUser = Depends(require_admin),
) -> BluetoothScanOut:
    return _bluetooth_scan_response(manager)


@app.post("/admin/audio/bluetooth/pair", response_model=BluetoothActionOut)
async def admin_pair_bluetooth_device(
    payload: BluetoothPairRequest,
    manager: BluetoothManager = Depends(get_bluetooth_manager),
    scanner: AudioDeviceScanner = Depends(get_audio_device_scanner),
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> BluetoothActionOut:
    try:
        device = manager.pair_device(payload.address)
    except BluetoothError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audio_device_id: Optional[str] = None
    if payload.set_default:
        audio_device_id = _find_matching_audio_device(scanner, device.address, device.name)
        if audio_device_id:
            settings.set(_AUDIO_OUTPUT_KEY, {"device_id": audio_device_id})

    message = "Bluetooth-Gerät verbunden"
    if payload.set_default and not audio_device_id:
        message = (
            "Gerät gekoppelt – bitte gewünschtes Ausgabegerät manuell auswählen"
        )

    return BluetoothActionOut(
        device=_bluetooth_device_to_out(device),
        audio_device_id=audio_device_id,
        message=message,
    )


@app.post("/admin/audio/bluetooth/connect", response_model=BluetoothActionOut)
async def admin_connect_bluetooth_device(
    payload: BluetoothConnectRequest,
    manager: BluetoothManager = Depends(get_bluetooth_manager),
    scanner: AudioDeviceScanner = Depends(get_audio_device_scanner),
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> BluetoothActionOut:
    return _bluetooth_connect_action(manager, scanner, settings, payload)


@app.post("/admin/bluetooth/connect/{address}", response_model=BluetoothActionOut)
async def admin_connect_bluetooth_device_path(
    address: str,
    set_default: bool = Query(False),
    manager: BluetoothManager = Depends(get_bluetooth_manager),
    scanner: AudioDeviceScanner = Depends(get_audio_device_scanner),
    settings: SettingsService = Depends(get_settings_service),
    _: AdminUser = Depends(require_admin),
) -> BluetoothActionOut:
    payload = BluetoothConnectRequest(address=address, connect=True, set_default=set_default)
    return _bluetooth_connect_action(manager, scanner, settings, payload)


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


@app.get("/admin/playlists", response_model=List[PlaylistSummaryOut])
async def admin_list_playlists(
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> List[PlaylistSummaryOut]:
    summaries = playlists.list_playlists()
    return [_playlist_summary_to_out(summary) for summary in summaries]


@app.post("/admin/playlists", response_model=PlaylistDetailOut, status_code=status.HTTP_201_CREATED)
async def admin_create_playlist(
    payload: PlaylistCreateRequest,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistDetailOut:
    try:
        detail = playlists.create_playlist(payload.name, payload.description)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _playlist_detail_to_out(detail)


@app.get("/admin/playlists/{playlist_id}", response_model=PlaylistDetailOut)
async def admin_get_playlist(
    playlist_id: int,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistDetailOut:
    try:
        detail = playlists.get_playlist(playlist_id)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _playlist_detail_to_out(detail)


@app.patch("/admin/playlists/{playlist_id}", response_model=PlaylistDetailOut)
async def admin_update_playlist(
    playlist_id: int,
    payload: PlaylistUpdateRequest,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistDetailOut:
    try:
        detail = playlists.update_playlist(
            playlist_id, name=payload.name, description=payload.description
        )
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _playlist_detail_to_out(detail)


@app.delete("/admin/playlists/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_playlist(
    playlist_id: int,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> Response:
    try:
        playlists.delete_playlist(playlist_id)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/admin/playlists/{playlist_id}/tracks", response_model=PlaylistDetailOut)
async def admin_add_playlist_track(
    playlist_id: int,
    payload: PlaylistTrackAddRequest,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistDetailOut:
    try:
        detail = playlists.add_track(playlist_id, payload.track_id)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _playlist_detail_to_out(detail)


@app.delete("/admin/playlists/{playlist_id}/tracks/{track_id}", response_model=PlaylistDetailOut)
async def admin_remove_playlist_track(
    playlist_id: int,
    track_id: int,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistDetailOut:
    try:
        detail = playlists.remove_track(playlist_id, track_id)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _playlist_detail_to_out(detail)


@app.post("/admin/playlists/fallback", response_model=PlaylistFallbackOut)
async def admin_set_fallback_playlist(
    payload: PlaylistFallbackUpdate,
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistFallbackOut:
    try:
        playlist_id = playlists.set_fallback_playlist(payload.playlist_id)
    except ValueError as exc:  # pragma: no cover - simple validation branch
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PlaylistFallbackOut(playlist_id=playlist_id)


@app.get("/admin/playlists/fallback", response_model=PlaylistFallbackOut)
async def admin_get_fallback_playlist(
    playlists: PlaylistService = Depends(get_playlist_service),
    _: AdminUser = Depends(require_admin),
) -> PlaylistFallbackOut:
    return PlaylistFallbackOut(playlist_id=playlists.get_fallback_playlist_id())


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
        scene_binding_update = updates.pop("scene_bindings", None)
        if updates:
            settings.update_dict(_LIGHT_SETTINGS_KEY, updates)
        if scene_binding_update is not None:
            raw_bindings = (
                scene_binding_update if isinstance(scene_binding_update, dict) else {}
            )
            sanitized = _sanitize_scene_bindings(raw_bindings)
            current_settings = settings.get_dict(_LIGHT_SETTINGS_KEY, {})
            current_bindings_raw = current_settings.get("scene_bindings", {})
            current_sanitized = (
                _sanitize_scene_bindings(current_bindings_raw)
                if isinstance(current_bindings_raw, dict)
                else {}
            )
            merged_bindings = _merge_scene_bindings(
                config.osc.scene_bindings,
                current_sanitized,
                sanitized,
            )
            settings.update_dict(
                _LIGHT_SETTINGS_KEY, {"scene_bindings": merged_bindings}
            )
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


@app.post("/admin/diagnostics/run", response_model=DiagnosticRunOut)
async def admin_run_diagnostics(
    runner: Callable[[], Tuple[int, List[DiagnosticResultModel]]] = Depends(
        get_diagnostics_runner
    ),
    _: AdminUser = Depends(require_admin),
) -> DiagnosticRunOut:
    exit_code, results = runner()
    return DiagnosticRunOut(
        exit_code=exit_code,
        results=[
            DiagnosticResultOut(name=item.name, success=item.success, detail=item.detail)
            for item in results
        ],
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
