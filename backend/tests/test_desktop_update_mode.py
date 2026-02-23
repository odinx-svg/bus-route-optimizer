import importlib.util
import sys
import types
from pathlib import Path


def _load_desktop_launcher():
    module_name = "desktop_launcher_test_module"
    launcher_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "desktop" / "desktop_launcher.py"
    )

    # Stub pywebview to avoid GUI dependency during tests.
    fake_webview = types.ModuleType("webview")
    fake_webview.SAVE_DIALOG = 1
    fake_webview.create_window = lambda *args, **kwargs: None
    fake_webview.start = lambda *args, **kwargs: None
    sys.modules["webview"] = fake_webview

    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, launcher_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_update_mode_onedir_requires_installer():
    launcher = _load_desktop_launcher()
    installer_asset = {"name": "TuttiSetup.exe"}
    portable_asset = {"name": "TuttiDesktopApp.zip"}

    asset, update_mode, block_reason = launcher._resolve_update_asset_for_mode(
        install_mode="onedir_installed",
        installer_asset=installer_asset,
        portable_asset=portable_asset,
    )

    assert update_mode == "installer"
    assert block_reason is None
    assert asset == installer_asset


def test_update_mode_portable_requires_zip():
    launcher = _load_desktop_launcher()
    installer_asset = {"name": "TuttiSetup.exe"}
    portable_asset = {"name": "TuttiDesktopApp.zip"}

    asset, update_mode, block_reason = launcher._resolve_update_asset_for_mode(
        install_mode="portable",
        installer_asset=installer_asset,
        portable_asset=portable_asset,
    )

    assert update_mode == "portable"
    assert block_reason is None
    assert asset == portable_asset


def test_update_mode_portable_blocks_when_zip_missing():
    launcher = _load_desktop_launcher()
    installer_asset = {"name": "TuttiSetup.exe"}

    asset, update_mode, block_reason = launcher._resolve_update_asset_for_mode(
        install_mode="portable",
        installer_asset=installer_asset,
        portable_asset=None,
    )

    assert asset is None
    assert update_mode == "portable"
    assert block_reason == "portable_asset_missing"


def test_update_mode_onedir_blocks_when_installer_missing():
    launcher = _load_desktop_launcher()
    portable_asset = {"name": "TuttiDesktopApp.zip"}

    asset, update_mode, block_reason = launcher._resolve_update_asset_for_mode(
        install_mode="onedir_installed",
        installer_asset=None,
        portable_asset=portable_asset,
    )

    assert asset is None
    assert update_mode == "installer"
    assert block_reason == "installer_asset_missing"


def test_select_portable_asset_prefers_zip_and_ignores_exe_only():
    launcher = _load_desktop_launcher()
    release_with_zip = {
        "assets": [
            {"name": "TuttiSetup.exe"},
            {"name": "TuttiDesktopApp.zip"},
            {"name": "Tutti Desktop.exe"},
        ]
    }
    release_exe_only = {
        "assets": [
            {"name": "TuttiSetup.exe"},
            {"name": "Tutti Desktop.exe"},
        ]
    }

    selected = launcher._select_portable_asset(release_with_zip)
    assert selected and selected.get("name") == "TuttiDesktopApp.zip"

    selected_missing_zip = launcher._select_portable_asset(release_exe_only)
    assert selected_missing_zip is None
