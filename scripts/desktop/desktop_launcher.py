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


def _select_release_asset(release_data: dict) -> Optional[dict]:
    assets = release_data.get("assets", []) or []
    by_name = {asset.get("name"): asset for asset in assets}

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
        if name.endswith(".exe"):
            return asset
    return None


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

    asset = _select_release_asset(release)
    if not asset:
        _log_update(f"Release {latest_tag} found but no compatible asset was found")
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
    data_dir = backend_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("SERVE_FRONTEND_DIST", "true")
    os.environ.setdefault("FRONTEND_DIST_DIR", str(frontend_dist))
    os.environ.setdefault("APP_RUNTIME_MODE", "stable")
    os.environ.setdefault("CELERY_ENABLED", "false")
    os.environ.setdefault("WEBSOCKET_ENABLED", "true")
    os.environ.setdefault("USE_DATABASE", "true")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/tutti_desktop.db")
    os.environ.setdefault("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")

    os.chdir(backend_dir)
    # Support both import styles in runtime:
    # - local modules: from services... / from optimizer_v6...
    # - package modules: from backend.services...
    sys.path.insert(0, str(backend_dir))
    sys.path.insert(0, str(runtime_root))

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
        data_dir = self.backend_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["SERVE_FRONTEND_DIST"] = "true"
        env["FRONTEND_DIST_DIR"] = str(self.frontend_dist)
        env["APP_RUNTIME_MODE"] = "stable"
        env["CELERY_ENABLED"] = "false"
        env["WEBSOCKET_ENABLED"] = "true"
        env["USE_DATABASE"] = "true"
        env["DATABASE_URL"] = "sqlite:///./data/tutti_desktop.db"
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

    window = webview.create_window(
        "TUTTI Fleet Control Center",
        APP_URL,
        width=1600,
        height=1000,
        min_size=(1200, 760),
        background_color="#0a1324",
    )
    window.events.closed += _safe_shutdown
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
