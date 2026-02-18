"""
Tutti API - FastAPI backend for bus route optimization.

This module provides REST API endpoints for:
- Uploading route Excel files
- Optimizing bus schedules using various algorithms (V2-V6)
- Exporting schedules as PDF
- Async job management with real-time progress via WebSocket
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional, Union, Tuple
from pydantic import BaseModel
import shutil
import os
import tempfile
import logging
import io
import json
import importlib.util
import asyncio
import re
import traceback
import sys

from parser import parse_routes, parse_routes_with_report, aggregate_parse_reports
from models import Route, Bus, BusSchedule

# Config import
try:
    from config import config
    CELERY_ENABLED = config.CELERY_ENABLED and config.is_celery_available()
except ImportError:
    config = None
    CELERY_ENABLED = os.getenv("CELERY_ENABLED", "true").lower() == "true"

# Celery imports (optional)
try:
    from celery_app import celery_app
    from tasks import optimize_task, optimize_pipeline_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    celery_app = None
    optimize_task = None
    optimize_pipeline_task = None

# WebSocket imports
WEBSOCKET_AVAILABLE = False
manager = None
_websocket_import_error: Optional[str] = None

def _fallback_status_message(job_id: str, status: str, message: Optional[str] = None) -> Dict[str, Any]:
    return {"type": "status", "job_id": job_id, "status": status, "message": message or status}

def _fallback_progress_message(job_id: str, phase: str, progress: int, message: str, extra: Optional[dict] = None) -> Dict[str, Any]:
    payload = {"type": "progress", "job_id": job_id, "phase": phase, "progress": progress, "message": message}
    if extra:
        payload.update(extra)
    return payload

def _fallback_completed_message(job_id: str, result: Dict[str, Any], stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"type": "completed", "job_id": job_id, "result": result, "stats": stats}

def _fallback_error_message(job_id: str, error_code: str, message: str) -> Dict[str, Any]:
    return {"type": "error", "job_id": job_id, "error_code": error_code, "message": message}

def _fallback_pong_message() -> Dict[str, Any]:
    return {"type": "pong"}

build_status_message = _fallback_status_message
build_progress_message = _fallback_progress_message
build_completed_message = _fallback_completed_message
build_error_message = _fallback_error_message
build_pong_message = _fallback_pong_message


def _candidate_backend_roots() -> List[str]:
    """Return backend root candidates for source and frozen runtimes."""
    base_dir = os.path.dirname(__file__)
    candidates: List[str] = [
        base_dir,
        os.path.join(base_dir, "backend"),
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend(
            [
                meipass,
                os.path.join(meipass, "backend"),
            ]
        )
    # Preserve order and remove duplicates
    unique: List[str] = []
    for candidate in candidates:
        resolved = os.path.abspath(candidate)
        if resolved not in unique:
            unique.append(resolved)
    return unique


def _resolve_backend_file(*parts: str) -> Optional[str]:
    """Resolve a backend file path across source and PyInstaller layouts."""
    for root in _candidate_backend_roots():
        path = os.path.join(root, *parts)
        if os.path.exists(path):
            return path
    return None


try:
    websocket_module_path = _resolve_backend_file("websocket.py")
    if not websocket_module_path:
        raise ImportError("websocket.py not found in runtime backend paths")
    ws_spec = importlib.util.spec_from_file_location("tutti_ws_core", websocket_module_path)
    if ws_spec is None or ws_spec.loader is None:
        raise ImportError(f"Could not load spec from {websocket_module_path}")
    ws_module = importlib.util.module_from_spec(ws_spec)
    ws_spec.loader.exec_module(ws_module)

    manager = getattr(ws_module, "manager")
    build_status_message = getattr(ws_module, "build_status_message")
    build_progress_message = getattr(ws_module, "build_progress_message")
    build_completed_message = getattr(ws_module, "build_completed_message")
    build_error_message = getattr(ws_module, "build_error_message")
    build_pong_message = getattr(ws_module, "build_pong_message")
    WEBSOCKET_AVAILABLE = True
except Exception as e:
    _websocket_import_error = str(e)
    try:
        from backend.websocket import (
            manager,
            build_status_message,
            build_progress_message,
            build_completed_message,
            build_error_message,
            build_pong_message,
        )
        WEBSOCKET_AVAILABLE = True
    except Exception as inner:
        _websocket_import_error = f"{_websocket_import_error}; fallback import failed: {inner}"
        WEBSOCKET_AVAILABLE = False
        manager = None

# Monte Carlo validation jobs cache (debe estar antes del import)
validation_jobs: Dict[str, Any] = {}

# Monte Carlo WebSocket imports
try:
    from websocket_monte_carlo import handle_monte_carlo_websocket, MONTE_CARLO_AVAILABLE, set_validation_jobs_cache
    MONTE_CARLO_WS_AVAILABLE = True
    # Connect validation jobs cache to WebSocket handler
    set_validation_jobs_cache(validation_jobs)
except ImportError:
    MONTE_CARLO_WS_AVAILABLE = False

# Progress listener
try:
    from progress_listener import start_progress_listener, is_listener_running
    PROGRESS_LISTENER_AVAILABLE = True
except ImportError:
    PROGRESS_LISTENER_AVAILABLE = False

# Database imports
from db.database import SessionLocal, is_database_available, create_tables
from db.models import OptimizationJob
from datetime import datetime, timedelta
from uuid import uuid4
try:
    from services.job_runtime_store import runtime_job_store, TERMINAL_STATUSES
except ImportError:
    from backend.services.job_runtime_store import runtime_job_store, TERMINAL_STATUSES

try:
    from services.fleet_assignment import assign_fleet_profiles_to_schedule
except ImportError:
    from backend.services.fleet_assignment import assign_fleet_profiles_to_schedule

logger = logging.getLogger(__name__)
LOCAL_PIPELINE_TASKS: Dict[str, asyncio.Task] = {}
_LAST_RUNTIME_SNAPSHOT_PERSISTED_AT: Dict[str, datetime] = {}

if not WEBSOCKET_AVAILABLE and _websocket_import_error:
    logger.warning(f"[Import] Core WebSocket module not available: {_websocket_import_error}")


def _format_exception_message(exc: Exception) -> str:
    exc_type = type(exc).__name__
    exc_text = str(exc).strip()
    if exc_text:
        return f"{exc_type}: {exc_text}"
    return exc_type


def _apply_fleet_profiles(schedule: List[BusSchedule]) -> Tuple[List[BusSchedule], Dict[str, Any]]:
    """Attach real fleet profile metadata to optimized schedules."""
    try:
        assigned_schedule, summary = assign_fleet_profiles_to_schedule(schedule)
        return assigned_schedule, summary
    except Exception as e:
        logger.warning(f"[FleetAssignment] Could not assign fleet profiles: {e}")
        return schedule, {
            "fleet_available": 0,
            "fleet_assigned": 0,
            "virtual_buses": len(schedule),
            "unmatched_bus_ids": [bus.bus_id for bus in schedule],
        }


def _persist_job_update(
    job_id: str,
    *,
    status: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    stats: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """Persist optimistic job updates when DB is available."""
    if not is_database_available():
        return

    db = SessionLocal()
    try:
        job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
        if not job:
            return
        if status is not None:
            job.status = status
        if result is not None:
            job.result = result
        if stats is not None:
            job.stats = stats
        if error_message is not None:
            job.error_message = error_message
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        db.commit()
    except Exception as e:
        logger.warning(f"[Pipeline] Could not persist job update for {job_id}: {e}")
    finally:
        db.close()


def _persist_runtime_snapshot(job_id: str, force: bool = False, throttle_seconds: float = 1.0) -> None:
    """Persist runtime snapshot in OptimizationJob.stats.runtime_snapshot."""
    if not is_database_available():
        return

    snapshot = runtime_job_store.get_snapshot(job_id)
    if not snapshot:
        return

    now = datetime.utcnow()
    last_persisted = _LAST_RUNTIME_SNAPSHOT_PERSISTED_AT.get(job_id)
    if not force and last_persisted and (now - last_persisted).total_seconds() < float(throttle_seconds):
        return

    db = SessionLocal()
    try:
        job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
        if not job:
            return
        stats_obj = dict(job.stats or {})
        stats_obj["runtime_snapshot"] = runtime_job_store.serialize_status(snapshot)
        job.stats = stats_obj
        db.commit()
        _LAST_RUNTIME_SNAPSHOT_PERSISTED_AT[job_id] = now
    except Exception as e:
        logger.debug(f"[RuntimeSnapshot] Could not persist runtime snapshot for {job_id}: {e}")
    finally:
        db.close()


def _update_local_job_state(job_id: str, **updates: Any) -> Dict[str, Any]:
    """Compatibility wrapper to update unified runtime snapshots."""
    status = str(updates.get("status", "running"))
    stage = str(updates.get("stage") or updates.get("phase") or status)
    phase = str(updates.get("phase") or stage)
    message = str(updates.get("message") or status)
    progress = int(updates.get("progress", 0) or 0)
    execution_mode = str(updates.get("execution_mode") or "local")
    persisted = bool(updates.get("persisted", False))
    algorithm = updates.get("algorithm")
    created_at = updates.get("created_at")
    if not runtime_job_store.get_snapshot(job_id):
        snapshot = runtime_job_store.create_job(
            job_id=job_id,
            mode=execution_mode,
            persisted_db=persisted,
            algorithm=algorithm,
            status=status,
            message=message,
        )
        if created_at is not None:
            snapshot = runtime_job_store.update_from_db_row(
                job_id,
                created_at=created_at,
                status=status,
                execution_mode=execution_mode,
                algorithm=algorithm,
            )
    if status == "completed":
        return runtime_job_store.mark_completed(
            job_id=job_id,
            result=updates.get("result") or {},
            stats=updates.get("stats"),
            execution_mode=execution_mode,
        )
    if status in {"failed", "error"}:
        return runtime_job_store.mark_failed(
            job_id=job_id,
            error_code=str(updates.get("error_code") or "PIPELINE_FAILED"),
            message=str(updates.get("error") or updates.get("error_message") or message),
            stage=stage,
            execution_mode=execution_mode,
            terminal_reason=str(updates.get("terminal_reason") or "failed"),
        )
    if status == "cancelled":
        return runtime_job_store.mark_cancelled(job_id=job_id, message=message)
    if status == "lost":
        return runtime_job_store.mark_lost(job_id=job_id, message=message)

    extra = dict(updates)
    extra["phase"] = phase
    extra["status"] = status
    extra["execution_mode"] = execution_mode
    return runtime_job_store.update_progress(
        job_id=job_id,
        stage=stage,
        progress=progress,
        message=message,
        extra=extra,
    )


def _get_local_job_state(job_id: str) -> Optional[Dict[str, Any]]:
    return runtime_job_store.get_snapshot(job_id)


def _cleanup_old_local_jobs() -> None:
    expired_ids = runtime_job_store.cleanup()
    for cached_job_id in expired_ids:
        LOCAL_PIPELINE_TASKS.pop(cached_job_id, None)


def _format_job_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_local_job_status(job: Dict[str, Any]) -> Dict[str, Any]:
    return runtime_job_store.serialize_status(job)


def _serialize_local_job_result(job: Dict[str, Any]) -> Dict[str, Any]:
    return runtime_job_store.serialize_result(job)


async def _emit_ws_message(job_id: str, message: Dict[str, Any]) -> None:
    """Emit a websocket message for a job if websocket manager is available."""
    if not WEBSOCKET_AVAILABLE or not manager:
        return
    try:
        await manager.send_progress(job_id, message)
    except Exception as e:
        logger.debug(f"[Pipeline] Failed WS emit for job {job_id}: {e}")


async def _run_local_pipeline_job(
    job_id: str,
    routes_data: List[Dict[str, Any]],
    config_payload: Dict[str, Any],
) -> None:
    """
    Execute pipeline in-process when Celery is not available.
    This preserves async behavior for the frontend (queued + WS progress).
    """
    current_stage: Dict[str, str] = {"stage": "starting"}

    try:
        try:
            from services.optimization_pipeline_service import (
                PipelineConfig,
                run_optimization_pipeline_by_day,
            )
        except ImportError:
            from backend.services.optimization_pipeline_service import (
                PipelineConfig,
                run_optimization_pipeline_by_day,
            )

        started_at = datetime.utcnow()
        _update_local_job_state(
            job_id,
            status="running",
            started_at=started_at,
            stage="starting",
            progress=1,
            message="Pipeline automático en ejecución",
            error=None,
        )
        _persist_job_update(job_id, status="running", started_at=started_at)
        await _emit_ws_message(
            job_id,
            build_status_message(job_id, "running", "Pipeline automático en ejecución"),
        )

        routes = [Route(**route_data) for route_data in routes_data]
        config_obj = PipelineConfig.from_dict(config_payload)

        def progress_callback(
            phase: str,
            progress: int,
            message: str,
            extra: Optional[Dict[str, Any]] = None,
        ) -> None:
            extra_data = extra or {}
            stage = extra_data.get("stage", phase)
            current_stage["stage"] = str(stage)
            _update_local_job_state(
                job_id,
                status="running",
                stage=stage,
                phase=phase,
                progress=int(progress),
                message=message,
                day=extra_data.get("day"),
                iteration=extra_data.get("iteration"),
                metrics=extra_data.get("metrics"),
            )
            payload_extra: Dict[str, Any] = {
                "stage": stage,
                "day": extra_data.get("day"),
                "iteration": extra_data.get("iteration"),
                "metrics": extra_data.get("metrics"),
            }
            for key, value in extra_data.items():
                if key in {"phase", "progress", "message", "job_id", "timestamp"}:
                    continue
                payload_extra[key] = value
            payload = build_progress_message(
                job_id=job_id,
                phase=phase,
                progress=progress,
                message=message,
                extra=payload_extra,
            )
            if WEBSOCKET_AVAILABLE and manager:
                asyncio.create_task(manager.send_progress(job_id, payload))

        pipeline_result = await run_optimization_pipeline_by_day(
            routes=routes,
            config=config_obj,
            progress_callback=progress_callback,
        )

        _persist_job_update(
            job_id,
            status="completed",
            result=pipeline_result,
            stats=pipeline_result.get("summary_metrics"),
            completed_at=datetime.utcnow(),
        )
        _update_local_job_state(
            job_id,
            status="completed",
            phase="completed",
            stage="completed",
            progress=100,
            message="Pipeline completado",
            result=pipeline_result,
            stats=pipeline_result.get("summary_metrics"),
            completed_at=datetime.utcnow(),
        )
        await _emit_ws_message(
            job_id,
            build_completed_message(job_id, pipeline_result, pipeline_result.get("summary_metrics")),
        )
    except asyncio.CancelledError:
        _persist_job_update(job_id, status="cancelled", completed_at=datetime.utcnow())
        _update_local_job_state(
            job_id,
            status="cancelled",
            stage=current_stage.get("stage", "cancelled"),
            progress=100,
            message="Job cancelado por el usuario",
            completed_at=datetime.utcnow(),
        )
        await _emit_ws_message(
            job_id,
            build_status_message(job_id, "cancelled", "Job cancelado por el usuario"),
        )
        raise
    except Exception as e:
        error_message = _format_exception_message(e)
        stage = current_stage.get("stage", "unknown")
        logger.error(f"[Pipeline] Local async job failed at stage {stage}: {error_message}")
        logger.debug("[Pipeline] Local async traceback:\n%s", traceback.format_exc())
        _persist_job_update(
            job_id,
            status="failed",
            error_message=f"{stage}: {error_message}",
            completed_at=datetime.utcnow(),
        )
        _update_local_job_state(
            job_id,
            status="failed",
            stage=stage,
            progress=100,
            message=error_message,
            error=f"{stage}: {error_message}",
            completed_at=datetime.utcnow(),
        )
        await _emit_ws_message(
            job_id,
            build_error_message(job_id, "PIPELINE_FAILED", error_message),
        )
    finally:
        LOCAL_PIPELINE_TASKS.pop(job_id, None)


def _has_active_celery_workers(timeout: float = 0.8) -> bool:
    """Return True when Celery is enabled and at least one worker responds."""
    if not CELERY_ENABLED or not celery_app:
        return False
    try:
        result = celery_app.control.ping(timeout=timeout)
        return bool(result)
    except Exception:
        return False


def _load_ws_handler(module_filename: str, handler_name: str):
    """
    Load websocket handler directly from backend/websocket/*.py.

    Avoids import ambiguity between:
    - backend/websocket.py (module)
    - backend/websocket/ (package)
    """
    module_path = _resolve_backend_file("websocket", module_filename)
    if not module_path:
        searched = ", ".join(_candidate_backend_roots())
        raise ImportError(f"WS module not found: {module_filename} (searched: {searched})")

    module_key = f"tutti_ws_{module_filename.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_key, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not build import spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    handler = getattr(module, handler_name, None)
    if handler is None:
        raise ImportError(f"Handler {handler_name} not found in {module_path}")
    return handler

# =============================================================================
# MONTE CARLO VALIDATION JOBS CACHE
# =============================================================================

def _cleanup_old_validation_jobs():
    """Remove validation jobs older than 1 hour."""
    now = datetime.utcnow()
    expired = [
        job_id for job_id, job in validation_jobs.items()
        if now - job.get("created_at", now) > timedelta(hours=1)
    ]
    for job_id in expired:
        del validation_jobs[job_id]
        logger.info(f"[Validation Cache] Removed expired job {job_id}")

CELERY_ENABLED = CELERY_ENABLED and CELERY_AVAILABLE

app = FastAPI(
    title="Tutti API",
    description="Bus route optimization API",
    version="1.0.0"
)


def _resolve_frontend_dist_dir() -> Optional[str]:
    """Resolve frontend dist directory for desktop mode static hosting."""
    candidates = [
        os.getenv("FRONTEND_DIST_DIR", "").strip(),
        os.path.join(os.path.dirname(__file__), "frontend_dist"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = os.path.abspath(candidate)
        if os.path.isdir(resolved) and os.path.isfile(os.path.join(resolved, "index.html")):
            return resolved
    return None


FRONTEND_DIST_DIR = _resolve_frontend_dist_dir()
SERVE_FRONTEND_DIST = os.getenv("SERVE_FRONTEND_DIST", "false").lower() in ("true", "1", "yes", "on")

# Import and register validation router
try:
    from api.validation import router as validation_router
    app.include_router(validation_router)
    logger.info("[Startup] Validation router registered successfully")
except ImportError as e:
    logger.warning(f"[Startup] Could not register validation router: {e}")

# Import and register route editor router
try:
    from api.routes_editor import router as routes_editor_router
    app.include_router(routes_editor_router)
    logger.info("[Startup] Route editor router registered successfully")
except ImportError as e:
    logger.warning(f"[Startup] Could not register route editor router: {e}")

# Import and register fleet router
try:
    from api.fleet import router as fleet_router
    app.include_router(fleet_router)
    logger.info("[Startup] Fleet router registered successfully")
except ImportError as e:
    logger.warning(f"[Startup] Could not register fleet router: {e}")

# Enable CORS
def _wildcard_origin_to_regex(origin_pattern: str) -> str:
    """Convert wildcard origins (e.g. https://*.vercel.app) to regex."""
    escaped = re.escape(origin_pattern.strip())
    return "^" + escaped.replace(r"\*", ".*") + "$"


default_origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # React dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
configured_origins = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
explicit_extra_origins = [origin for origin in configured_origins if "*" not in origin]
wildcard_origins = [origin for origin in configured_origins if "*" in origin]

# Helpful default for Vercel previews in beta/production.
if os.getenv("CORS_ALLOW_VERCEL_PREVIEWS", "true").lower() == "true":
    wildcard_origins.append("https://*.vercel.app")

allowed_origins = list(dict.fromkeys(default_origins + explicit_extra_origins))

origin_regex_parts: List[str] = []
raw_origin_regex = os.getenv("CORS_ORIGIN_REGEX", "").strip()
if raw_origin_regex:
    origin_regex_parts.append(raw_origin_regex)

origin_regex_parts.extend(_wildcard_origin_to_regex(origin) for origin in wildcard_origins)
allow_origin_regex = "|".join(dict.fromkeys(origin_regex_parts)) if origin_regex_parts else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> Any:
    """Root endpoint returning welcome message."""
    if SERVE_FRONTEND_DIST and FRONTEND_DIST_DIR:
        index_file = os.path.join(FRONTEND_DIST_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
    return {"message": "Welcome to Tutti API"}


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Health check endpoint with service status."""
    services = {
        "database": "disabled" if not is_database_available() else "ok",
        "celery": "disabled" if not CELERY_ENABLED else "unknown"
    }
    
    # Check Celery if enabled
    if CELERY_ENABLED:
        services["celery"] = "ok" if _has_active_celery_workers(timeout=1.0) else "no_workers"

    runtime_mode = "stable"
    if config and getattr(config, "APP_RUNTIME_MODE", None):
        runtime_mode = str(config.APP_RUNTIME_MODE)

    ws_stats = {
        "active_jobs": 0,
        "active_connections": 0,
    }
    if WEBSOCKET_AVAILABLE and manager:
        try:
            ws_stats["active_jobs"] = len(manager.get_active_jobs())
            ws_stats["active_connections"] = int(manager.get_connection_count())
        except Exception:
            pass

    return {
        "status": "ok",
        "service": "tutti-backend",
        "services": services,
        "mode": runtime_mode,
        "ws_manager": ws_stats,
        "job_store": runtime_job_store.stats(),
    }


@app.post("/upload", response_model=List[Route])
async def upload_files(files: List[UploadFile] = File(...)) -> List[Route]:
    """
    Upload Excel files containing route data.
    
    Args:
        files: List of Excel files to parse
        
    Returns:
        List of parsed Route objects with complete stop data
    """
    all_routes: List[Route] = []
    temp_files: List[str] = []

    try:
        for file in files:
            suffix = os.path.splitext(file.filename)[1] if file.filename else '.xlsx'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
                temp_files.append(tmp_path)

            routes = parse_routes(tmp_path)
            all_routes.extend(routes)

        if not all_routes:
            raise HTTPException(status_code=400, detail="No routes found or error parsing files")

        # Store routes in cache for GET /api/routes/{id} endpoint
        try:
            from api.routes_editor import update_routes_cache
            from datetime import datetime
            
            for route in all_routes:
                route_dict = route.dict()
                route_dict["created_at"] = datetime.utcnow()
                update_routes_cache(route.id, route_dict)
            logger.info(f"[Upload] Stored {len(all_routes)} routes in cache")
        except ImportError as e:
            logger.warning(f"[Upload] Could not cache routes: {e}")

        return all_routes
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Could not delete temp file {temp_path}: {e}")


@app.post("/upload/analyze")
async def upload_files_with_analysis(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """
    Upload Excel files and return parsed routes plus data-quality report.

    Response:
    {
      "routes": Route[],
      "parse_report": ParseReport
    }
    """
    all_routes: List[Route] = []
    parse_reports: List[Dict[str, Any]] = []
    temp_files: List[str] = []

    try:
        for file in files:
            suffix = os.path.splitext(file.filename)[1] if file.filename else ".xlsx"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                tmp_path = tmp.name
                temp_files.append(tmp_path)

            routes, parse_report = parse_routes_with_report(tmp_path)
            if file.filename:
                parse_report["file_name"] = file.filename

            all_routes.extend(routes)
            parse_reports.append(parse_report)

        if not all_routes:
            aggregated = aggregate_parse_reports(parse_reports)
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "No routes found or error parsing files",
                    "parse_report": aggregated,
                },
            )

        aggregated_report = aggregate_parse_reports(parse_reports)

        # Store routes in cache for GET /api/routes/{id} endpoint
        try:
            from api.routes_editor import update_routes_cache
            from datetime import datetime

            for route in all_routes:
                route_dict = route.dict()
                route_dict["created_at"] = datetime.utcnow()
                update_routes_cache(route.id, route_dict)
            logger.info(f"[UploadAnalyze] Stored {len(all_routes)} routes in cache")
        except ImportError as e:
            logger.warning(f"[UploadAnalyze] Could not cache routes: {e}")

        return {
            "routes": all_routes,
            "parse_report": aggregated_report,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload/analyze: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Could not delete temp file {temp_path}: {e}")


@app.post("/optimize-lp")
async def optimize_lp(routes: List[Route]) -> List[Dict[str, Any]]:
    """
    Simple optimization without progress tracking (V2).
    
    Args:
        routes: List of Route objects to optimize
        
    Returns:
        List of schedule dictionaries
    """
    try:
        from optimizer_v2 import optimize_routes_v2
        
        logger.info(f"Starting optimization with {len(routes)} routes")
        schedule = optimize_routes_v2(routes)
        logger.info(f"Optimization complete: {len(schedule)} buses")
        
        return [s.dict() for s in schedule]
        
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize-v4")
async def optimize_v4_endpoint(routes: List[Route]) -> Dict[str, Any]:
    """
    Optimizacion V4: Agrupacion por cercania geografica + early arrival.
    
    Args:
        routes: List of Route objects to optimize
        
    Returns:
        Dictionary with schedule and statistics
    """
    try:
        from optimizer_v4 import optimize_v4
        
        logger.info(f"[V4] Starting optimization with {len(routes)} routes")
        
        # Ejecutar optimizacion
        schedule = optimize_v4(routes)
        
        # Calcular estadisticas
        total_routes = sum(len(b.items) for b in schedule)
        buses_with_4_entries = sum(1 for b in schedule 
                                   if sum(1 for i in b.items if i.type == "entry") == 4)
        buses_with_3_plus_exits = sum(1 for b in schedule 
                                      if sum(1 for i in b.items if i.type == "exit") >= 3)
        buses_with_7_total = sum(1 for b in schedule if len(b.items) >= 7)
        
        logger.info(f"[V4] Complete: {len(schedule)} buses, {total_routes} routes")
        logger.info(f"[V4] Buses 4+3: {buses_with_7_total}, 4 entries: {buses_with_4_entries}")
        
        return {
            "schedule": [s.dict() for s in schedule],
            "stats": {
                "total_buses": len(schedule),
                "total_routes": total_routes,
                "buses_with_4_entries": buses_with_4_entries,
                "buses_with_3_plus_exits": buses_with_3_plus_exits,
                "buses_with_7_routes": buses_with_7_total
            }
        }
        
    except Exception as e:
        logger.error(f"[V4] Optimization error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize")
async def optimize_v5_endpoint(routes: List[Route]) -> Dict[str, Any]:
    """
    Tutti Optimizer V5: OSRM-based chain optimization.
    Morning: shift early to maximize chains.
    Afternoon: fixed departure, chain exits.
    Merge morning+afternoon to minimize fleet.
    
    Args:
        routes: List of Route objects to optimize
        
    Returns:
        Dictionary with schedule and statistics
    """
    try:
        from optimizer_v5 import optimize_v5

        logger.info(f"[V5] Starting optimization with {len(routes)} routes")
        schedule = optimize_v5(routes)
        schedule, fleet_assignment = _apply_fleet_profiles(schedule)

        # Compute stats
        total_routes = sum(len(b.items) for b in schedule)
        entry_counts = [sum(1 for i in b.items if i.type == "entry") for b in schedule]
        exit_counts = [sum(1 for i in b.items if i.type == "exit") for b in schedule]
        max_entries = max(entry_counts) if entry_counts else 0
        max_exits = max(exit_counts) if exit_counts else 0
        buses_with_morning_and_afternoon = sum(1 for i, e in enumerate(entry_counts) if e > 0 and exit_counts[i] > 0)
        total_early_shift = sum(
            item.time_shift_minutes for b in schedule for item in b.items
            if item.time_shift_minutes > 0
        )

        logger.info(f"[V5] Complete: {len(schedule)} buses, {total_routes} routes")

        return {
            "schedule": [s.dict() for s in schedule],
            "stats": {
                "total_buses": len(schedule),
                "total_routes": total_routes,
                "total_entries": sum(entry_counts),
                "total_exits": sum(exit_counts),
                "max_entries_per_bus": max_entries,
                "max_exits_per_bus": max_exits,
                "buses_with_both": buses_with_morning_and_afternoon,
                "avg_routes_per_bus": round(total_routes / len(schedule), 1) if schedule else 0,
                "total_early_shift_minutes": total_early_shift,
            },
            "fleet_assignment": fleet_assignment,
        }

    except Exception as e:
        logger.error(f"[V5] Optimization error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize-v6")
async def optimize_v6_endpoint(
    routes: List[Route],
    use_ml_assignment: bool = Query(
        default=True,
        description="Activa scoring ML para encadenado de rutas",
    ),
) -> Dict[str, Any]:
    """
    Tutti Optimizer V6: ILP-based optimization + local search.
    Uses PuLP for optimal chain building and cross-block matching.
    
    Args:
        routes: List of Route objects to optimize
        
    Returns:
        Dictionary with schedule and statistics
    """
    try:
        from optimizer_v6 import optimize_v6

        logger.info(
            f"[V6] Starting optimization with {len(routes)} routes "
            f"(ml_assignment={use_ml_assignment})"
        )
        schedule = optimize_v6(routes, use_ml_assignment=use_ml_assignment)
        schedule, fleet_assignment = _apply_fleet_profiles(schedule)

        total_routes = sum(len(b.items) for b in schedule)
        entry_counts = [sum(1 for i in b.items if i.type == "entry") for b in schedule]
        exit_counts = [sum(1 for i in b.items if i.type == "exit") for b in schedule]
        max_entries = max(entry_counts) if entry_counts else 0
        max_exits = max(exit_counts) if exit_counts else 0
        buses_with_morning_and_afternoon = sum(1 for i, e in enumerate(entry_counts) if e > 0 and exit_counts[i] > 0)
        total_early_shift = sum(
            item.time_shift_minutes for b in schedule for item in b.items
            if item.time_shift_minutes > 0
        )

        logger.info(f"[V6] Complete: {len(schedule)} buses, {total_routes} routes")

        return {
            "schedule": [s.dict() for s in schedule],
            "stats": {
                "total_buses": len(schedule),
                "total_routes": total_routes,
                "total_entries": sum(entry_counts),
                "total_exits": sum(exit_counts),
                "max_entries_per_bus": max_entries,
                "max_exits_per_bus": max_exits,
                "buses_with_both": buses_with_morning_and_afternoon,
                "avg_routes_per_bus": round(total_routes / len(schedule), 1) if schedule else 0,
                "total_early_shift_minutes": total_early_shift,
            },
            "optimization_options": {
                "use_ml_assignment": bool(use_ml_assignment),
            },
            "fleet_assignment": fleet_assignment,
        }

    except Exception as e:
        logger.error(f"[V6] Optimization error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize-v6-ab")
async def optimize_v6_ab_endpoint(
    routes: List[Route],
    include_schedules: bool = Query(
        default=False,
        description="Incluye schedules completos para ambos modos (payload grande)",
    ),
) -> Dict[str, Any]:
    """
    Ejecuta comparación A/B entre V6 con ML OFF y ML ON.
    """
    try:
        from optimizer_v6 import optimize_v6

        logger.info(f"[V6-AB] Running A/B optimization with {len(routes)} routes")

        schedule_ml_off = optimize_v6(routes, use_ml_assignment=False)
        schedule_ml_off, fleet_assignment_ml_off = _apply_fleet_profiles(schedule_ml_off)
        stats_ml_off = _calculate_stats(schedule_ml_off)

        schedule_ml_on = optimize_v6(routes, use_ml_assignment=True)
        schedule_ml_on, fleet_assignment_ml_on = _apply_fleet_profiles(schedule_ml_on)
        stats_ml_on = _calculate_stats(schedule_ml_on)

        deltas = {
            "total_buses": int(stats_ml_on.get("total_buses", 0)) - int(stats_ml_off.get("total_buses", 0)),
            "total_early_shift_minutes": int(stats_ml_on.get("total_early_shift_minutes", 0))
            - int(stats_ml_off.get("total_early_shift_minutes", 0)),
            "avg_routes_per_bus": round(
                float(stats_ml_on.get("avg_routes_per_bus", 0.0))
                - float(stats_ml_off.get("avg_routes_per_bus", 0.0)),
                2,
            ),
        }

        if stats_ml_on.get("total_buses", 0) < stats_ml_off.get("total_buses", 0):
            recommended_mode = "ml_on"
            reason = "reduce número de buses"
        elif stats_ml_on.get("total_buses", 0) > stats_ml_off.get("total_buses", 0):
            recommended_mode = "ml_off"
            reason = "reduce número de buses"
        elif stats_ml_on.get("total_early_shift_minutes", 0) < stats_ml_off.get("total_early_shift_minutes", 0):
            recommended_mode = "ml_on"
            reason = "reduce adelantos acumulados"
        elif stats_ml_on.get("total_early_shift_minutes", 0) > stats_ml_off.get("total_early_shift_minutes", 0):
            recommended_mode = "ml_off"
            reason = "reduce adelantos acumulados"
        else:
            recommended_mode = "tie"
            reason = "sin diferencia relevante en métricas base"

        response: Dict[str, Any] = {
            "comparison": {
                "ml_off": {
                    "optimization_options": {"use_ml_assignment": False},
                    "stats": stats_ml_off,
                    "fleet_assignment": fleet_assignment_ml_off,
                },
                "ml_on": {
                    "optimization_options": {"use_ml_assignment": True},
                    "stats": stats_ml_on,
                    "fleet_assignment": fleet_assignment_ml_on,
                },
                "deltas_ml_on_minus_ml_off": deltas,
            },
            "recommendation": {
                "mode": recommended_mode,
                "reason": reason,
            },
        }

        if include_schedules:
            response["comparison"]["ml_off"]["schedule"] = [s.dict() for s in schedule_ml_off]
            response["comparison"]["ml_on"]["schedule"] = [s.dict() for s in schedule_ml_on]

        return response

    except Exception as e:
        logger.error(f"[V6-AB] Optimization error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize-v6-advanced")
async def optimize_v6_advanced(
    routes: List[Route],
    weights: Optional[Dict[str, float]] = None,
    preset: Optional[str] = None,
    use_lns: bool = True,
    use_ml_assignment: bool = Query(
        default=True,
        description="Activa scoring ML para encadenado de rutas",
    ),
) -> Dict[str, Any]:
    """
    Tutti Optimizer V6 Advanced: Multi-objective + LNS.
    
    Permite optimizar con mÃºltiples criterios usando pesos configurables
    y opcionalmente aplicar Large Neighborhood Search para mejorar resultados.
    
    Args:
        routes: List of Route objects to optimize
        weights: Pesos personalizados para funciÃ³n objetivo (opcional)
        preset: Nombre del preset a usar (minimize_buses, minimize_cost, minimize_emissions, balanced)
        use_lns: Usar LNS para mejorar soluciÃ³n (default: True)
        
    Returns:
        Dictionary with schedule, statistics, and multi-objective metrics
    """
    try:
        from optimizer_multi import ObjectiveWeights, MultiObjectiveOptimizer
        from optimizer_lns import optimize_v6_lns

        logger.info(f"[V6-Advanced] Starting optimization with {len(routes)} routes")
        logger.info(f"[V6-Advanced] LNS enabled: {use_lns}")

        # Determinar pesos a usar
        if preset:
            from config import ObjectivePresets
            weights_dict = ObjectivePresets.get_preset(preset)
            logger.info(f"[V6-Advanced] Using preset: {preset}")
        elif weights:
            weights_dict = weights
            logger.info(f"[V6-Advanced] Using custom weights")
        else:
            weights_dict = None
            logger.info(f"[V6-Advanced] Using default weights")

        # Crear objetos de pesos
        if weights_dict:
            weights_obj = ObjectiveWeights(**weights_dict)
        else:
            weights_obj = ObjectiveWeights()

        # Ejecutar optimizaciÃ³n
        schedule = optimize_v6_lns(
            routes,
            weights=weights_obj,
            use_lns=use_lns,
            use_ml_assignment=use_ml_assignment,
        )
        schedule, fleet_assignment = _apply_fleet_profiles(schedule)

        # Calcular estadÃ­sticas estÃ¡ndar
        total_routes = sum(len(b.items) for b in schedule)
        entry_counts = [sum(1 for i in b.items if i.type == "entry") for b in schedule]
        exit_counts = [sum(1 for i in b.items if i.type == "exit") for b in schedule]
        
        # Calcular mÃ©tricas multi-objetivo
        evaluator = MultiObjectiveOptimizer(weights_obj)
        metrics = evaluator.calculate_metrics(schedule)
        score = evaluator.evaluate_schedule(schedule)

        logger.info(f"[V6-Advanced] Complete: {len(schedule)} buses, score={score:.2f}")

        return {
            "schedule": [s.dict() for s in schedule],
            "stats": {
                "total_buses": len(schedule),
                "total_routes": total_routes,
                "total_entries": sum(entry_counts),
                "total_exits": sum(exit_counts),
                "max_entries_per_bus": max(entry_counts) if entry_counts else 0,
                "max_exits_per_bus": max(exit_counts) if exit_counts else 0,
                "buses_with_both": sum(1 for i, e in enumerate(entry_counts) if e > 0 and exit_counts[i] > 0),
                "avg_routes_per_bus": round(total_routes / len(schedule), 1) if schedule else 0,
            },
            "multi_objective": {
                "score": round(score, 2),
                "metrics": metrics.to_dict(),
                "weights": weights_obj.to_dict()
            },
            "optimization_options": {
                "use_lns": bool(use_lns),
                "use_ml_assignment": bool(use_ml_assignment),
            },
            "fleet_assignment": fleet_assignment,
        }

    except Exception as e:
        logger.error(f"[V6-Advanced] Optimization error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


DAY_NAMES: Dict[str, str] = {
    "L": "Lunes", "M": "Martes", "Mc": "MiÃ©rcoles",
    "X": "Jueves", "V": "Viernes"
}
ALL_DAYS: List[str] = ["L", "M", "Mc", "X", "V"]


def _calculate_stats(schedule: List[BusSchedule]) -> Dict[str, Any]:
    """Calcular estadÃ­sticas del schedule."""
    if not schedule:
        return {
            "total_buses": 0,
            "total_routes": 0,
            "total_entries": 0,
            "total_exits": 0,
            "max_entries_per_bus": 0,
            "max_exits_per_bus": 0,
            "buses_with_both": 0,
            "avg_routes_per_bus": 0,
            "total_early_shift_minutes": 0,
        }
    
    total_routes = sum(len(bus.items) for bus in schedule)
    entry_counts = [sum(1 for i in bus.items if i.type == "entry") for bus in schedule]
    exit_counts = [sum(1 for i in bus.items if i.type == "exit") for bus in schedule]
    max_entries = max(entry_counts) if entry_counts else 0
    max_exits = max(exit_counts) if exit_counts else 0
    buses_with_both = sum(1 for i, e in enumerate(entry_counts) if e > 0 and exit_counts[i] > 0)
    total_early_shift = sum(
        item.time_shift_minutes for bus in schedule for item in bus.items
        if item.time_shift_minutes > 0
    )
    
    return {
        "total_buses": len(schedule),
        "total_routes": total_routes,
        "total_entries": sum(entry_counts),
        "total_exits": sum(exit_counts),
        "max_entries_per_bus": max_entries,
        "max_exits_per_bus": max_exits,
        "buses_with_both": buses_with_both,
        "avg_routes_per_bus": round(total_routes / len(schedule), 1) if schedule else 0,
        "total_early_shift_minutes": total_early_shift,
    }


class PipelineConfigPayload(BaseModel):
    auto_start: bool = True
    objective: str = "min_buses_viability"
    max_duration_sec: int = 300
    max_iterations: int = 2
    use_ml_assignment: bool = True
    invalid_rows_dropped: int = 0


class PipelineOptimizationRequest(BaseModel):
    routes: List[Route]
    config: Optional[PipelineConfigPayload] = None


def _route_to_json_payload(route: Route) -> Dict[str, Any]:
    """Serialize Route into JSON-safe payload (times/dates as strings)."""
    if hasattr(route, "model_dump"):
        return route.model_dump(mode="json")  # type: ignore[attr-defined]
    return json.loads(json.dumps(route.dict(), default=str))


@app.post("/optimize-v6-by-day")
async def optimize_v6_by_day_endpoint(
    routes: List[Route],
    use_ml_assignment: bool = Query(
        default=True,
        description="Activa scoring ML para encadenado de rutas",
    ),
) -> Dict[str, Any]:
    """
    Optimize routes per day of the week.
    Returns a dict keyed by day code with schedule and stats for each day.
    
    Args:
        routes: List of Route objects to optimize
        
    Returns:
        Dictionary mapping day codes to schedules and statistics
    """
    try:
        from optimizer_v6 import optimize_v6

        logger.info(f"[V6-ByDay] Starting per-day optimization with {len(routes)} total routes")

        results: Dict[str, Any] = {}

        for day in ALL_DAYS:
            # Filter routes that run on this day
            day_routes = [r for r in routes if day in r.days]

            if not day_routes:
                results[day] = {
                    "schedule": [],
                    "stats": {
                        "total_buses": 0, "total_routes": 0,
                        "total_entries": 0, "total_exits": 0,
                        "max_entries_per_bus": 0, "max_exits_per_bus": 0,
                        "buses_with_both": 0, "avg_routes_per_bus": 0,
                        "total_early_shift_minutes": 0,
                    },
                    "day_name": DAY_NAMES[day]
                }
                continue

            logger.info(
                f"[V6-ByDay] {DAY_NAMES[day]}: {len(day_routes)} routes "
                f"(ml_assignment={use_ml_assignment})"
            )
            schedule = optimize_v6(day_routes, use_ml_assignment=use_ml_assignment)
            schedule, fleet_assignment = _apply_fleet_profiles(schedule)

            total_routes = sum(len(b.items) for b in schedule)
            entry_counts = [sum(1 for i in b.items if i.type == "entry") for b in schedule]
            exit_counts = [sum(1 for i in b.items if i.type == "exit") for b in schedule]
            max_entries = max(entry_counts) if entry_counts else 0
            max_exits = max(exit_counts) if exit_counts else 0
            buses_with_both = sum(1 for i, e in enumerate(entry_counts) if e > 0 and exit_counts[i] > 0)
            total_early_shift = sum(
                item.time_shift_minutes for b in schedule for item in b.items
                if item.time_shift_minutes > 0
            )

            results[day] = {
                "schedule": [s.dict() for s in schedule],
                "stats": {
                    "total_buses": len(schedule),
                    "total_routes": total_routes,
                    "total_entries": sum(entry_counts),
                    "total_exits": sum(exit_counts),
                    "max_entries_per_bus": max_entries,
                    "max_exits_per_bus": max_exits,
                    "buses_with_both": buses_with_both,
                    "avg_routes_per_bus": round(total_routes / len(schedule), 1) if schedule else 0,
                    "total_early_shift_minutes": total_early_shift,
                },
                "fleet_assignment": fleet_assignment,
                "day_name": DAY_NAMES[day]
            }

            logger.info(f"[V6-ByDay] {DAY_NAMES[day]}: {len(schedule)} buses, {total_routes} routes")

        return results

    except Exception as e:
        logger.error(f"[V6-ByDay] Optimization error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MONTE CARLO VALIDATION ENDPOINTS
# =============================================================================

@app.post("/validate-schedule")
async def validate_schedule_endpoint(schedule: List[BusSchedule]) -> Dict[str, Any]:
    """
    Valida un horario ya optimizado con Monte Carlo.
    Retorna un job_id para seguimiento WebSocket.
    
    Args:
        schedule: Lista de BusSchedule con el horario optimizado
        
    Returns:
        dict: job_id y WebSocket URL para seguimiento
    """
    # Limpiar jobs antiguos
    _cleanup_old_validation_jobs()
    
    job_id = str(uuid4())
    
    # Guardar el schedule en memoria/cache para el WebSocket
    validation_jobs[job_id] = {
        "schedule": schedule,
        "status": "ready",
        "created_at": datetime.utcnow()
    }
    
    logger.info(f"[Validate Schedule] Job {job_id} created with {len(schedule)} buses")
    
    return {
        "job_id": job_id,
        "status": "ready",
        "message": "Listo para validaciÃ³n Monte Carlo",
        "websocket_url": f"/ws/monte-carlo/{job_id}"
    }


@app.get("/validate-schedule/{job_id}")
async def get_validation_job_status(job_id: str) -> Dict[str, Any]:
    """
    Obtiene el estado de un job de validaciÃ³n.
    
    Args:
        job_id: ID del job de validaciÃ³n
        
    Returns:
        dict: Estado del job
    """
    if job_id not in validation_jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    job = validation_jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "created_at": job["created_at"].isoformat(),
        "bus_count": len(job.get("schedule", []))
    }


# =============================================================================
# DEBUG ENDPOINTS FOR MONTE CARLO
# =============================================================================

@app.post("/debug-monte-carlo")
async def debug_monte_carlo(schedule: List[BusSchedule]) -> Dict[str, Any]:
    """
    Endpoint de debug para Monte Carlo.
    
    Retorna informaciÃ³n detallada sobre el schedule sin ejecutar simulaciÃ³n:
    - travel_times extraÃ­dos del schedule
    - base_travel_times estimados
    - AnÃ¡lisis de buffers entre rutas
    - VerificaciÃ³n de factibilidad base
    
    Args:
        schedule: Lista de BusSchedule con el horario optimizado
        
    Returns:
        dict: InformaciÃ³n de debug detallada
    """
    from validation.monte_carlo import extract_travel_times_from_schedule, check_schedule_feasibility
    
    logger.info(f"[Debug MC] Analyzing schedule with {len(schedule)} buses")
    
    # Extraer travel times del schedule
    travel_times = extract_travel_times_from_schedule(schedule)
    
    # AnÃ¡lisis por bus
    bus_analysis = []
    for bus_idx, bus in enumerate(schedule):
        items = sorted(bus.items, key=lambda x: x.start_time.hour * 60 + x.start_time.minute)
        pairs = []
        
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            
            end_current = current.end_time.hour * 60 + current.end_time.minute
            start_next = next_item.start_time.hour * 60 + next_item.start_time.minute
            buffer = start_next - end_current
            
            tt_key = (current.route_id, next_item.route_id)
            travel_time = travel_times.get(tt_key, 15.0)
            
            pairs.append({
                "from_route": current.route_id,
                "to_route": next_item.route_id,
                "end_current": f"{current.end_time.hour:02d}:{current.end_time.minute:02d}",
                "start_next": f"{next_item.start_time.hour:02d}:{next_item.start_time.minute:02d}",
                "buffer_minutes": buffer,
                "deadhead_minutes": next_item.deadhead_minutes,
                "travel_time_used": travel_time,
                "has_violation": buffer < travel_time,
                "margin": buffer - travel_time
            })
        
        bus_analysis.append({
            "bus_index": bus_idx,
            "total_items": len(items),
            "transitions": pairs
        })
    
    # Verificar factibilidad base
    is_feasible, violations = check_schedule_feasibility(schedule, travel_times)
    
    # Calcular estadÃ­sticas de margen
    all_margins = []
    for bus in bus_analysis:
        for pair in bus["transitions"]:
            all_margins.append(pair["margin"])
    
    return {
        "summary": {
            "total_buses": len(schedule),
            "total_transitions": len(travel_times),
            "base_feasible": is_feasible,
            "base_violations": violations,
            "unique_travel_time_pairs": len(travel_times)
        },
        "travel_times": {f"{k[0]}->{k[1]}": v for k, v in travel_times.items()},
        "bus_analysis": bus_analysis,
        "margin_stats": {
            "min_margin": min(all_margins) if all_margins else 0,
            "max_margin": max(all_margins) if all_margins else 0,
            "avg_margin": sum(all_margins) / len(all_margins) if all_margins else 0,
            "negative_margins": sum(1 for m in all_margins if m < 0),
            "zero_or_negative": sum(1 for m in all_margins if m <= 0)
        }
    }


# =============================================================================
# SUGGESTION ENGINE ENDPOINTS
# =============================================================================

@app.post("/api/suggestions")
async def get_suggestions(
    route: Route = Body(..., description="Ruta a evaluar para inserciÃ³n"),
    buses: List[Bus] = Body(..., description="Lista de buses disponibles"),
    bus_schedules: Optional[Dict[str, List[Dict[str, Any]]]] = Body(
        None, 
        description="Schedule actual de cada bus {bus_id: [schedule_items]}"
    ),
    max_suggestions: int = Body(5, ge=1, le=20),
    min_buffer_minutes: float = Body(5.0, ge=0)
) -> Dict[str, Any]:
    """
    Genera sugerencias inteligentes para ubicaciÃ³n Ã³ptima de una ruta.
    
    EvalÃºa TODAS las posiciones posibles en todos los buses y devuelve
    las mejores opciones ordenadas por puntuaciÃ³n (0-100).
    
    Usa OSRM para calcular tiempos de viaje reales entre rutas.
    
    Args:
        route: Ruta a evaluar para inserciÃ³n
        buses: Lista de buses disponibles
        bus_schedules: Schedule actual de cada bus (opcional)
        max_suggestions: NÃºmero mÃ¡ximo de sugerencias a retornar
        min_buffer_minutes: Buffer mÃ­nimo aceptable entre rutas
        
    Returns:
        Dict con route_id, suggestions ordenadas, y estadÃ­sticas
        
    Example:
        POST /api/suggestions
        {
            "route": {"id": "R001", "name": "Route 1", ...},
            "buses": [{"id": "BUS01", "capacity": 50}, ...],
            "bus_schedules": {
                "BUS01": [
                    {"route_id": "R002", "start_time": "07:00", "end_time": "08:00"}
                ]
            },
            "max_suggestions": 5
        }
    """
    try:
        from services.suggestion_engine import (
            SuggestionEngine, 
            get_suggestion_engine
        )
        
        logger.info(f"[Suggestions] Generando sugerencias para ruta {route.id}")
        logger.info(f"[Suggestions] Buses disponibles: {len(buses)}")
        
        # Obtener o crear motor de sugerencias
        engine = get_suggestion_engine()
        
        # Generar sugerencias
        response = await engine.generate_suggestions(
            route=route,
            buses=buses,
            bus_schedules=bus_schedules,
            max_suggestions=max_suggestions,
            min_buffer_minutes=min_buffer_minutes
        )
        
        logger.info(f"[Suggestions] Generadas {len(response.suggestions)} sugerencias")
        logger.info(f"[Suggestions] Top score: {response.suggestions[0].score if response.suggestions else 'N/A'}")
        
        return {
            "route_id": response.route_id,
            "suggestions": [s.model_dump() for s in response.suggestions],
            "total_evaluated": response.total_evaluated,
            "generated_at": response.generated_at.isoformat(),
            "osrm_stats": response.osrm_stats
        }
        
    except Exception as e:
        logger.error(f"[Suggestions] Error generando sugerencias: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error generando sugerencias: {str(e)}"
        )


@app.get("/api/suggestions/health")
async def suggestions_health_check() -> Dict[str, Any]:
    """
    Verifica el estado del motor de sugerencias y OSRM.
    
    Returns:
        Dict con estado de los servicios
    """
    try:
        from services.osrm_service import get_osrm_service
        
        osrm_service = get_osrm_service()
        osrm_health = await osrm_service.health_check()
        osrm_stats = osrm_service.get_stats()
        
        return {
            "status": "healthy" if osrm_health.get('status') == 'healthy' else 'degraded',
            "osrm": {
                "status": osrm_health.get('status'),
                "response_time_ms": osrm_health.get('response_time_ms'),
                "cache_size": osrm_health.get('cache_size'),
                "cache_hits": osrm_stats.get('cache_hits', 0),
                "requests": osrm_stats.get('requests', 0)
            },
            "suggestion_engine": {
                "available": True,
                "weights": {
                    "prev_buffer": 0.35,
                    "next_buffer": 0.35,
                    "geographic": 0.20,
                    "capacity": 0.10
                }
            }
        }
        
    except Exception as e:
        logger.error(f"[Suggestions Health] Error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "osrm": None,
            "suggestion_engine": {"available": False}
        }


# =============================================================================
# PDF EXPORT
# =============================================================================

@app.post("/export_pdf")
async def export_pdf(data: Union[List[Dict[str, Any]], Dict[str, Any]] = Body(...)) -> StreamingResponse:
    """
    Export schedule as PDF.
    
    Args:
        data: Schedule data dictionary or list
        
    Returns:
        PDF file as StreamingResponse
    """
    try:
        from pdf_service import generate_schedule_pdf

        # Support both old format (list) and new format (dict with schedule + day_name)
        if isinstance(data, list):
            schedule: List[Dict[str, Any]] = data
            day_name: Optional[str] = None
        else:
            raw_schedule = data.get("schedule", [])
            schedule = raw_schedule if isinstance(raw_schedule, list) else []
            day_name = data.get("day_name", None)

        pdf_buffer = generate_schedule_pdf(schedule, day_name=day_name)

        filename = "tutti_schedule"
        if day_name:
            filename += f"_{day_name.lower()}"
        filename += ".pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Type": "application/pdf", "Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ASYNC OPTIMIZATION ENDPOINTS (Celery)
# =============================================================================

@app.post("/optimize-pipeline-by-day-async")
async def optimize_pipeline_by_day_async(request: PipelineOptimizationRequest) -> Dict[str, Any]:
    """
    Encola pipeline automático por día:
    optimización base + validación OSRM + reoptimización iterativa.
    """
    routes = request.routes
    routes_payload = [_route_to_json_payload(route) for route in routes]
    _cleanup_old_local_jobs()
    config_payload = request.config.model_dump() if request.config else {
        "auto_start": True,
        "objective": "min_buses_viability",
        "max_duration_sec": int(os.environ.get("TUTTI_PIPELINE_MAX_DURATION_SEC", "300")),
        "max_iterations": int(os.environ.get("TUTTI_PIPELINE_MAX_ITERATIONS", "2")),
        "use_ml_assignment": True,
        "invalid_rows_dropped": 0,
    }
    job_id = str(uuid4())
    created_at = datetime.utcnow()
    _update_local_job_state(
        job_id,
        status="queued",
        algorithm="pipeline-v6-osrm",
        created_at=created_at,
        config=config_payload,
        message="Pipeline en cola",
        progress=0,
        stage="queued",
    )

    db = None
    if is_database_available():
        try:
            db = SessionLocal()
            job = OptimizationJob(
                id=job_id,
                status="queued",
                algorithm="pipeline-v6-osrm",
                input_data=routes_payload,
                created_at=created_at
            )
            db.add(job)
            db.commit()
        except Exception as e:
            logger.warning(f"[Pipeline] Could not create job in database: {e}")
        finally:
            if db:
                db.close()

    can_use_celery = (
        CELERY_ENABLED
        and optimize_pipeline_task
        and is_database_available()
        and (not config or config.is_redis_available())
        and _has_active_celery_workers(timeout=0.8)
    )
    if can_use_celery:
        try:
            task = optimize_pipeline_task.delay(
                routes_data=routes_payload,
                job_id=job_id,
                pipeline_config=config_payload,
            )
            return {
                "job_id": job_id,
                "task_id": task.id,
                "status": "queued",
                "message": "Pipeline automático encolado correctamente",
                "websocket_url": f"/ws/optimize/{job_id}",
                "config_applied": config_payload,
            }
        except Exception as e:
            logger.warning(f"[Pipeline] Celery failed, using sync fallback: {e}")

    try:
        routes_data = routes_payload
        local_task = asyncio.create_task(
            _run_local_pipeline_job(
                job_id=job_id,
                routes_data=routes_data,
                config_payload=config_payload,
            )
        )
        LOCAL_PIPELINE_TASKS[job_id] = local_task

        if WEBSOCKET_AVAILABLE and manager:
            await manager.send_progress(
                job_id,
                build_status_message(job_id, "queued", "Pipeline local encolado"),
            )

        return {
            "job_id": job_id,
            "task_id": None,
            "status": "queued",
            "message": "Pipeline automático encolado (modo local)",
            "websocket_url": f"/ws/optimize/{job_id}",
            "config_applied": config_payload,
        }
    except Exception as e:
        logger.error(f"[Pipeline] Local async fallback failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


@app.post("/optimize-hybrid-by-day-async")
async def optimize_hybrid_by_day_async(request: PipelineOptimizationRequest) -> Dict[str, Any]:
    """
    Encola pipeline híbrido (QUBO quantum-inspired + validación OSRM).

    Es un wrapper compatible del endpoint general con `objective` forzado a
    `min_buses_viability_hybrid`.
    """
    config_payload = request.config.model_dump() if request.config else {}
    config_payload["objective"] = "min_buses_viability_hybrid"
    config_payload.setdefault("auto_start", True)
    config_payload.setdefault("max_duration_sec", int(os.environ.get("TUTTI_PIPELINE_MAX_DURATION_SEC", "300")))
    config_payload.setdefault("max_iterations", int(os.environ.get("TUTTI_PIPELINE_MAX_ITERATIONS", "2")))
    config_payload.setdefault("use_ml_assignment", True)
    config_payload.setdefault("invalid_rows_dropped", 0)

    wrapped_request = PipelineOptimizationRequest(
        routes=request.routes,
        config=PipelineConfigPayload(**config_payload),
    )
    return await optimize_pipeline_by_day_async(wrapped_request)

@app.post("/optimize-async")
async def optimize_async(
    routes: List[Route],
    use_ml_assignment: bool = Query(
        default=True,
        description="Activa scoring ML para encadenado de rutas",
    ),
) -> Dict[str, Any]:
    """
    Encolar optimizaciÃ³n para procesamiento async.
    
    Args:
        routes: Lista de rutas a optimizar
        
    Returns:
        dict: InformaciÃ³n del job encolado (job_id, task_id, status)
    """
    job_id = str(uuid4())
    
    # Crear job en DB si estÃ¡ disponible
    db = None
    if is_database_available():
        try:
            db = SessionLocal()
            job = OptimizationJob(
                id=job_id,
                status="queued",
                algorithm="v6",
                input_data=[r.dict() for r in routes],
                created_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not create job in database: {e}")
        finally:
            if db:
                db.close()
    
    if CELERY_ENABLED and optimize_task:
        try:
            # Encolar tarea Celery
            task = optimize_task.delay(
                routes_data=[r.dict() for r in routes],
                job_id=job_id,
                use_ml_assignment=use_ml_assignment,
            )
            return {
                "job_id": job_id,
                "task_id": task.id,
                "status": "queued",
                "message": "OptimizaciÃ³n encolada correctamente",
                "websocket_url": f"/ws/optimize/{job_id}",
                "optimization_options": {
                    "use_ml_assignment": bool(use_ml_assignment),
                },
            }
        except Exception as e:
            logger.warning(f"Celery failed (Redis unavailable?), using sync mode: {e}")
            # Continue to sync fallback below
    
    # Fallback: procesar sync
    logger.info(f"Celery disabled or unavailable, processing job {job_id} synchronously")
    try:
        from optimizer_v6 import optimize_v6
        schedule = optimize_v6(routes, use_ml_assignment=use_ml_assignment)
        schedule, fleet_assignment = _apply_fleet_profiles(schedule)
        
        total_routes = sum(len(bus.items) for bus in schedule)
        result = {
            "schedule": [s.dict() for s in schedule],
            "stats": {
                "total_buses": len(schedule),
                "total_routes": total_routes,
            },
            "optimization_options": {
                "use_ml_assignment": bool(use_ml_assignment),
            },
            "fleet_assignment": fleet_assignment,
        }
        
        # Actualizar job en DB
        if is_database_available():
            db = SessionLocal()
            try:
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.result = result
                    job.completed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
        
        return {
            "job_id": job_id,
            "task_id": None,
            "status": "completed",
            "message": "OptimizaciÃ³n completada (modo sÃ­ncrono)",
            "result": result,
            "websocket_url": f"/ws/optimize/{job_id}",
            "optimization_options": {
                "use_ml_assignment": bool(use_ml_assignment),
            },
        }
    except Exception as e:
        logger.error(f"Sync optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimize-async-advanced")
async def optimize_async_advanced(
    routes: List[Route],
    weights: Optional[Dict[str, float]] = None,
    preset: Optional[str] = None,
    use_lns: bool = True,
    use_ml_assignment: bool = Query(
        default=True,
        description="Activa scoring ML para encadenado de rutas",
    ),
) -> Dict[str, Any]:
    """
    Encolar optimizaciÃ³n avanzada (multi-objetivo + LNS) para procesamiento async.
    
    Args:
        routes: Lista de rutas a optimizar
        weights: Pesos personalizados para funciÃ³n objetivo
        preset: Nombre del preset a usar (minimize_buses, minimize_cost, minimize_emissions, balanced)
        use_lns: Usar LNS para mejorar soluciÃ³n (default: True)
        
    Returns:
        dict: InformaciÃ³n del job encolado
    """
    job_id = str(uuid4())
    
    # Crear job en DB si estÃ¡ disponible
    db = None
    if is_database_available():
        try:
            db = SessionLocal()
            job = OptimizationJob(
                id=job_id,
                status="queued",
                algorithm="v6-advanced",
                input_data=[r.dict() for r in routes],
                created_at=datetime.utcnow()
            )
            db.add(job)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not create job in database: {e}")
        finally:
            if db:
                db.close()
    
    # Importar la nueva tarea
    try:
        from tasks import optimize_advanced_task
        advanced_task_available = True
    except ImportError:
        advanced_task_available = False
    
    if CELERY_ENABLED and advanced_task_available:
        try:
            # Encolar tarea Celery avanzada
            task = optimize_advanced_task.delay(
                routes_data=[r.dict() for r in routes],
                job_id=job_id,
                weights=weights,
                preset=preset,
                use_lns=use_lns,
                use_ml_assignment=use_ml_assignment,
            )
            
            features = ["multi_objective"]
            if use_lns:
                features.append("lns")
            
            return {
                "job_id": job_id,
                "task_id": task.id,
                "status": "queued",
                "message": "Optimizacion avanzada encolada correctamente",
                "websocket_url": f"/ws/optimize/{job_id}",
                "features": features,
                "optimization_options": {
                    "use_lns": bool(use_lns),
                    "use_ml_assignment": bool(use_ml_assignment),
                },
            }
        except Exception as e:
            logger.warning(f"Celery advanced task failed, using sync mode: {e}")

    # Fallback: procesar sync
    logger.info(f"Celery disabled or task unavailable, processing job {job_id} synchronously")
    try:
        from optimizer_multi import ObjectiveWeights, MultiObjectiveOptimizer
        from optimizer_lns import optimize_v6_lns
        
        # Determinar pesos
        if preset:
            from config import ObjectivePresets
            weights_dict = ObjectivePresets.get_preset(preset)
        else:
            weights_dict = weights
        
        weights_obj = ObjectiveWeights(**weights_dict) if weights_dict else ObjectiveWeights()
        
        # Ejecutar optimizacion
        schedule = optimize_v6_lns(
            routes,
            weights=weights_obj,
            use_lns=use_lns,
            use_ml_assignment=use_ml_assignment,
        )
        
        # Calcular metricas
        stats = _calculate_stats(schedule)
        evaluator = MultiObjectiveOptimizer(weights_obj)
        metrics = evaluator.calculate_metrics(schedule)
        score = evaluator.evaluate_schedule(schedule)
        
        result = {
            "schedule": [s.dict() for s in schedule],
            "stats": stats,
            "multi_objective": {
                "score": round(score, 2),
                "metrics": metrics.to_dict(),
                "weights": weights_obj.to_dict()
            },
            "optimization_options": {
                "use_lns": bool(use_lns),
                "use_ml_assignment": bool(use_ml_assignment),
            }
        }
        
        # Actualizar job en DB
        if is_database_available():
            db = SessionLocal()
            try:
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.result = result
                    job.completed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
        
        features = ["multi_objective"]
        if use_lns:
            features.append("lns")
        
        return {
            "job_id": job_id,
            "task_id": None,
            "status": "completed",
            "message": "Optimizacion avanzada completada (modo sincrono)",
            "result": result,
            "websocket_url": f"/ws/optimize/{job_id}",
            "features": features,
            "optimization_options": {
                "use_lns": bool(use_lns),
                "use_ml_assignment": bool(use_ml_assignment),
            },
        }
    except Exception as e:
        logger.error(f"Sync advanced optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Obtener estado de un job.
    
    Args:
        job_id: ID del job
        
    Returns:
        dict: Estado del job
    """
    _cleanup_old_local_jobs()
    local_job = _get_local_job_state(job_id)
    local_payload = _serialize_local_job_status(local_job) if local_job else None

    db_payload: Optional[Dict[str, Any]] = None
    if is_database_available():
        db = SessionLocal()
        try:
            job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
            if job:
                db_payload = {
                    "job_id": str(job.id),
                    "status": job.status,
                    "algorithm": job.algorithm,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "error": job.error_message,
                }
        finally:
            db.close()

    # If DB and runtime diverge, prefer whichever is terminal.
    if local_payload and db_payload:
        local_terminal = str(local_payload.get("status", "")).lower() in TERMINAL_STATUSES
        db_terminal = str(db_payload.get("status", "")).lower() in TERMINAL_STATUSES
        if local_terminal and not db_terminal:
            return local_payload
        if db_terminal and not local_terminal:
            return db_payload
        # While running, runtime snapshot has richer/stabler progress metadata.
        return local_payload

    if local_payload:
        return local_payload
    if db_payload:
        return db_payload

    raise HTTPException(status_code=404, detail="Job no encontrado")


@app.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    """
    Obtener resultados de un job completado.
    
    Args:
        job_id: ID del job
        
    Returns:
        dict: Resultados de la optimizaciÃ³n
    """
    _cleanup_old_local_jobs()
    local_job = _get_local_job_state(job_id)
    local_payload = _serialize_local_job_result(local_job) if local_job else None

    db_payload: Optional[Dict[str, Any]] = None
    if is_database_available():
        db = SessionLocal()
        try:
            job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
            if job:
                if job.status == "failed":
                    db_payload = {
                        "job_id": job_id,
                        "status": "failed",
                        "error": job.error_message,
                    }
                elif job.status == "completed":
                    db_payload = {
                        "job_id": job_id,
                        "status": "completed",
                        "result": job.result,
                        "stats": job.stats,
                    }
                else:
                    db_payload = {"job_id": job_id, "status": job.status}
        finally:
            db.close()

    # If DB and runtime diverge, prefer whichever reached a terminal state.
    if local_payload and db_payload:
        local_status = str(local_payload.get("status", "unknown")).lower()
        db_status = str(db_payload.get("status", "unknown")).lower()
        local_terminal = local_status in TERMINAL_STATUSES
        db_terminal = db_status in TERMINAL_STATUSES

        if local_terminal and not db_terminal:
            return local_payload
        if db_terminal and not local_terminal:
            return db_payload
        if local_status == "completed" and local_payload.get("result"):
            return local_payload
        if db_status == "completed" and db_payload.get("result"):
            return db_payload
        return local_payload

    if local_payload:
        return local_payload
    if db_payload:
        return db_payload

    raise HTTPException(status_code=404, detail="Job no encontrado")


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Obtener estado de una tarea Celery directamente.
    
    Args:
        task_id: ID de la tarea Celery
        
    Returns:
        dict: Estado de la tarea
    """
    if not CELERY_ENABLED or not celery_app:
        raise HTTPException(status_code=503, detail="Celery not available")
    
    try:
        result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "state": result.state
        }
        
        if result.successful():
            response["result"] = result.get()
        elif result.failed():
            response["error"] = str(result.result)
        elif result.state == "PROGRESS":
            response["progress"] = result.info
            
        return response
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=503, detail="Celery backend not available")


@app.delete("/jobs/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, Any]:
    """
    Cancelar un job en progreso.
    
    Args:
        job_id: ID del job a cancelar
        
    Returns:
        dict: Mensaje de confirmaciÃ³n
    """
    if not is_database_available():
        local_job = _get_local_job_state(job_id)
        local_task = LOCAL_PIPELINE_TASKS.get(job_id)
        if not local_job and not local_task:
            raise HTTPException(status_code=404, detail="Job no encontrado")

        status = (local_job or {}).get("status")
        if status and status not in ["queued", "running"]:
            raise HTTPException(
                status_code=400,
                detail=f"Job no puede cancelarse. Estado actual: {status}"
            )

        if local_task and not local_task.done():
            local_task.cancel()
            logger.info(f"[Cancel] Cancelled local pipeline task for job {job_id}")

        _update_local_job_state(
            job_id,
            status="cancelled",
            completed_at=datetime.utcnow(),
            message="Job cancelado por el usuario",
            stage="cancelled",
            progress=100,
        )

        if WEBSOCKET_AVAILABLE and manager:
            await manager.send_progress(
                job_id,
                build_status_message(job_id, "cancelled", "Job cancelado por el usuario")
            )

        return {
            "message": "Job cancelado correctamente",
            "job_id": job_id,
            "status": "cancelled"
        }
    
    db = SessionLocal()
    try:
        job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        
        if job.status not in ["queued", "running"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Job no puede cancelarse. Estado actual: {job.status}"
            )
        
        # Revocar tarea Celery si estÃ¡ disponible
        if CELERY_ENABLED and celery_app:
            try:
                # Intentar revocar la tarea
                celery_app.control.revoke(job_id, terminate=True, signal='SIGTERM')
                logger.info(f"[Cancel] Revoked Celery task for job {job_id}")
            except Exception as e:
                logger.warning(f"[Cancel] Failed to revoke Celery task: {e}")

        # Cancelar task local en memoria (fallback sin Celery)
        local_task = LOCAL_PIPELINE_TASKS.get(job_id)
        if local_task and not local_task.done():
            local_task.cancel()
            logger.info(f"[Cancel] Cancelled local pipeline task for job {job_id}")
        
        # Actualizar estado en DB
        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        db.commit()
        
        # Notificar via WebSocket si estÃ¡ disponible
        if WEBSOCKET_AVAILABLE and manager:
            await manager.send_progress(
                job_id, 
                build_status_message(job_id, "cancelled", "Job cancelado por el usuario")
            )
        
        logger.info(f"[Cancel] Job {job_id} cancelled successfully")
        return {
            "message": "Job cancelado correctamente",
            "job_id": job_id,
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Cancel] Error cancelling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al cancelar job: {str(e)}")
    finally:
        db.close()


# =============================================================================
# WEBSOCKET ENDPOINTS
# =============================================================================

@app.websocket("/ws/optimize/{job_id}")
async def websocket_optimize(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time optimization progress updates.
    
    Connect to this endpoint to receive live progress updates for a specific job.
    
    Protocol:
    - Client connects: ws://localhost:8000/ws/optimize/{job_id}
    - Server sends initial status
    - Client can send: {"action": "ping"} for heartbeat
    - Server responds: {"type": "pong", "timestamp": "..."}
    - Server broadcasts progress: {"type": "progress", "phase": "...", "progress": 45, ...}
    
    Args:
        websocket: WebSocket connection
        job_id: The job ID to subscribe to
    """
    if not WEBSOCKET_AVAILABLE:
        await websocket.close(code=1011, reason="WebSocket not available")
        return
    
    # Accept connection
    connected = await manager.connect(websocket, job_id)
    if not connected:
        await websocket.close(code=1011, reason="Failed to accept connection")
        return
    
    logger.info(f"[WebSocket] Client connected for job {job_id}")
    
    try:
        # Send initial status
        status_sent = False
        if is_database_available():
            db = SessionLocal()
            try:
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    await manager.send_to_client(
                        websocket,
                        build_status_message(job_id, job.status)
                    )
                    
                    # If job is completed, send result immediately
                    if job.status == "completed" and job.result:
                        await manager.send_to_client(
                            websocket,
                            build_completed_message(job_id, job.result, job.stats)
                        )
                    status_sent = True
                else:
                    local_job = _get_local_job_state(job_id)
                    if local_job:
                        await manager.send_to_client(
                            websocket,
                            build_status_message(
                                job_id,
                                str(local_job.get("status", "queued")),
                                str(local_job.get("message", "Job local en memoria")),
                            )
                        )
                        status_sent = True
            finally:
                db.close()
        if not status_sent:
            local_job = _get_local_job_state(job_id)
            if local_job:
                await manager.send_to_client(
                    websocket,
                    build_status_message(
                        job_id,
                        str(local_job.get("status", "queued")),
                        str(local_job.get("message", "Job local en memoria")),
                    )
                )
                status_sent = True

        if not status_sent:
            await manager.send_to_client(
                websocket,
                build_status_message(job_id, "unknown", "Job no encontrado")
            )
        
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Receive message from client (heartbeat or commands)
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await manager.send_to_client(
                        websocket,
                        {"type": "error", "message": "Invalid JSON"}
                    )
                    continue
                
                action = message.get("action")
                
                if action == "ping":
                    # Heartbeat response
                    await manager.send_to_client(websocket, build_pong_message())
                    
                elif action == "get_status":
                    # Client requesting current status
                    if is_database_available():
                        db = SessionLocal()
                        try:
                            job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                            if job:
                                await manager.send_to_client(
                                    websocket,
                                    build_status_message(job_id, job.status)
                                )
                        finally:
                            db.close()
                            
                else:
                    await manager.send_to_client(
                        websocket,
                        {"type": "error", "message": f"Unknown action: {action}"}
                    )
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"[WebSocket] Error handling message for job {job_id}: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected from job {job_id}")
    except Exception as e:
        logger.error(f"[WebSocket] Error for job {job_id}: {e}")
    finally:
        await manager.disconnect(websocket, job_id)
        logger.info(f"[WebSocket] Connection closed for job {job_id}")


@app.websocket("/ws/monte-carlo/{job_id}")
async def websocket_monte_carlo(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time Monte Carlo simulation streaming.
    
    Streams Monte Carlo validation results progressively in batches,
    allowing real-time visualization of simulation progress and
    3D scatter plot data.
    
    IMPORTANT: Primero debe llamar a POST /validate-schedule para crear un job
    y obtener el job_id. El horario optimizado se obtiene del cache, no del WebSocket.
    
    Protocol:
    - Client calls: POST /validate-schedule with optimized schedule
    - Server returns: { "job_id": "...", "websocket_url": "/ws/monte-carlo/{job_id}" }
    - Client connects: ws://localhost:8000/ws/monte-carlo/{job_id}
    - Client sends configuration JSON:
      {
        "n_simulations": 1000,
        "uncertainty": 0.2,
        "distribution": "lognormal",
        "batch_size": 50
      }
    - Server sends progress updates every batch_size simulations:
      {
        "type": "progress",
        "completed": 50,
        "total": 1000,
        "feasible_rate": 0.92,
        "grade": "A",
        "scenarios": [{"id": 0, "x": 0.15, "y": 245.5, "z": 1, "feasible": true, ...}]
      }
    - Server sends completion message:
      {
        "type": "completed",
        "final_grade": "A",
        "feasible_rate": 0.95,
        "interpretation": {
          "grade": "A",
          "meaning": "MÃ¡s del 95% de escenarios vÃ¡lidos",
          "description": "El horario es muy robusto...",
          "recommendation": "El horario estÃ¡ listo para producciÃ³n."
        },
        "stats": {
          "total_simulations": 1000,
          "feasible_count": 950,
          "infeasible_count": 50,
          "avg_violations_per_scenario": 2.5
        }
      }
    
    Args:
        websocket: WebSocket connection
        job_id: Unique job identifier (must exist in validation_jobs cache)
    """
    if not MONTE_CARLO_WS_AVAILABLE:
        await websocket.close(code=1011, reason="Monte Carlo WebSocket not available")
        return
    
    await handle_monte_carlo_websocket(websocket, job_id)


# =============================================================================
# MANUAL SCHEDULE VALIDATION WEBSOCKET ENDPOINT
# =============================================================================

# Import del handler de validaciÃ³n en tiempo real
try:
    handle_schedule_validation_websocket = _load_ws_handler(
        "schedule_validation_ws.py",
        "handle_schedule_validation_websocket",
    )
    SCHEDULE_VALIDATION_WS_AVAILABLE = True
except Exception as e:
    SCHEDULE_VALIDATION_WS_AVAILABLE = False
    logger.warning(f"[Import] Schedule validation WebSocket not available: {e}")


@app.websocket("/ws/validate-schedule")
async def websocket_validate_schedule(websocket: WebSocket):
    """
    WebSocket endpoint para validaciÃ³n de horarios manuales en tiempo real.
    
    Valida instantÃ¡neamente si las conexiones entre rutas son viables,
    calculando tiempos de viaje reales con OSRM.
    
    Protocol:
    - Client connects: ws://localhost:8000/ws/validate-schedule
    - Server sends: { "type": "connected", "session_id": "..." }
    
    Mensajes del cliente:
    
    1. Validar conexiÃ³n entre dos rutas:
    {
        "type": "validate_connection",
        "route_a": {
            "id": "R1",
            "route_id": "R1",
            "start_time": "08:00",
            "end_time": "08:30",
            "start_location": [42.24, -8.72],
            "end_location": [42.25, -8.73],
            "type": "entry"
        },
        "route_b": {
            "id": "R2",
            "route_id": "R2",
            "start_time": "09:00",
            "end_time": "09:30",
            "start_location": [42.25, -8.73],
            "end_location": [42.26, -8.74],
            "type": "exit"
        }
    }
    
    Server response:
    {
        "type": "validation_result",
        "compatible": true,
        "buffer_minutes": 10.5,
        "travel_time": 14.5,
        "time_available": 25.0,
        "suggested_start": null,
        "issue": null,
        "validation_time_ms": 45.2
    }
    
    2. Validar horario completo:
    {
        "type": "validate_full_schedule",
        "routes": [ {...}, {...}, ... ]
    }
    
    Server response:
    {
        "type": "full_validation",
        "is_valid": true,
        "issues": [],
        "issues_count": 0,
        "total_travel_time": 45.5,
        "efficiency_score": 85.0,
        "buffer_stats": {"min": 5.5, "max": 15.2, "avg": 10.1}
    }
    
    3. ValidaciÃ³n progresiva (agregar rutas una por una):
    {
        "type": "validate_progressive",
        "bus_id": "B001",
        "route": {...},
        "reset": false  // true para reiniciar el estado
    }
    
    4. Solicitar sugerencias de horario:
    {
        "type": "suggest_time",
        "current_route": {...},
        "next_route": {...},
        "travel_time": 15.0  // opcional
    }
    
    5. Heartbeat:
    { "type": "ping" }
    
    Server response:
    { "type": "pong", "timestamp": "..." }
    
    Args:
        websocket: WebSocket connection
    """
    if not SCHEDULE_VALIDATION_WS_AVAILABLE:
        await websocket.close(code=1011, reason="Schedule validation WebSocket not available")
        return
    
    from uuid import uuid4
    session_id = str(uuid4())
    
    await handle_schedule_validation_websocket(websocket, session_id)


# =============================================================================
# TIMELINE VALIDATION WEBSOCKET ENDPOINT
# =============================================================================

# Import del handler de validaciÃ³n de timeline
try:
    handle_timeline_validation_websocket = _load_ws_handler(
        "timeline_validation_ws.py",
        "handle_timeline_validation_websocket",
    )
    TIMELINE_VALIDATION_WS_AVAILABLE = True
except Exception as e:
    TIMELINE_VALIDATION_WS_AVAILABLE = False
    logger.warning(f"[Import] Timeline validation WebSocket not available: {e}")


@app.websocket("/ws/timeline-validate")
async def websocket_timeline_validate(websocket: WebSocket):
    """
    WebSocket endpoint para validaciÃ³n de timeline en tiempo real.
    
    Valida compatibilidad de rutas usando OSRM cuando el usuario las mueve,
    con respuesta en < 500ms gracias al cache de resultados.
    
    Protocol:
    - Client connects: ws://localhost:8000/ws/timeline-validate
    - Server sends: { "type": "connected", "session_id": "..." }
    
    Mensajes del cliente:
    
    1. Validar compatibilidad entre dos rutas:
    {
        "type": "check_compatibility",
        "route_a": {
            "endCoordinates": [lat, lon] or {"lat": x, "lon": y},
            "endTime": "08:30"
        },
        "route_b": {
            "startCoordinates": [lat, lon] or {"lat": x, "lon": y},
            "startTime": "09:00"
        }
    }
    
    Server response:
    {
        "type": "compatibility_result",
        "is_compatible": true,
        "travel_time_minutes": 14.5,
        "buffer_minutes": 10.5,
        "time_available": 25.0,
        "quality": "excellent",  // excellent | good | tight | incompatible
        "from_fallback": false,
        "validation_time_ms": 45.2
    }
    
    2. Obtener sugerencias de ubicaciÃ³n:
    {
        "type": "get_suggestions",
        "route": { ... },
        "buses": [
            { "busId": "B1", "routes": [...] },
            { "busId": "B2", "routes": [...] }
        ]
    }
    
    3. ValidaciÃ³n batch (mÃºltiples pares):
    {
        "type": "batch_validate",
        "pairs": [
            { "id": "1", "route_a": {...}, "route_b": {...} },
            { "id": "2", "route_a": {...}, "route_b": {...} }
        ]
    }
    
    4. Heartbeat:
    { "type": "ping" }
    
    Server response:
    { "type": "pong", "timestamp": "..." }
    
    Args:
        websocket: WebSocket connection
    """
    if not TIMELINE_VALIDATION_WS_AVAILABLE:
        await websocket.close(code=1011, reason="Timeline validation WebSocket not available")
        return
    
    from uuid import uuid4
    session_id = str(uuid4())
    
    await handle_timeline_validation_websocket(websocket, session_id)


# Serve compiled frontend assets in desktop mode.
if SERVE_FRONTEND_DIST and FRONTEND_DIST_DIR:
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIST_DIR, html=True),
        name="frontend-static",
    )
    logger.info(f"[Desktop] Serving frontend dist from: {FRONTEND_DIST_DIR}")
elif SERVE_FRONTEND_DIST:
    logger.warning("[Desktop] SERVE_FRONTEND_DIST enabled but no valid dist folder found")


# =============================================================================
# STARTUP AND SHUTDOWN EVENTS
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("[Startup] Tutti API starting...")

    # Ensure core DB tables exist in production environments.
    if is_database_available():
        try:
            create_tables()
            logger.info("[Startup] Database tables ensured")
        except Exception as e:
            logger.warning(f"[Startup] Could not ensure database tables: {e}")
    
    # Start progress listener if available
    if PROGRESS_LISTENER_AVAILABLE and WEBSOCKET_AVAILABLE and manager:
        started = await start_progress_listener(manager)
        if started:
            logger.info("[Startup] Progress listener started successfully")
        else:
            logger.warning("[Startup] Progress listener could not be started (Redis may be unavailable)")
    
    # Log configuration
    if config:
        logger.info(f"[Startup] Configuration: Celery={config.CELERY_ENABLED}, WebSocket={config.WEBSOCKET_ENABLED}")
    
    logger.info("[Startup] Tutti API ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("[Shutdown] Tutti API shutting down...")
    
    # Stop progress listener if running
    if PROGRESS_LISTENER_AVAILABLE:
        from progress_listener import stop_progress_listener
        stopped = stop_progress_listener()
        if stopped:
            logger.info("[Shutdown] Progress listener stopped")
    
    # Close OSRM service and save cache
    try:
        from services.osrm_service import close_osrm_service
        await close_osrm_service()
        logger.info("[Shutdown] OSRM service closed and cache saved")
    except Exception as e:
        logger.warning(f"[Shutdown] Error closing OSRM service: {e}")
    
    logger.info("[Shutdown] Tutti API shutdown complete")
