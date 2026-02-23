from pathlib import Path

from services.fleet_registry import FleetRegistry


def test_fleet_registry_uses_tutti_data_dir_when_present(monkeypatch, tmp_path):
    data_dir = tmp_path / "desktop_data"
    monkeypatch.setenv("TUTTI_DATA_DIR", str(data_dir))
    monkeypatch.delenv("TUTTI_FLEET_STORAGE_PATH", raising=False)

    registry = FleetRegistry()

    expected = data_dir / "fleet_profiles.json"
    assert registry.storage_path == expected
    assert registry.storage_path.exists()


def test_fleet_registry_uses_explicit_storage_path(monkeypatch, tmp_path):
    explicit_path = tmp_path / "custom" / "fleet.json"
    monkeypatch.setenv("TUTTI_FLEET_STORAGE_PATH", str(explicit_path))

    registry = FleetRegistry()

    assert registry.storage_path == explicit_path
    assert registry.storage_path.exists()
