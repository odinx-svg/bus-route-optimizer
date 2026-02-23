#!/usr/bin/env python3
"""
Tutti Desktop Launcher

Opens Tutti as a real desktop window (native WebView), starts the local backend
in background, and stops it automatically when the window is closed.
"""

from __future__ import annotations

import atexit
import base64
import ctypes
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, MutableMapping, Optional

import webview


APP_URL = "http://127.0.0.1:8000"
APP_HEALTH_URL = f"{APP_URL}/health"
GITHUB_API_BASE = "https://api.github.com"
UPDATE_HTTP_TIMEOUT_SEC = 20
DESKTOP_OSRM_BASE_URL = "http://187.77.33.218:5000"
DESKTOP_OSRM_ROUTE_URL = f"{DESKTOP_OSRM_BASE_URL}/route/v1/driving"
DESKTOP_OSRM_TABLE_URL = f"{DESKTOP_OSRM_BASE_URL}/table/v1/driving"
CHECKSUM_ASSET_NAME = "checksums-sha256.txt"

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


def _apply_desktop_osrm_defaults(env_map: MutableMapping[str, str]) -> str:
    """
    Ensure desktop runtime has a deterministic OSRM endpoint.

    setdefault keeps manual overrides (system/user env) intact.
    """
    env_map.setdefault("OSRM_BASE_URL", DESKTOP_OSRM_BASE_URL)
    env_map.setdefault("OSRM_ROUTE_URL", DESKTOP_OSRM_ROUTE_URL)
    env_map.setdefault("OSRM_TABLE_URL", DESKTOP_OSRM_TABLE_URL)
    env_map.setdefault("OSRM_URL", env_map.get("OSRM_ROUTE_URL", DESKTOP_OSRM_ROUTE_URL))
    return str(env_map.get("OSRM_BASE_URL", DESKTOP_OSRM_BASE_URL))


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


def _is_onedir_install(exe_path: Path) -> bool:
    """Return True when the executable is part of a PyInstaller onedir layout."""
    try:
        return (exe_path.resolve().parent / "_internal").is_dir()
    except Exception:
        return False


def _download_file(
    url: str,
    destination: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Download a file and return its SHA-256 hex digest.

    *progress_callback(bytes_downloaded, total_bytes)* is called after every
    chunk.  ``total_bytes`` is ``0`` when the server does not advertise
    Content-Length.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "tutti-desktop-updater"})
    sha256 = hashlib.sha256()
    downloaded = 0
    with urllib.request.urlopen(req, timeout=120) as response, destination.open("wb") as output:
        total = int(response.headers.get("Content-Length") or 0)
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            sha256.update(chunk)
            downloaded += len(chunk)
            if progress_callback:
                try:
                    progress_callback(downloaded, total)
                except Exception:
                    pass
    return sha256.hexdigest()


def _fetch_expected_checksum(release_data: dict, asset_name: str) -> Optional[str]:
    """Try to find the SHA-256 checksum for *asset_name* in the release.

    Looks for a ``checksums-sha256.txt`` asset that contains lines in the
    format ``<hex_hash>  <filename>`` (sha256sum style).
    """
    assets = release_data.get("assets", []) or []
    checksum_asset = None
    for asset in assets:
        if (asset.get("name") or "").lower() == CHECKSUM_ASSET_NAME:
            checksum_asset = asset
            break
    if not checksum_asset:
        return None

    download_url = checksum_asset.get("browser_download_url")
    if not download_url:
        return None

    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "tutti-desktop-updater"})
        with urllib.request.urlopen(req, timeout=UPDATE_HTTP_TIMEOUT_SEC) as response:
            content = response.read().decode("utf-8")
        for line in content.strip().splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[1].strip("* ") == asset_name:
                return parts[0].lower()
    except Exception as exc:
        _log_update(f"Could not fetch checksum file ({exc})")
    return None


def _verify_checksum(file_path: Path, actual_hash: str, expected_hash: Optional[str]) -> bool:
    """Return True if the download integrity is verified.

    If no expected hash is available the check is skipped (best-effort).
    """
    if not expected_hash:
        _log_update("Checksum verification skipped: no expected hash available")
        return True
    if actual_hash.lower() == expected_hash.lower():
        _log_update(f"Checksum OK: {actual_hash}")
        return True
    _log_update(f"CHECKSUM MISMATCH: expected={expected_hash} actual={actual_hash}")
    return False


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


def _resolve_backup_dir() -> Path:
    """Return the directory where pre-update backups are kept."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".tutti"
    backup_dir = base / "Tutti" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _create_backup(current_exe: Path) -> Optional[Path]:
    """Copy the running executable to the backup directory.

    Keeps only the two most recent backups to save disk space.
    """
    backup_dir = _resolve_backup_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"Tutti Desktop {APP_VERSION} ({timestamp}).exe"
    try:
        shutil.copy2(current_exe, backup_path)
        _log_update(f"Backup created: {backup_path}")
    except Exception as exc:
        _log_update(f"Backup failed ({exc})")
        return None

    # Prune old backups – keep the 2 most recent.
    existing = sorted(backup_dir.glob("Tutti Desktop *.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old_backup in existing[2:]:
        try:
            old_backup.unlink()
            _log_update(f"Pruned old backup: {old_backup.name}")
        except Exception:
            pass

    return backup_path


def _launch_updater_and_exit(current_exe: Path, new_exe: Path, backup_exe: Optional[Path]) -> bool:
    """Replace the running exe with the new one via a helper batch script.

    The batch script:
    1. Waits for the main process to exit.
    2. Retries the copy up to 5 times (handles file-lock races).
    3. Verifies the new exe exists and has a non-zero size.
    4. On failure, restores from backup if available.
    5. Auto-restarts the app when TUTTI_DESKTOP_AUTORESTART_AFTER_UPDATE=1.
    """
    auto_restart = _env_flag("TUTTI_DESKTOP_AUTORESTART_AFTER_UPDATE", "1")
    start_cmd = (
        f'set "TUTTI_AFTER_UPDATE=1"\n'
        f'set "TUTTI_DESKTOP_DISABLE_AUTO_UPDATE=1"\n'
        f'timeout /t 12 /nobreak >nul\n'
        f'start "" "{current_exe}"'
        if auto_restart
        else 'echo Actualizacion aplicada. Abre TUTTI manualmente.'
    )
    backup_line = ""
    if backup_exe and backup_exe.exists():
        backup_line = f"""
echo Restaurando backup...
copy /Y "{backup_exe}" "{current_exe}" >nul
if errorlevel 1 (
    echo ERROR: No se pudo restaurar el backup.
)
"""

    updater_bat = Path(tempfile.gettempdir()) / "tutti_desktop_self_update.bat"
    script = f"""@echo off
setlocal EnableDelayedExpansion
set "RETRIES=0"
:wait_exit
timeout /t 2 /nobreak >nul

:retry_copy
copy /Y "{new_exe}" "{current_exe}" >nul
if errorlevel 1 (
    set /a RETRIES+=1
    if !RETRIES! GEQ 5 goto fail
    timeout /t 2 /nobreak >nul
    goto retry_copy
)

REM Verify the new exe is present and non-empty
if not exist "{current_exe}" goto fail
for %%A in ("{current_exe}") do if %%~zA==0 goto fail

{start_cmd}
exit /b 0

:fail
echo ERROR: La actualizacion fallo.
{backup_line}
{start_cmd}
exit /b 1
"""
    updater_bat.write_text(script, encoding="utf-8")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    subprocess.Popen(["cmd", "/c", str(updater_bat)], creationflags=creation_flags)
    return True


def _build_installer_update_args(installer_exe: Path) -> list[str]:
    args = [str(installer_exe)]
    silent_update_enabled = _env_flag("TUTTI_DESKTOP_UPDATE_SILENT", "1")
    if not silent_update_enabled:
        return args

    installer_log_path = _resolve_update_log_path().parent / "installer-update.log"
    args.extend(
        [
            "/SP-",
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NOCANCEL",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/FORCECLOSEAPPLICATIONS",
            f"/LOG={installer_log_path}",
        ]
    )
    return args


def _launch_installer_and_exit(installer_exe: Path, expected_exe: Optional[Path] = None) -> bool:
    try:
        auto_restart = _env_flag("TUTTI_DESKTOP_AUTORESTART_AFTER_UPDATE", "1")
        target_exe = (expected_exe or Path(sys.executable)).resolve()
        installer_args = _build_installer_update_args(installer_exe)
        _log_update(f"Launching installer update | args={' '.join(installer_args[1:]) or '(interactive)'}")

        if os.name == "nt":
            runner_bat = Path(tempfile.gettempdir()) / "tutti_desktop_installer_update.bat"
            command_line = subprocess.list2cmdline(installer_args)
            current_pid = os.getpid()
            target_exe_dir = target_exe.parent
            script = f"""@echo off
setlocal EnableDelayedExpansion
set "TARGET_PID={current_pid}"
set "TARGET_EXE={target_exe}"
set "TARGET_EXE_DIR={target_exe_dir}"
set "WAIT_SEC=0"
set "AUTO_RESTART={1 if auto_restart else 0}"

:wait_for_tutti_exit
tasklist /FI "PID eq %TARGET_PID%" | findstr /I "%TARGET_PID%" >nul
if not errorlevel 1 (
    set /a WAIT_SEC+=1
    if !WAIT_SEC! GEQ 30 goto force_kill
    timeout /t 1 /nobreak >nul
    goto wait_for_tutti_exit
)

goto run_installer

:force_kill
taskkill /PID %TARGET_PID% /T /F >nul 2>&1

:run_installer
taskkill /IM "Tutti Desktop.exe" /T /F >nul 2>&1
timeout /t 1 /nobreak >nul

start /wait "" {command_line}
if not errorlevel 1 (
    if "%AUTO_RESTART%"=="1" (
        set "TRY=0"
        :wait_target
        if exist "%TARGET_EXE%" goto start_target
        set /a TRY+=1
        if !TRY! GEQ 12 goto done
        timeout /t 1 /nobreak >nul
        goto wait_target

        :start_target
        set "TUTTI_AFTER_UPDATE=1"
        set "TUTTI_DESKTOP_DISABLE_AUTO_UPDATE=1"
        if not exist "%TARGET_EXE%" goto done
        for %%A in ("%TARGET_EXE%") do if %%~zA==0 goto done
        timeout /t 18 /nobreak >nul
        start "" /D "%TARGET_EXE_DIR%" "%TARGET_EXE%"
    )
)

:done
exit /b 0
"""
            runner_bat.write_text(script, encoding="utf-8")
            creation_flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            subprocess.Popen(["cmd", "/c", str(runner_bat)], creationflags=creation_flags)
        else:
            subprocess.Popen(installer_args)
        return True
    except Exception as exc:
        _log_update(f"Installer launch failed ({exc})")
        return False


def _build_changelog_summary(release_data: dict, max_lines: int = 12) -> str:
    """Extract a human-readable changelog snippet from the release body."""
    body = (release_data.get("body") or "").strip()
    if not body:
        return ""

    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Skip markdown headings like "## What's Changed", keep content.
        if line.startswith("#"):
            continue
        # Skip GitHub auto-generated boilerplate lines.
        if line.startswith("**Full Changelog**"):
            continue
        lines.append(line)
        if len(lines) >= max_lines:
            lines.append("...")
            break

    return "\n".join(lines)


def _make_progress_window_html() -> str:
    """Return a small HTML page used as a download progress overlay."""
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{margin:0;background:#0a1324;color:#e2e8f0;font-family:'Segoe UI',sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column}
h2{font-size:18px;margin-bottom:16px;font-weight:500}
.bar-outer{width:340px;height:18px;background:#1e293b;border-radius:9px;overflow:hidden}
.bar-inner{height:100%;width:0%;background:linear-gradient(90deg,#3b82f6,#06b6d4);
border-radius:9px;transition:width .3s}
#pct{margin-top:10px;font-size:13px;color:#94a3b8}
#status{margin-top:6px;font-size:12px;color:#64748b}
</style></head><body>
<h2>Descargando actualizacion...</h2>
<div class="bar-outer"><div class="bar-inner" id="bar"></div></div>
<div id="pct">0%</div>
<div id="status">Conectando...</div>
</body></html>"""


class _ProgressReporter:
    """Bridges download progress to the progress WebView window."""

    def __init__(self, webview_window: Optional[object] = None) -> None:
        self._window = webview_window
        self._last_pct = -1

    def __call__(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = min(int(downloaded * 100 / total), 100)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            status_text = f"{mb_done:.1f} MB / {mb_total:.1f} MB"
        else:
            pct = 0
            mb_done = downloaded / (1024 * 1024)
            status_text = f"{mb_done:.1f} MB descargados"

        if pct == self._last_pct:
            return
        self._last_pct = pct

        if self._window:
            try:
                self._window.evaluate_js(
                    f"document.getElementById('bar').style.width='{pct}%';"
                    f"document.getElementById('pct').textContent='{pct}%';"
                    f"document.getElementById('status').textContent='{status_text}';"
                )
            except Exception:
                pass


def _check_and_apply_update_if_available() -> bool:
    if not AUTO_UPDATE_ENABLED:
        return False
    if os.environ.get("TUTTI_DESKTOP_DISABLE_AUTO_UPDATE") == "1":
        return False
    if not getattr(sys, "frozen", False):
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
    onedir_install = _is_onedir_install(current_exe)

    asset: Optional[dict] = None
    update_mode = "portable"
    if (onedir_install or protected_install) and installer_asset:
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
    _log_update(
        f"Update mode resolved | onedir_install={onedir_install} "
        f"protected_install={protected_install} mode={update_mode} asset={asset.get('name', '?')}"
    )
    if (protected_install or onedir_install) and update_mode != "installer":
        _log_update(
            "Update blocked: installer mode required but release has no installer asset"
        )
        _message_box(
            (
                "Hay una nueva version, pero esta instalacion requiere actualizacion por instalador.\n\n"
                "Sube TuttiSetup.exe al release y vuelve a abrir TUTTI."
            ),
            "TUTTI - Actualizacion pendiente",
            kind="warn",
        )
        return False

    # Build changelog for the confirmation dialog.
    changelog = _build_changelog_summary(release)
    changelog_block = ""
    if changelog:
        changelog_block = f"\n\nNovedades:\n{changelog}"

    asset_size = asset.get("size") or 0
    size_label = f" ({asset_size / (1024 * 1024):.1f} MB)" if asset_size else ""

    confirm = _message_box(
        (
            f"Hay una nueva version disponible: {latest_tag}\n"
            f"Version actual: {APP_VERSION}\n"
            f"Descarga: {asset.get('name', '?')}{size_label}"
            f"{changelog_block}\n\n"
            "Deseas actualizar ahora?"
        ),
        "TUTTI - Actualizacion disponible",
        kind="yesno",
    )
    if not confirm:
        _log_update("User declined update")
        return False

    download_url = asset.get("browser_download_url")
    asset_name = asset.get("name") or "release_asset"
    if not download_url:
        _log_update("Update aborted: release asset has no download URL")
        _message_box("No se pudo obtener el enlace de descarga de la actualizacion.", "TUTTI", kind="warn")
        return False

    # Fetch expected checksum before downloading.
    expected_hash = _fetch_expected_checksum(release, asset_name)

    work_dir = Path(tempfile.mkdtemp(prefix="tutti_update_"))
    asset_path = work_dir / asset_name

    # Show progress window while downloading.
    progress_win: Optional[object] = None
    try:
        progress_win = webview.create_window(
            "TUTTI - Descargando actualizacion",
            html=_make_progress_window_html(),
            width=460,
            height=200,
            resizable=False,
            on_top=True,
        )
    except Exception:
        pass

    reporter = _ProgressReporter(progress_win)
    download_hash: Optional[str] = None
    download_error: Optional[Exception] = None

    def _do_download() -> None:
        nonlocal download_hash, download_error
        try:
            _log_update(
                f"Downloading update asset | tag={latest_tag} | asset={asset_name} | url={download_url}"
            )
            download_hash = _download_file(download_url, asset_path, progress_callback=reporter)
        except Exception as exc:
            download_error = exc

    download_thread = threading.Thread(target=_do_download, daemon=True)
    download_thread.start()

    if progress_win:
        try:
            # webview.start blocks until all windows close.  We poll the
            # download thread and close the window when done.
            def _poll_download(win: object) -> None:
                while download_thread.is_alive():
                    time.sleep(0.3)
                time.sleep(0.3)
                try:
                    win.destroy()  # type: ignore[attr-defined]
                except Exception:
                    pass

            polling_thread = threading.Thread(target=_poll_download, args=(progress_win,), daemon=True)
            polling_thread.start()
            webview.start()
        except Exception:
            pass

    download_thread.join(timeout=300)

    if download_error:
        _log_update(f"Update failed while downloading ({download_error})")
        _message_box(
            f"Error al descargar la actualizacion:\n{download_error}",
            "TUTTI - Error de actualizacion",
            kind="warn",
        )
        shutil.rmtree(work_dir, ignore_errors=True)
        return False

    # Verify integrity.
    if not _verify_checksum(asset_path, download_hash or "", expected_hash):
        _message_box(
            (
                "La verificacion de integridad de la descarga fallo.\n"
                "El archivo puede estar corrupto. Intenta de nuevo mas tarde."
            ),
            "TUTTI - Error de integridad",
            kind="warn",
        )
        shutil.rmtree(work_dir, ignore_errors=True)
        return False

    try:
        auto_restart_after_update = _env_flag("TUTTI_DESKTOP_AUTORESTART_AFTER_UPDATE", "1")
        restart_hint = (
            "TUTTI se abrira automaticamente al finalizar."
            if auto_restart_after_update
            else "Al terminar, abre TUTTI manualmente."
        )
        if update_mode == "installer":
            _log_update(
                f"Installer update downloaded | tag={latest_tag} | asset={asset_name}"
            )
            return _launch_installer_and_exit(asset_path, expected_exe=current_exe)

        if str(asset_name).lower().endswith(".zip"):
            updated_exe = _extract_exe_from_zip(asset_path, work_dir)
            if not updated_exe:
                _log_update("Update failed: zip downloaded but no .exe found inside")
                _message_box("No se encontro el .exe dentro del ZIP de actualizacion.", "TUTTI", kind="warn")
                return False
        else:
            updated_exe = asset_path

        # Create backup before replacing.
        backup_path = _create_backup(current_exe)

        _log_update(
            f"Update downloaded successfully | applying update to {current_exe} from {updated_exe}"
        )
        _message_box(
            (
                "Actualizacion descargada y verificada.\n"
                "La app se cerrara para aplicar cambios.\n"
                f"{restart_hint}"
            ),
            "TUTTI - Actualizando",
            kind="info",
        )
        return _launch_updater_and_exit(current_exe=current_exe, new_exe=updated_exe, backup_exe=backup_path)
    except Exception as exc:
        _log_update(f"Update failed while applying ({exc})")
        shutil.rmtree(work_dir, ignore_errors=True)
        return False


def _check_update_background(callback: Callable[[Optional[dict], str], None]) -> None:
    """Run the update check in a background thread (non-blocking).

    Calls *callback(release_data, latest_tag)* from the worker thread when an
    update is available, or *callback(None, "")* when there is nothing to do.
    """
    def _worker() -> None:
        if not AUTO_UPDATE_ENABLED:
            callback(None, "")
            return
        if os.environ.get("TUTTI_DESKTOP_DISABLE_AUTO_UPDATE") == "1":
            callback(None, "")
            return
        if not getattr(sys, "frozen", False):
            callback(None, "")
            return

        _log_update(f"Background update check started | current_version={APP_VERSION}")
        try:
            release = _fetch_latest_release(GITHUB_REPO)
        except Exception as exc:
            _log_update(f"Background update check failed ({exc})")
            callback(None, "")
            return

        latest_tag = str(release.get("tag_name") or "").strip()
        if latest_tag and _is_newer_version(APP_VERSION, latest_tag):
            _log_update(
                f"Background update available | current_version={APP_VERSION} | latest_tag={latest_tag}"
            )
            callback(release, latest_tag)
        else:
            _log_update(
                f"Background no update | current_version={APP_VERSION} | latest_tag={latest_tag or '?'}"
            )
            callback(None, "")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


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
    _apply_desktop_osrm_defaults(os.environ)

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

    print(
        "[DesktopLauncher] OSRM effective endpoints | "
        f"base={os.environ.get('OSRM_BASE_URL', '')} "
        f"route={os.environ.get('OSRM_ROUTE_URL', os.environ.get('OSRM_URL', ''))} "
        f"table={os.environ.get('OSRM_TABLE_URL', '')}",
        flush=True,
    )
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


def _kill_stale_backend_on_port(port: int = 8000) -> None:
    """Kill any leftover process holding the backend port from a previous session."""
    if os.name != "nt":
        return
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        bind_tokens = (
            f"127.0.0.1:{port}",
            f"0.0.0.0:{port}",
            f"[::1]:{port}",
            f"[::]:{port}",
        )
        pids_to_kill: set[int] = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            local_addr = parts[1]
            if not any(token in local_addr for token in bind_tokens):
                continue
            try:
                pid = int(parts[-1])
            except Exception:
                continue
            if pid > 0 and pid != os.getpid():
                pids_to_kill.add(pid)

        for pid in sorted(pids_to_kill):
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
            )
            time.sleep(0.4)
    except Exception:
        pass


class DesktopRuntime:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.backend_dir = runtime_root / "backend"
        self.frontend_dist = runtime_root / "frontend" / "dist"
        self.venv_python = runtime_root / ".venv" / "Scripts" / "python.exe"
        self.backend_proc: Optional[subprocess.Popen] = None
        self.log_handle = None

    def _close_log_handle(self) -> None:
        if not self.log_handle:
            return
        try:
            self.log_handle.write("===== TUTTI DESKTOP BACKEND STOP =====\n")
            self.log_handle.flush()
            self.log_handle.close()
        except Exception:
            pass
        finally:
            self.log_handle = None

    def _python_cmd(self) -> str:
        if self.venv_python.exists():
            return str(self.venv_python)
        return sys.executable

    def start_backend(self) -> None:
        if self.backend_proc and self.backend_proc.poll() is None:
            return
        if self.backend_proc and self.backend_proc.poll() is not None:
            self.backend_proc = None
            self._close_log_handle()

        # Kill stale backend from a previous crashed session.
        _kill_stale_backend_on_port(8000)

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
        _apply_desktop_osrm_defaults(env)

        # OSRM cache persistence in AppData (survives between sessions).
        osrm_cache_path = data_dir / "osrm_cache.json"
        env["OSRM_CACHE_FILE"] = str(osrm_cache_path)
        env["OSRM_CACHE_ENABLED"] = "true"

        # Desktop-optimized pipeline: reduce iterations, relax timeout.
        env.setdefault("TUTTI_PIPELINE_MAX_ITERATIONS", "1")
        env.setdefault("TUTTI_PIPELINE_MAX_DURATION_SEC", "180")

        # Faster OSRM failure recovery for desktop.
        env.setdefault("OSRM_TIMEOUT", "8")
        env.setdefault("OSRM_MAX_RETRIES", "1")
        env.setdefault("OSRM_RETRY_DELAY", "0.3")

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
        self.log_handle.write(
            "[DesktopLauncher] OSRM effective endpoints | "
            f"base={env.get('OSRM_BASE_URL', '')} "
            f"route={env.get('OSRM_ROUTE_URL', env.get('OSRM_URL', ''))} "
            f"table={env.get('OSRM_TABLE_URL', '')}\n"
        )
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
            self._close_log_handle()
            return
        if self.backend_proc.poll() is not None:
            self.backend_proc = None
            self._close_log_handle()
            return
        try:
            self.backend_proc.terminate()
            self.backend_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.backend_proc.kill()
        except OSError:
            pass
        finally:
            self.backend_proc = None
            self._close_log_handle()


class DesktopBridge:
    """Functions exposed to the desktop frontend through pywebview."""

    def __init__(self) -> None:
        self._window: Optional[object] = None

    def bind_window(self, window: object) -> None:
        self._window = window

    def save_pdf_file(self, pdf_base64: str, suggested_filename: str = "tutti_schedule.pdf") -> dict:
        """
        Open a native Save dialog and write the PDF bytes to the selected path.
        Called from frontend via `window.pywebview.api.save_pdf_file(...)`.
        """
        if not self._window:
            return {"success": False, "error": "Desktop window not ready"}
        if not pdf_base64:
            return {"success": False, "error": "Empty PDF payload"}

        try:
            filename = os.path.basename((suggested_filename or "tutti_schedule.pdf").strip()) or "tutti_schedule.pdf"
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"

            selected = self._window.create_file_dialog(
                webview.SAVE_DIALOG,  # type: ignore[attr-defined]
                save_filename=filename,
                file_types=("PDF files (*.pdf)", "All files (*.*)"),
            )
            if not selected:
                return {"success": False, "cancelled": True}

            target = selected[0] if isinstance(selected, (list, tuple)) else selected
            target_path = Path(str(target))
            if target_path.suffix.lower() != ".pdf":
                target_path = target_path.with_suffix(".pdf")

            data = base64.b64decode(pdf_base64)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)
            return {"success": True, "path": str(target_path)}
        except Exception as exc:
            _log_update(f"save_pdf_file failed ({exc})")
            return {"success": False, "error": str(exc)}


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--run-backend":
        return _run_backend_process_mode()

    # Check for updates in the foreground only when TUTTI_DESKTOP_UPDATE_BLOCKING=1,
    # otherwise the check runs in background while the app boots.
    blocking_update = _env_flag("TUTTI_DESKTOP_UPDATE_BLOCKING", "0")
    skip_update_boot = _env_flag("TUTTI_AFTER_UPDATE", "0") or _env_flag(
        "TUTTI_DESKTOP_DISABLE_AUTO_UPDATE", "0"
    )
    _pending_update: dict = {}
    _background_update_done = threading.Event()

    if skip_update_boot:
        _log_update("Skipping update checks on post-update startup")
        _background_update_done.set()
    elif blocking_update:
        if _check_and_apply_update_if_available():
            return 0
    else:
        # Non-blocking: fire the check and notify later if an update is found.
        def _on_update_result(release: Optional[dict], tag: str) -> None:
            if release and tag:
                _pending_update["release"] = release
                _pending_update["tag"] = tag
            _background_update_done.set()

        _check_update_background(_on_update_result)

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

    # Update prompt gate:
    # - If background check already found update -> prompt now.
    # - If background check is still running (race) -> run foreground check
    #   once to avoid missing available updates.
    if not blocking_update:
        wait_timeout_raw = os.environ.get("TUTTI_DESKTOP_BG_UPDATE_WAIT_SEC", "4")
        try:
            wait_timeout = max(0.0, min(15.0, float(wait_timeout_raw)))
        except Exception:
            wait_timeout = 4.0

        background_finished = _background_update_done.wait(timeout=wait_timeout)
        should_check_foreground = bool(_pending_update.get("release")) or (not background_finished)

        if not background_finished:
            _log_update(
                "Background update check did not finish before startup gate; "
                "running foreground update check"
            )

        if should_check_foreground and _check_and_apply_update_if_available():
            runtime.stop_backend()
            return 0

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

    desktop_bridge = DesktopBridge()
    window = webview.create_window(
        "TUTTI Fleet Control Center",
        APP_URL,
        js_api=desktop_bridge,
        **window_options,
    )
    desktop_bridge.bind_window(window)
    window.events.closed += _safe_shutdown
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
