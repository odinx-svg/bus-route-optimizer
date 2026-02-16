"""
In-memory runtime store for optimization jobs.

Provides a unified snapshot source for job orchestration, WS reconnection,
and polling fallbacks.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Dict, List, Optional


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "lost", "error"}


def _utc_now() -> datetime:
    return datetime.utcnow()


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class JobRuntimeStore:
    """Thread-safe runtime state store for optimization jobs."""

    def __init__(self, terminal_ttl_hours: int = 4) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        self._terminal_ttl = timedelta(hours=max(1, int(terminal_ttl_hours)))

    def create_job(
        self,
        job_id: str,
        mode: str = "local",
        persisted_db: bool = False,
        algorithm: Optional[str] = None,
        status: str = "queued",
        message: str = "Pipeline en cola",
    ) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock:
            snapshot = self._jobs.get(job_id, {})
            snapshot.update(
                {
                    "job_id": job_id,
                    "status": status,
                    "phase": status,
                    "stage": status,
                    "progress": int(snapshot.get("progress", 0)),
                    "message": message,
                    "execution_mode": mode,
                    "persisted": bool(persisted_db),
                    "algorithm": algorithm or snapshot.get("algorithm"),
                    "created_at": snapshot.get("created_at", now),
                    "updated_at": now,
                    "started_at": snapshot.get("started_at"),
                    "completed_at": snapshot.get("completed_at"),
                    "result": snapshot.get("result"),
                    "stats": snapshot.get("stats"),
                    "metrics": snapshot.get("metrics"),
                    "error": snapshot.get("error"),
                    "error_code": snapshot.get("error_code"),
                    "terminal_reason": snapshot.get("terminal_reason"),
                    "last_contact_at": now,
                    "last_ws_seen_at": snapshot.get("last_ws_seen_at"),
                }
            )
            self._jobs[job_id] = snapshot
            return deepcopy(snapshot)

    def update_progress(
        self,
        job_id: str,
        stage: str,
        progress: int,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        payload = dict(extra or {})
        status = str(payload.pop("status", "running"))
        phase = str(payload.pop("phase", stage))
        execution_mode = payload.pop("execution_mode", None)
        metrics = payload.pop("metrics", None)

        with self._lock:
            snapshot = self._jobs.get(job_id) or self.create_job(job_id)
            snapshot.update(
                {
                    "status": status,
                    "phase": phase,
                    "stage": stage,
                    "progress": max(0, min(100, int(progress))),
                    "message": message,
                    "updated_at": now,
                    "last_contact_at": now,
                }
            )
            if execution_mode is not None:
                snapshot["execution_mode"] = execution_mode
            if metrics is not None:
                snapshot["metrics"] = metrics
            for key, value in payload.items():
                snapshot[key] = value
            if snapshot["status"] == "running" and snapshot.get("started_at") is None:
                snapshot["started_at"] = now
            self._jobs[job_id] = snapshot
            return deepcopy(snapshot)

    def mark_completed(
        self,
        job_id: str,
        result: Dict[str, Any],
        stats: Optional[Dict[str, Any]] = None,
        execution_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock:
            snapshot = self._jobs.get(job_id) or self.create_job(job_id)
            snapshot.update(
                {
                    "status": "completed",
                    "phase": "completed",
                    "stage": "completed",
                    "progress": 100,
                    "message": "Pipeline completado",
                    "result": result,
                    "stats": stats,
                    "completed_at": now,
                    "updated_at": now,
                    "last_contact_at": now,
                    "terminal_reason": "completed",
                }
            )
            if execution_mode:
                snapshot["execution_mode"] = execution_mode
            self._jobs[job_id] = snapshot
            return deepcopy(snapshot)

    def mark_failed(
        self,
        job_id: str,
        error_code: str,
        message: str,
        *,
        stage: Optional[str] = None,
        execution_mode: Optional[str] = None,
        terminal_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock:
            snapshot = self._jobs.get(job_id) or self.create_job(job_id)
            snapshot.update(
                {
                    "status": "failed",
                    "phase": "error",
                    "stage": stage or snapshot.get("stage") or "error",
                    "progress": max(int(snapshot.get("progress", 0)), 0),
                    "message": message,
                    "error": message,
                    "error_code": error_code,
                    "completed_at": now,
                    "updated_at": now,
                    "last_contact_at": now,
                    "terminal_reason": terminal_reason or "failed",
                }
            )
            if execution_mode:
                snapshot["execution_mode"] = execution_mode
            self._jobs[job_id] = snapshot
            return deepcopy(snapshot)

    def mark_cancelled(self, job_id: str, message: str = "Job cancelado por el usuario") -> Dict[str, Any]:
        now = _utc_now()
        with self._lock:
            snapshot = self._jobs.get(job_id) or self.create_job(job_id)
            snapshot.update(
                {
                    "status": "cancelled",
                    "phase": "cancelled",
                    "stage": "cancelled",
                    "progress": 100,
                    "message": message,
                    "completed_at": now,
                    "updated_at": now,
                    "last_contact_at": now,
                    "terminal_reason": "cancelled",
                }
            )
            self._jobs[job_id] = snapshot
            return deepcopy(snapshot)

    def mark_lost(self, job_id: str, message: str = "Job perdido por desconexion prolongada") -> Dict[str, Any]:
        return self.mark_failed(
            job_id=job_id,
            error_code="JOB_LOST",
            message=message,
            terminal_reason="lost",
        )

    def touch_ws(self, job_id: str) -> None:
        now = _utc_now()
        with self._lock:
            if job_id not in self._jobs:
                return
            self._jobs[job_id]["last_ws_seen_at"] = now

    def update_from_db_row(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        algorithm: Optional[str] = None,
        created_at: Any = None,
        started_at: Any = None,
        completed_at: Any = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        stats: Optional[Dict[str, Any]] = None,
        execution_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        with self._lock:
            snapshot = self._jobs.get(job_id) or self.create_job(job_id)
            if status:
                snapshot["status"] = status
                snapshot["phase"] = status if status != "failed" else "error"
                snapshot["stage"] = snapshot.get("stage") or status
            if algorithm is not None:
                snapshot["algorithm"] = algorithm
            if created_at is not None:
                snapshot["created_at"] = created_at
            if started_at is not None:
                snapshot["started_at"] = started_at
            if completed_at is not None:
                snapshot["completed_at"] = completed_at
            if error is not None:
                snapshot["error"] = error
                if status in {"failed", "error"}:
                    snapshot["message"] = error
            if result is not None:
                snapshot["result"] = result
            if stats is not None:
                snapshot["stats"] = stats
            if execution_mode is not None:
                snapshot["execution_mode"] = execution_mode
            snapshot["updated_at"] = now
            snapshot["last_contact_at"] = now
            self._jobs[job_id] = snapshot
            return deepcopy(snapshot)

    def get_snapshot(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            snapshot = self._jobs.get(job_id)
            return deepcopy(snapshot) if snapshot else None

    def remove(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def cleanup(self) -> List[str]:
        now = _utc_now()
        removed: List[str] = []
        with self._lock:
            for job_id, snapshot in list(self._jobs.items()):
                status = str(snapshot.get("status", ""))
                updated_at = snapshot.get("updated_at") or snapshot.get("created_at")
                if not isinstance(updated_at, datetime):
                    continue
                if status in TERMINAL_STATUSES and (now - updated_at) > self._terminal_ttl:
                    removed.append(job_id)
                    self._jobs.pop(job_id, None)
        return removed

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._jobs)
            terminal = sum(1 for job in self._jobs.values() if str(job.get("status")) in TERMINAL_STATUSES)
            return {"cached_jobs": total, "terminal_jobs": terminal, "active_jobs": max(0, total - terminal)}

    def serialize_status(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": str(snapshot.get("job_id")),
            "status": str(snapshot.get("status", "unknown")),
            "algorithm": snapshot.get("algorithm"),
            "created_at": _iso(snapshot.get("created_at")),
            "started_at": _iso(snapshot.get("started_at")),
            "completed_at": _iso(snapshot.get("completed_at")),
            "error": snapshot.get("error"),
            "stage": snapshot.get("stage"),
            "phase": snapshot.get("phase"),
            "progress": int(snapshot.get("progress", 0) or 0),
            "message": snapshot.get("message"),
            "updated_at": _iso(snapshot.get("updated_at")),
            "execution_mode": snapshot.get("execution_mode", "local"),
            "persisted": bool(snapshot.get("persisted", False)),
            "terminal_reason": snapshot.get("terminal_reason"),
        }

    def serialize_result(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = self.serialize_status(snapshot)
        status = payload["status"]
        if status == "completed":
            payload["result"] = snapshot.get("result")
            payload["stats"] = snapshot.get("stats")
        elif status in {"failed", "error", "cancelled", "lost"}:
            payload["error"] = snapshot.get("error") or snapshot.get("message")
        return payload


runtime_job_store = JobRuntimeStore()

