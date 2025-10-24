from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient
from urllib.parse import quote

from auto_dj.config import AutoDjConfig, DatabaseConfig, PathsConfig
from auto_dj.database.models import AdminUser
from auto_dj.database.session import Database
from auto_dj.services.bluetooth import BluetoothDevice
from auto_dj.services.playlists import PlaylistService
from auto_dj.services.queue import QueueManager
from auto_dj.tools.diagnostics import DiagnosticResult
from auto_dj.web.app import (
    app,
    get_bluetooth_manager,
    get_config,
    get_database,
    get_diagnostics_runner,
    get_playlist_service,
    get_queue_manager,
    require_admin,
)


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


@pytest.fixture
def admin_client(tmp_path):
    config = build_config(tmp_path)
    database = Database(config.database)
    database.create_all()

    playlist_service = PlaylistService(database)
    queue_manager = QueueManager(database, config.queue_policy, playlist_service)

    admin = AdminUser(
        id=1,
        username="admin",
        password_hash="hash",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_login_at=None,
    )

    overrides = {
        get_config: lambda: config,
        get_database: lambda: database,
        get_playlist_service: lambda: playlist_service,
        get_queue_manager: lambda: queue_manager,
        require_admin: lambda: admin,
    }

    for dependency, provider in overrides.items():
        app.dependency_overrides[dependency] = provider

    try:
        with TestClient(app) as client:
            yield client, database
    finally:
        for dependency in list(overrides):
            app.dependency_overrides.pop(dependency, None)


class FakeBluetoothManager:
    def __init__(self) -> None:
        self.device = BluetoothDevice(
            address="AA:BB:CC:DD:EE:FF",
            name="Studio Speaker",
            paired=True,
            trusted=True,
            connected=False,
        )

    def list_devices(self):
        return [self.device]

    def scan(self):
        return self.list_devices()

    def pair_device(self, address: str):
        self.device = BluetoothDevice(
            address=self.device.address,
            name=self.device.name,
            paired=True,
            trusted=True,
            connected=True,
        )
        return self.device

    def connect_device(self, address: str):
        self.device = BluetoothDevice(
            address=self.device.address,
            name=self.device.name,
            paired=True,
            trusted=True,
            connected=True,
        )
        return self.device

    def disconnect_device(self, address: str):
        self.device = BluetoothDevice(
            address=self.device.address,
            name=self.device.name,
            paired=True,
            trusted=True,
            connected=False,
        )
        return self.device


def test_admin_diagnostics_runner_override(admin_client):
    client, _ = admin_client

    def runner():
        return 0, [DiagnosticResult(name="music_library", success=True, detail="ok")]

    app.dependency_overrides[get_diagnostics_runner] = lambda: runner
    try:
        response = client.post("/admin/diagnostics/run")
        assert response.status_code == 200
        payload = response.json()
        assert payload["exit_code"] == 0
        assert payload["results"][0]["detail"] == "ok"
        assert payload["results"][0]["severity"] == "ok"
    finally:
        app.dependency_overrides.pop(get_diagnostics_runner, None)


def test_admin_bluetooth_listing(admin_client):
    client, _ = admin_client

    manager = FakeBluetoothManager()
    app.dependency_overrides[get_bluetooth_manager] = lambda: manager
    try:
        response = client.get("/admin/audio/bluetooth")
        assert response.status_code == 200
        payload = response.json()
        assert payload["devices"][0]["name"] == "Studio Speaker"
    finally:
        app.dependency_overrides.pop(get_bluetooth_manager, None)


def test_admin_bluetooth_scan_alias(admin_client):
    client, _ = admin_client

    manager = FakeBluetoothManager()
    app.dependency_overrides[get_bluetooth_manager] = lambda: manager
    try:
        response = client.post("/admin/bluetooth/scan")
        assert response.status_code == 200
        payload = response.json()
        assert payload["devices"][0]["address"] == "AA:BB:CC:DD:EE:FF"
    finally:
        app.dependency_overrides.pop(get_bluetooth_manager, None)


def test_admin_bluetooth_connect_action(admin_client):
    client, _ = admin_client

    manager = FakeBluetoothManager()
    app.dependency_overrides[get_bluetooth_manager] = lambda: manager
    try:
        response = client.post(
            "/admin/audio/bluetooth/connect",
            json={
                "address": "AA:BB:CC:DD:EE:FF",
                "connect": True,
                "set_default": False,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["device"]["connected"] is True
    finally:
        app.dependency_overrides.pop(get_bluetooth_manager, None)


def test_admin_bluetooth_connect_path_endpoint(admin_client):
    client, _ = admin_client

    manager = FakeBluetoothManager()
    app.dependency_overrides[get_bluetooth_manager] = lambda: manager
    try:
        encoded = quote(manager.device.address, safe="")
        response = client.post(f"/admin/bluetooth/connect/{encoded}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["device"]["connected"] is True
    finally:
        app.dependency_overrides.pop(get_bluetooth_manager, None)
