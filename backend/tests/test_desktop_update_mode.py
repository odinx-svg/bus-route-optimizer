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


def test_windows_installer_runner_uses_explicit_elevation():
    launcher = _load_desktop_launcher()
    batch_script, ps_script = launcher._build_windows_installer_runner_scripts(
        installer_args=[
            r"C:\Temp\TuttiSetup.exe",
            "/SP-",
            "/VERYSILENT",
            r"/LOG=C:\Users\Juanjo\AppData\Local\Tutti\logs\installer-update.log",
        ],
        target_exe=Path(r"C:\Program Files\TUTTI\Tutti Desktop.exe"),
        auto_restart=True,
        runner_ps1=Path(r"C:\Temp\tutti_desktop_installer_update.ps1"),
        updater_log_path=Path(r"C:\Users\Juanjo\AppData\Local\Tutti\logs\desktop-updater.log"),
    )

    assert "Start-Process -FilePath $installerPath -ArgumentList $arguments -Verb RunAs -Wait -PassThru" in ps_script
    assert '-WindowStyle Hidden -File "C:\\Temp\\tutti_desktop_installer_update.ps1"' in batch_script
    assert "INSTALLER_RUNNER_EXIT code=!INSTALLER_EXIT!" in batch_script


def test_launch_installer_windows_uses_shell_execute(monkeypatch, tmp_path):
    launcher = _load_desktop_launcher()
    installer = tmp_path / "TuttiSetup.exe"
    installer.write_bytes(b"stub")

    observed: dict[str, object] = {}

    class _FakeShell32:
        def ShellExecuteW(self, hwnd, verb, file_path, params, directory, show):
            observed["verb"] = verb
            observed["file_path"] = file_path
            observed["params"] = params
            observed["directory"] = directory
            observed["show"] = show
            return 33

    monkeypatch.setattr(
        launcher.ctypes,
        "windll",
        types.SimpleNamespace(shell32=_FakeShell32()),
        raising=False,
    )

    launched = launcher._launch_installer_and_exit(installer)

    assert launched is True
    assert observed["verb"] == "runas"
    assert observed["file_path"] == str(installer)
    assert "/VERYSILENT" in str(observed["params"])
    assert observed["directory"] == str(installer.parent)
