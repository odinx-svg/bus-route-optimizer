#!/usr/bin/env python3
"""
Tutti Desktop Launcher

Opens Tutti as a real desktop window (native WebView), starts the local backend
in background, and stops it automatically when the window is closed.
"""

from __future__ import annotations

import atexit
import ctypes
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import webview


APP_URL = "http://127.0.0.1:8000"
APP_HEALTH_URL = f"{APP_URL}/health"
GITHUB_API_BASE = "https://api.github.com"
UPDATE_HTTP_TIMEOUT_SEC = 20

try:
    from desktop_version import (  # type: ignore
        APP_VERSION,
        AUTO_UPDATE_ENABLED,
        GITHUB_REPO,
        RELEASE_ASSET_EXE,
        RELEASE_ASSET_ZIP,
    )
except Exception:
    APP_VERSION = "0.1.0"
    AUTO_UPDATE_ENABLED = True
    GITHUB_REPO = "odinx-svg/bus-route-optimizer"
    RELEASE_ASSET_ZIP = "TuttiDesktopApp.zip"
    RELEASE_ASSET_EXE = "Tutti Desktop.exe"


def _resolve_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller onefile extracts resources into _MEIPASS.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # Fallback for non-onefile frozen apps.
        return Path(sys.executable).resolve().parent

    # scripts/desktop/desktop_launcher.py -> project root is ../../
    return Path(__file__).resolve().parents[2]


def _resolve_update_log_path() -> Path:
    log_dir = Path.home() / "AppData" / "Local" / "Tutti" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "desktop-updater.log"


def _resolve_persistent_data_dir() -> Path:
    """Resolve a writable persistent data directory for desktop runtime."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        data_dir = base / "Tutti" / "data"
    else:
        data_dir = Path.home() / ".tutti" / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _sqlite_url_for_path(db_path: Path) -> str:
    absolute = db_path.resolve()
    return f"sqlite:///{absolute.as_posix()}"


def _force_line_buffered_stdio() -> None:
    """Make backend stdout/stderr flush line-by-line for live desktop logs."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(line_buffering=True, write_through=True)
        except Exception:
            # Best effort only.
            pass


def _env_flag(name: str, default: str = "0") -> bool:
    value = os.environ.get(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _log_update(message: str) -> None:
    try:
        log_path = _resolve_update_log_path()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}Z] {message}\n")
    except Exception:
        # Logging should never break application startup.
        pass


def _parse_version_numbers(version: str) -> tuple[int, ...]:
    # Accepts tags like "v0.1.2", "0.1.2-beta.1", etc.
    numbers = re.findall(r"\d+", version or "")
    if not numbers:
        return (0,)
    return tuple(int(part) for part in numbers)


def _is_newer_version(current_version: str, latest_version: str) -> bool:
    current = _parse_version_numbers(current_version)
    latest = _parse_version_numbers(latest_version)

    max_len = max(len(current), len(latest))
    current_norm = current + (0,) * (max_len - len(current))
    latest_norm = latest + (0,) * (max_len - len(latest))
    return latest_norm > current_norm


def _message_box(text: str, title: str, kind: str = "info") -> bool:
    if os.name != "nt":
        return False

    mb_ok = 0x00000000
    mb_yes_no = 0x00000004
    mb_icon_info = 0x00000040
    mb_icon_warn = 0x00000030

    if kind == "yesno":
        style = mb_yes_no | mb_icon_info
        result = ctypes.windll.user32.MessageBoxW(None, text, title, style)
        return result == 6  # IDYES

    style = mb_ok | (mb_icon_warn if kind == "warn" else mb_icon_info)
    ctypes.windll.user32.MessageBoxW(None, text, title, style)
    return False


def _fetch_latest_release(repo_slug: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "tutti-desktop-updater",
    }
    allow_prerelease = os.environ.get("TUTTI_DESKTOP_ALLOW_PRERELEASE") == "1"

    # Fast path: latest release endpoint.
    latest_url = f"{GITHUB_API_BASE}/repos/{repo_slug}/releases/latest"
    req = urllib.request.Request(latest_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=UPDATE_HTTP_TIMEOUT_SEC) as response:
            payload = response.read().decode("utf-8")
            release = json.loads(payload)
            if release and not release.get("draft"):
                return release
    except urllib.error.HTTPError as exc:
        # 404 means no "latest" release configured yet (or no published releases).
        if exc.code != 404:
            raise
    except Exception:
        # Fallback to the releases list below.
        pass

    # Fallback: iterate releases list and pick first valid one.
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_slug}/releases?per_page=25"
    req_list = urllib.request.Request(releases_url, headers=headers)
    with urllib.request.urlopen(req_list, timeout=UPDATE_HTTP_TIMEOUT_SEC) as response:
        payload = response.read().decode("utf-8")
        releases = json.loads(payload) or []

    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not allow_prerelease:
            continue
        if release.get("assets"):
            return release

    raise RuntimeError("No suitable GitHub release with assets found")


def _select_installer_asset(release_data: dict) -> Optional[dict]:
    assets = release_data.get("assets", []) or []
    by_name = {asset.get("name"): asset for asset in assets}

    exact_candidates = ("TuttiSetup.exe", "Tutti Installer.exe")
    for candidate in exact_candidates:
        if candidate in by_name:
            return by_name[candidate]

    for asset in assets:
        name = (asset.get("name") or "").lower()
        if not name.endswith(".exe"):
            continue
        if "setup" in name or "installer" in name or "install" in name:
            return asset
    return None


def _select_portable_asset(release_data: dict) -> Optional[dict]:
    assets = release_data.get("assets", []) or []
    by_name = {asset.get("name"): asset for asset in assets}
    installer_keywords = ("setup", "installer", "install")

    if RELEASE_ASSET_ZIP in by_name:
        return by_name[RELEASE_ASSET_ZIP]
    if RELEASE_ASSET_EXE in by_name:
        return by_name[RELEASE_ASSET_EXE]

    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(".zip"):
            return asset
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if any(keyword in name for keyword in installer_keywords):
            continue
        if name.endswith(".exe"):
            return asset
    return None


def _is_protected_install_path(exe_path: Path) -> bool:
    if os.name != "nt":
        return False

    install_dir = exe_path.resolve().parent
    protected_roots: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        value = os.environ.get(env_name)
        if value:
            protected_roots.append(Path(value).resolve())

    for root in protected_roots:
        try:
            if install_dir.is_relative_to(root):
                return True
        except Exception:
            continue

    probe = install_dir / f".tutti_write_probe_{int(time.time())}.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def _download_file(url: str, destination: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "tutti-desktop-updater"})
    with urllib.request.urlopen(req, timeout=60) as response, destination.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def _extract_exe_from_zip(zip_path: Path, work_dir: Path) -> Optional[Path]:
    extract_dir = work_dir / "release_extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)

    preferred = list(extract_dir.rglob(RELEASE_ASSET_EXE))
    if preferred:
        return preferred[0]

    candidates = list(extract_dir.rglob("*.exe"))
    return candidates[0] if candidates else None


def _launch_updater_and_exit(current_exe: Path, new_exe: Path) -> bool:
    updater_bat = Path(tempfile.gettempdir()) / "tutti_desktop_self_update.bat"
    script = f"""@echo off
setlocal
timeout /t 2 /nobreak >nul
copy /Y "{new_exe}" "{current_exe}" >nul
if errorlevel 1 goto fail
start "" "{current_exe}"
exit /b 0
:fail
start "" "{current_exe}"
exit /b 1
"""
    updater_bat.write_text(script, encoding="utf-8")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    subprocess.Popen(["cmd", "/c", str(updater_bat)], creationflags=creation_flags)
    return True


def _launch_installer_and_exit(installer_exe: Path) -> bool:
    try:
        if os.name == "nt":
            os.startfile(str(installer_exe))  # type: ignore[attr-defined]
        else:
            subprocess.Popen([str(installer_exe)])
        return True
    except Exception as exc:
        _log_update(f"Installer launch failed ({exc})")
        return False


def _check_and_apply_update_if_available() -> bool:
    if not AUTO_UPDATE_ENABLED:
        return False
    if os.environ.get("TUTTI_DESKTOP_DISABLE_AUTO_UPDATE") == "1":
        return False
    if not getattr(sys, "frozen", False):
        # Auto-update is intended for distributed EXE builds.
        return False

    current_exe = Path(sys.executable).resolve()
    _log_update(
        f"Auto-update check started | current_version={APP_VERSION} | exe={current_exe}"
    )
    try:
        release = _fetch_latest_release(GITHUB_REPO)
    except Exception as exc:
        _log_update(f"Update check skipped: could not fetch release ({exc})")
        return False

    latest_tag = str(release.get("tag_name") or "").strip()
    if not latest_tag:
        _log_update("Update check skipped: release has no tag_name")
        return False
    if not _is_newer_version(APP_VERSION, latest_tag):
        _log_update(
            f"No update available | current_version={APP_VERSION} | latest_tag={latest_tag}"
        )
        return False

    installer_asset = _select_installer_asset(release)
    portable_asset = _select_portable_asset(release)
    protected_install = _is_protected_install_path(current_exe)

    asset: Optional[dict] = None
    update_mode = "portable"
    if protected_install and installer_asset:
        asset = installer_asset
        update_mode = "installer"
    elif portable_asset:
        asset = portable_asset
        update_mode = "portable"
    elif installer_asset:
        asset = installer_asset
        update_mode = "installer"

    if not asset:
        _log_update(f"Release {latest_tag} found but no compatible asset was found")
        return False
    if protected_install and update_mode != "installer":
        _log_update(
            "Update blocked: install path is protected and release has no installer asset"
        )
        _message_box(
            (
                "Hay una nueva version, pero esta instalacion requiere actualizacion con instalador.\n\n"
                "Sube TuttiSetup.exe al release y vuelve a abrir TUTTI."
            ),
            "TUTTI - Actualizacion pendiente",
            kind="warn",
        )
        return False

    confirm = _message_box(
        (
            f"Hay una nueva version disponible: {latest_tag}\\n"
            f"Version actual: {APP_VERSION}\\n\\n"
            "Deseas actualizar ahora?"
        ),
        "TUTTI - Actualizacion disponible",
        kind="yesno",
    )
    if not confirm:
        return False

    download_url = asset.get("browser_download_url")
    asset_name = asset.get("name") or "release_asset"
    if not download_url:
        _log_update("Update aborted: release asset has no download URL")
        _message_box("No se pudo obtener el enlace de descarga de la actualizacion.", "TUTTI", kind="warn")
        return False

    work_dir = Path(tempfile.mkdtemp(prefix="tutti_update_"))
    asset_path = work_dir / asset_name

    try:
        _log_update(
            f"Downloading update asset | tag={latest_tag} | asset={asset_name} | url={download_url}"
        )
        _download_file(download_url, asset_path)
        if update_mode == "installer":
            _log_update(
                f"Installer update downloaded | tag={latest_tag} | asset={asset_name}"
            )
            _message_box(
                (
                    "Se abrira el instalador de actualizacion.\n"
                    "Sigue el asistente y al finalizar se abrira TUTTI."
                ),
                "TUTTI - Actualizando",
                kind="info",
            )
            return _launch_installer_and_exit(asset_path)

        if str(asset_name).lower().endswith(".zip"):
            updated_exe = _extract_exe_from_zip(asset_path, work_dir)
            if not updated_exe:
                _log_update("Update failed: zip downloaded but no .exe found inside")
                _message_box("No se encontro el .exe dentro del ZIP de actualizacion.", "TUTTI", kind="warn")
                return False
        else:
            updated_exe = asset_path

        _log_update(
            f"Update downloaded successfully | applying update to {current_exe} from {updated_exe}"
        )
        _message_box(
            "Actualizacion descargada. La app se cerrara para aplicar cambios y volvera a abrirse.",
            "TUTTI - Actualizando",
            kind="info",
        )
        return _launch_updater_and_exit(current_exe=current_exe, new_exe=updated_exe)
    except Exception as exc:
        _log_update(f"Update failed while downloading/applying ({exc})")
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass
        return False


def _run_backend_process_mode() -> int:
    runtime_root = _resolve_runtime_root()
    backend_dir = runtime_root / "backend"
    frontend_dist = runtime_root / "frontend" / "dist"
    data_dir = _resolve_persistent_data_dir()
    database_url = _sqlite_url_for_path(data_dir / "tutti_desktop.db")

    os.environ.setdefault("SERVE_FRONTEND_DIST", "true")
    os.environ.setdefault("FRONTEND_DIST_DIR", str(frontend_dist))
    os.environ.setdefault("APP_RUNTIME_MODE", "stable")
    os.environ.setdefault("CELERY_ENABLED", "false")
    os.environ.setdefault("WEBSOCKET_ENABLED", "true")
    os.environ.setdefault("USE_DATABASE", "true")
    os.environ.setdefault("DATABASE_URL", database_url)
    os.environ.setdefault("TUTTI_DATA_DIR", str(data_dir))
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")

    os.chdir(backend_dir)
    # Support both import styles in runtime:
    # - local modules: from services... / from optimizer_v6...
    # - package modules: from backend.services...
    sys.path.insert(0, str(backend_dir))
    sys.path.insert(0, str(runtime_root))
    _force_line_buffered_stdio()

    try:
        from main import app  # local import to avoid loading backend in UI bootstrap
        import uvicorn
    except ModuleNotFoundError as exc:
        _message_box(
            (
                "Faltan modulos internos en este ejecutable.\n\n"
                f"Detalle: {exc}\n\n"
                "Rebuild requerido: ejecuta scripts\\desktop\\build-desktop-app-exe.bat"
            ),
            "TUTTI - Desktop packaging error",
            kind="warn",
        )
        return 1

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    return 0


def _wait_backend_ready(timeout_sec: int = 60) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(APP_HEALTH_URL, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1)
    return False


class DesktopRuntime:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.backend_dir = runtime_root / "backend"
        self.frontend_dist = runtime_root / "frontend" / "dist"
        self.venv_python = runtime_root / ".venv" / "Scripts" / "python.exe"
        self.backend_proc: Optional[subprocess.Popen] = None
        self.log_handle = None

    def _python_cmd(self) -> str:
        if self.venv_python.exists():
            return str(self.venv_python)
        return sys.executable

    def start_backend(self) -> None:
        data_dir = _resolve_persistent_data_dir()
        database_url = _sqlite_url_for_path(data_dir / "tutti_desktop.db")

        env = os.environ.copy()
        env["SERVE_FRONTEND_DIST"] = "true"
        env["FRONTEND_DIST_DIR"] = str(self.frontend_dist)
        env["APP_RUNTIME_MODE"] = "stable"
        env["CELERY_ENABLED"] = "false"
        env["WEBSOCKET_ENABLED"] = "true"
        env["USE_DATABASE"] = "true"
        env["DATABASE_URL"] = database_url
        env["TUTTI_DATA_DIR"] = str(data_dir)
        env["PYTHONUNBUFFERED"] = "1"
        env["CORS_ORIGINS"] = "http://127.0.0.1:8000,http://localhost:8000"

        logs_dir = Path.home() / "AppData" / "Local" / "Tutti" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        backend_log_path = logs_dir / "desktop-backend.log"
        env["TUTTI_DESKTOP_LOGFILE"] = str(backend_log_path)

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-backend"]
        else:
            cmd = [
                self._python_cmd(),
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ]

        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        self.log_handle = open(backend_log_path, "a", encoding="utf-8")
        self.log_handle.write("\n===== TUTTI DESKTOP BACKEND START =====\n")
        self.log_handle.flush()

        self.backend_proc = subprocess.Popen(
            cmd,
            cwd=str(self.backend_dir),
            env=env,
            creationflags=creation_flags,
            stdout=self.log_handle,
            stderr=self.log_handle,
        )

    def stop_backend(self) -> None:
        if not self.backend_proc:
            return
        if self.backend_proc.poll() is not None:
            return
        try:
            self.backend_proc.terminate()
            self.backend_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.backend_proc.kill()
        except OSError:
            pass
        finally:
            if self.log_handle:
                try:
                    self.log_handle.write("===== TUTTI DESKTOP BACKEND STOP =====\n")
                    self.log_handle.flush()
                    self.log_handle.close()
                except Exception:
                    pass
                self.log_handle = None


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--run-backend":
        return _run_backend_process_mode()

    if _check_and_apply_update_if_available():
        return 0

    runtime_root = _resolve_runtime_root()
    runtime = DesktopRuntime(runtime_root)

    def _safe_shutdown(*_args: object) -> None:
        runtime.stop_backend()

    atexit.register(_safe_shutdown)
    signal.signal(signal.SIGTERM, _safe_shutdown)
    signal.signal(signal.SIGINT, _safe_shutdown)

    if not runtime.frontend_dist.joinpath("index.html").exists():
        print("[Desktop] Frontend build not found. Run: npm run build (frontend)")
        return 1

    runtime.start_backend()
    if not _wait_backend_ready(timeout_sec=60):
        runtime.stop_backend()
        print("[Desktop] Backend did not become ready in time.")
        return 1

    default_fullscreen = "1" if getattr(sys, "frozen", False) else "0"
    start_fullscreen = _env_flag("TUTTI_DESKTOP_START_FULLSCREEN", default_fullscreen)
    frameless_window = _env_flag("TUTTI_DESKTOP_FRAMELESS", "0")

    window_options = {
        "width": 1600,
        "height": 1000,
        "min_size": (1200, 760),
        "background_color": "#0a1324",
        "fullscreen": start_fullscreen,
    }
    if not start_fullscreen:
        window_options["maximized"] = True
    if frameless_window:
        window_options["frameless"] = True
        window_options["easy_drag"] = True

    window = webview.create_window(
        "TUTTI Fleet Control Center",
        APP_URL,
        **window_options,
    )
    window.events.closed += _safe_shutdown
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
