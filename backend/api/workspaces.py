"""
Workspace API.

Provides versioned optimization workspaces with save/publish semantics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, status

from db import crud as db_crud
from db import schemas
from db.database import SessionLocal, create_tables, is_database_available
from db.models import (
    OptimizationWorkspaceModel,
    OptimizationWorkspaceVersionModel,
    PublishedFleetAssignmentModel,
)
from services.fleet_publication import (
    preview_workspace_publication,
    persist_publication_assignments,
)
from services.fleet_repository import FleetRepository
from services.fleet_scope import resolve_workspace_fleet_scope
from services.workspace_options import (
    DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS,
    get_workspace_optimization_options,
    sanitize_workspace_optimization_options,
    set_workspace_optimization_options,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
fleet_repository = FleetRepository()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _workspace_status_value(workspace: OptimizationWorkspaceModel) -> str:
    if workspace.archived:
        return "inactive"
    if workspace.published_version_id and (
        workspace.working_version_id is None
        or workspace.published_version_id == workspace.working_version_id
    ):
        return "active"
    return "draft"


def _has_schedule_payload(version: Optional[OptimizationWorkspaceVersionModel]) -> bool:
    schedule_by_day = _safe_dict(version.schedule_by_day if version is not None else None)
    for day_payload in schedule_by_day.values():
        if isinstance(day_payload, dict) and isinstance(day_payload.get("schedule"), list) and day_payload.get("schedule"):
            return True
        if isinstance(day_payload, list) and day_payload:
            return True
    return False


def _build_scope_summary(
    workspace: OptimizationWorkspaceModel,
    fleet_snapshot: Dict[str, Any],
) -> schemas.WorkspaceScopeSummary:
    scope_mode = str(fleet_snapshot.get("scope_mode") or "company").strip().lower()
    scope_company_ids = [
        str(company_id).strip()
        for company_id in _safe_list(fleet_snapshot.get("scope_company_ids"))
        if str(company_id).strip()
    ]
    company_id = str(
        fleet_snapshot.get("company_id")
        or workspace.company_id
        or db_crud.DEFAULT_COMPANY_ID
    ).strip()
    if not scope_company_ids:
        scope_company_ids = [company_id]
    ute_name = str(fleet_snapshot.get("ute_name") or "").strip() or None
    label = f"UTE · {ute_name}" if scope_mode == "ute" and ute_name else (
        "UTE" if scope_mode == "ute" else "Empresa"
    )
    return schemas.WorkspaceScopeSummary(
        mode="ute" if scope_mode == "ute" else "company",
        label=label,
        company_id=company_id or None,
        company_count=max(1, len(scope_company_ids)),
        ute_id=str(fleet_snapshot.get("ute_id") or "").strip() or None,
        ute_name=ute_name,
    )


def _build_readiness_summary(workspace: OptimizationWorkspaceModel) -> schemas.WorkspaceReadinessSummary:
    status_value = _workspace_status_value(workspace)
    working = workspace.working_version
    published = workspace.published_version
    source_version = working or published
    source_summary = _safe_dict(source_version.summary_metrics if source_version is not None else None)
    fleet_snapshot = _safe_dict(source_version.fleet_snapshot if source_version is not None else None)
    reconciliation = _safe_dict(fleet_snapshot.get("reconciliation"))
    conflicts = _safe_list(fleet_snapshot.get("conflicts"))
    pending_virtual_count = int(
        reconciliation.get("pending_count")
        or fleet_snapshot.get("virtual_created")
        or source_summary.get("fleet_virtual_created")
        or source_summary.get("fleet_virtual_buses")
        or 0
    )
    conflict_count = len(conflicts)
    virtual_policy = str(
        fleet_snapshot.get("virtual_publish_policy")
        or source_summary.get("fleet_virtual_publish_policy")
        or "allow"
    ).strip().lower()
    scope_summary = _build_scope_summary(workspace, fleet_snapshot)
    has_schedule = _has_schedule_payload(working or published)

    workflow_stage = "draft"
    readiness_state: schemas.ReadinessState = "warning"
    blocking_reason: Optional[str] = None
    next_action: schemas.NextRecommendedAction = "review"

    if status_value == "inactive":
        workflow_stage = "archived"
        readiness_state = "warning"
        blocking_reason = "workspace_archived"
        next_action = "review"
    elif status_value == "active":
        workflow_stage = "published"
        readiness_state = "published"
        next_action = "review"
    elif not has_schedule:
        workflow_stage = "draft"
        readiness_state = "warning"
        blocking_reason = "no_schedule"
        next_action = "optimize"
    elif conflict_count > 0:
        workflow_stage = "blocked_conflict"
        readiness_state = "blocked"
        blocking_reason = "fleet_conflict"
        next_action = "resolve_conflict"
    elif pending_virtual_count > 0 and virtual_policy == "block":
        workflow_stage = "pending_reconciliation"
        readiness_state = "warning"
        blocking_reason = "virtual_reconciliation_required"
        next_action = "reconcile"
    else:
        workflow_stage = "ready_to_publish"
        readiness_state = "ready"
        next_action = "publish"

    return schemas.WorkspaceReadinessSummary(
        workflow_stage=workflow_stage,
        readiness_state=readiness_state,
        blocking_reason=blocking_reason,
        next_recommended_action=next_action,
        pending_virtual_count=max(0, pending_virtual_count),
        conflict_count=max(0, conflict_count),
        scope_summary=scope_summary,
    )


def _ensure_tables_ready() -> None:
    if not is_database_available():
        return
    try:
        create_tables()
    except Exception:
        # best effort; endpoint logic will return proper errors if DB is unusable
        pass


def _to_version_response(version: Optional[OptimizationWorkspaceVersionModel]) -> Optional[schemas.WorkspaceVersionDetailResponse]:
    if version is None:
        return None
    fleet_snapshot = version.fleet_snapshot if isinstance(version.fleet_snapshot, dict) else None
    publication = None
    if isinstance(fleet_snapshot, dict):
        publication = schemas.FleetPublicationSummary(
            company_id=fleet_snapshot.get("company_id"),
            scope_mode=fleet_snapshot.get("scope_mode"),
            scope_company_ids=(
                fleet_snapshot.get("scope_company_ids", [])
                if isinstance(fleet_snapshot.get("scope_company_ids"), list)
                else []
            ),
            ute_id=fleet_snapshot.get("ute_id"),
            ute_name=fleet_snapshot.get("ute_name"),
            real_assigned=int(fleet_snapshot.get("real_assigned", 0) or 0),
            virtual_created=int(fleet_snapshot.get("virtual_created", 0) or 0),
            conflicts=fleet_snapshot.get("conflicts", []) if isinstance(fleet_snapshot.get("conflicts"), list) else [],
            blocked=bool(fleet_snapshot.get("blocked", False)),
            days=fleet_snapshot.get("days", {}) if isinstance(fleet_snapshot.get("days"), dict) else {},
        )
    return schemas.WorkspaceVersionDetailResponse(
        id=str(version.id),
        workspace_id=str(version.workspace_id),
        version_number=int(version.version_number or 0),
        save_kind=version.save_kind,  # type: ignore[arg-type]
        checkpoint_name=version.checkpoint_name,
        created_at=version.created_at,
        routes_payload=version.routes_payload,
        schedule_by_day=db_crud.normalize_schedule_by_day(version.schedule_by_day or {}),
        parse_report=version.parse_report if isinstance(version.parse_report, dict) else None,
        validation_report=version.validation_report if isinstance(version.validation_report, dict) else None,
        fleet_snapshot=fleet_snapshot,
        fleet_publication=publication,
        summary_metrics=version.summary_metrics if isinstance(version.summary_metrics, dict) else None,
    )


def _to_workspace_response(workspace: OptimizationWorkspaceModel) -> schemas.WorkspaceResponse:
    working = workspace.working_version
    published = workspace.published_version
    status_value = _workspace_status_value(workspace)
    readiness_summary = _build_readiness_summary(workspace)
    return schemas.WorkspaceResponse(
        id=str(workspace.id),
        company_id=str(workspace.company_id or "") or None,
        name=str(workspace.name or ""),
        city_label=workspace.city_label,
        archived=bool(workspace.archived),
        status=status_value,  # type: ignore[arg-type]
        published_version_id=str(workspace.published_version_id) if workspace.published_version_id else None,
        working_version_id=str(workspace.working_version_id) if workspace.working_version_id else None,
        published_version_number=int(published.version_number) if published else None,
        working_version_number=int(working.version_number) if working else None,
        version_count=len(workspace.versions or []),
        summary_metrics=(working.summary_metrics if working and isinstance(working.summary_metrics, dict) else None),
        workflow_stage=readiness_summary.workflow_stage,
        readiness_state=readiness_summary.readiness_state,
        blocking_reason=readiness_summary.blocking_reason,
        next_recommended_action=readiness_summary.next_recommended_action,
        pending_virtual_count=readiness_summary.pending_virtual_count,
        conflict_count=readiness_summary.conflict_count,
        scope_summary=readiness_summary.scope_summary,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def _to_workspace_detail_response(workspace: OptimizationWorkspaceModel) -> schemas.WorkspaceDetailResponse:
    base = _to_workspace_response(workspace)
    readiness_summary = _build_readiness_summary(workspace)
    return schemas.WorkspaceDetailResponse(
        **base.model_dump(),
        working_version=_to_version_response(workspace.working_version),
        published_version=_to_version_response(workspace.published_version),
        readiness_summary=readiness_summary,
    )


def _workspace_company_id(db, workspace: OptimizationWorkspaceModel) -> str:
    default_company = db_crud.ensure_default_company(db)
    company_id = str(workspace.company_id or "").strip() or str(default_company.id)
    return company_id


def _repair_workspace_primary_company(db, workspace: OptimizationWorkspaceModel) -> OptimizationWorkspaceModel:
    """
    Repair legacy workspaces still bound to the placeholder default company.

    If `company_main` has no active fleet and there is a single active UTE,
    promote that UTE owner as the workspace primary company.
    """
    default_company = db_crud.ensure_default_company(db)
    current_company_id = str(workspace.company_id or "").strip() or str(default_company.id)
    if current_company_id != str(default_company.id):
        return workspace

    default_vehicle_count = len(fleet_repository.list_active_profiles(company_id=str(default_company.id)))
    if default_vehicle_count > 0:
        return workspace

    active_utes = db_crud.list_utes(db, active_only=True)
    if len(active_utes) != 1:
        return workspace

    owner_company_id = str(active_utes[0].owner_company_id or "").strip()
    if not owner_company_id or owner_company_id == str(default_company.id):
        return workspace

    workspace.company_id = owner_company_id
    workspace.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workspace)
    return workspace


def _build_scope_label(scope_mode: Any, ute_name: Any = None) -> str:
    normalized_mode = str(scope_mode or "company").strip().lower()
    normalized_ute_name = str(ute_name or "").strip()
    if normalized_mode == "ute":
        return f"UTE · {normalized_ute_name}" if normalized_ute_name else "UTE"
    return "Empresa"


def _normalize_reconciliation_payload(reconciliation: Dict[str, Any]) -> Dict[str, Any]:
    normalized = reconciliation if isinstance(reconciliation, dict) else {}
    items = normalized.get("items", []) if isinstance(normalized.get("items"), list) else []
    normalized_items: List[Dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        normalized_items.append(
            {
                **row,
                "required_capacity": int(row.get("required_seats", 0) or 0),
                "time_window": {
                    "start_minute": int(row.get("start_minute", 0) or 0),
                    "end_minute": int(row.get("end_minute", 0) or 0),
                },
                "suggested_real_vehicles": row.get("suggestions", []) if isinstance(row.get("suggestions"), list) else [],
            }
        )
    by_day = normalized.get("by_day", {}) if isinstance(normalized.get("by_day"), dict) else {}
    company_mix = normalized.get("company_mix", {}) if isinstance(normalized.get("company_mix"), dict) else {}

    normalized_days: Dict[str, Any] = {}
    for day_key, day_payload in by_day.items():
        if not isinstance(day_payload, dict):
            normalized_days[day_key] = {"pending_virtual": 0, "items": [], "company_mix": {"total_pending_buses": 0, "recommended_companies": [], "companies_with_options": 0, "uncovered_buses": 0}}
            continue
        day_company_mix = day_payload.get("company_mix", {}) if isinstance(day_payload.get("company_mix"), dict) else {}
        normalized_days[day_key] = {
            **day_payload,
            "company_mix": {
                "total_pending_buses": int(day_company_mix.get("total_pending_buses", 0) or 0),
                "recommended_companies": day_company_mix.get("recommended_companies", []) if isinstance(day_company_mix.get("recommended_companies"), list) else [],
                "companies_with_options": int(day_company_mix.get("companies_with_options", 0) or 0),
                "uncovered_buses": int(day_company_mix.get("uncovered_buses", 0) or 0),
            },
        }

    return {
        **normalized,
        "items": normalized_items,
        "days": normalized_days,
        "pending_assignments": normalized_items,
        "company_mix": {
            "total_pending_buses": int(company_mix.get("total_pending_buses", 0) or 0),
            "recommended_companies": company_mix.get("recommended_companies", []) if isinstance(company_mix.get("recommended_companies"), list) else [],
            "companies_with_options": int(company_mix.get("companies_with_options", 0) or 0),
            "uncovered_buses": int(company_mix.get("uncovered_buses", 0) or 0),
        },
    }


def _reconciliation_key(day: Any, bus_id: Any) -> str:
    return f"{str(day or '').strip()}::{str(bus_id or '').strip()}"


def _select_reconciliation_assignments(
    rows: List[Dict[str, Any]],
    company_targets: Optional[Dict[str, int]] = None,
    bus_preferences: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_targets = {
        str(company_id or "unassigned"): max(0, int(count or 0))
        for company_id, count in (company_targets or {}).items()
    }
    remaining_targets = dict(normalized_targets)
    normalized_preferences = bus_preferences if isinstance(bus_preferences, dict) else {}
    selected_windows: Dict[str, Dict[str, List[List[int]]]] = {}
    selected_assignments: Dict[str, Dict[str, Any]] = {}
    unresolved: List[Dict[str, Any]] = []

    ordered_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: (
            len(row.get("suggested_real_vehicles", []) if isinstance(row.get("suggested_real_vehicles"), list) else []),
            -int(row.get("required_capacity", row.get("required_seats", 0)) or 0),
            int((row.get("time_window") or {}).get("start_minute", row.get("start_minute", 0)) or 0),
            str(row.get("bus_id", "")),
        ),
    )

    def _candidate_available(row: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
        vehicle_id = str(candidate.get("vehicle_id", "") or "").strip()
        day = str(row.get("day", "") or "").strip()
        if not vehicle_id or not day:
            return False
        time_window = row.get("time_window", {}) if isinstance(row.get("time_window"), dict) else {}
        start_minute = int(time_window.get("start_minute", row.get("start_minute", 0)) or 0)
        end_minute = int(time_window.get("end_minute", row.get("end_minute", 0)) or 0)
        if end_minute <= start_minute:
            end_minute = start_minute + 1
        vehicle_windows = selected_windows.get(vehicle_id, {}).get(day, [])
        return all(
            not ((start_minute < existing_end) and (end_minute > existing_start))
            for existing_start, existing_end in vehicle_windows
        )

    def _normalize_candidate_company(candidate: Dict[str, Any]) -> str:
        return str(candidate.get("company_id") or "unassigned")

    for row in ordered_rows:
        suggestions = row.get("suggested_real_vehicles", []) if isinstance(row.get("suggested_real_vehicles"), list) else []
        row_key = _reconciliation_key(row.get("day"), row.get("bus_id"))
        preference = normalized_preferences.get(row_key, {}) if isinstance(normalized_preferences.get(row_key), dict) else {}
        excluded_vehicle_ids = {
            str(vehicle_id).strip()
            for vehicle_id in (preference.get("excluded_vehicle_ids") or [])
            if str(vehicle_id).strip()
        }
        preferred_vehicle_id = str(preference.get("vehicle_id") or "").strip()
        preferred_company_id = str(preference.get("company_id") or "").strip()
        if excluded_vehicle_ids:
            suggestions = [
                candidate
                for candidate in suggestions
                if str(candidate.get("vehicle_id") or "").strip() not in excluded_vehicle_ids
            ]
        chosen: Optional[Dict[str, Any]] = None
        if preferred_vehicle_id:
            exact_match = next(
                (
                    candidate for candidate in suggestions
                    if str(candidate.get("vehicle_id") or "").strip() == preferred_vehicle_id
                ),
                None,
            )
            if exact_match is not None and _candidate_available(row, exact_match):
                chosen = exact_match
            else:
                unresolved.append(
                    {
                        "day": row.get("day"),
                        "bus_id": row.get("bus_id"),
                        "required_capacity": int(row.get("required_capacity", row.get("required_seats", 0)) or 0),
                        "reason": "preferred_vehicle_unavailable",
                        "preferred_vehicle_id": preferred_vehicle_id,
                    }
                )
                continue
        if chosen is None and preferred_company_id:
            preferred_company_candidates = [
                candidate
                for candidate in suggestions
                if _normalize_candidate_company(candidate) == preferred_company_id
            ]
            for candidate in preferred_company_candidates:
                if _candidate_available(row, candidate):
                    chosen = candidate
                    break
        if remaining_targets:
            prioritized = [
                candidate
                for candidate in suggestions
                if remaining_targets.get(_normalize_candidate_company(candidate), 0) > 0
            ]
            if chosen is None:
                for candidate in prioritized:
                    if _candidate_available(row, candidate):
                        chosen = candidate
                        break
        if chosen is None:
            for candidate in suggestions:
                if _candidate_available(row, candidate):
                    chosen = candidate
                    break

        if chosen is None:
            unresolved.append(
                {
                    "day": row.get("day"),
                    "bus_id": row.get("bus_id"),
                    "required_capacity": int(row.get("required_capacity", row.get("required_seats", 0)) or 0),
                }
            )
            continue

        selected_assignments[row_key] = chosen
        vehicle_id = str(chosen.get("vehicle_id") or "").strip()
        day = str(row.get("day") or "").strip()
        time_window = row.get("time_window", {}) if isinstance(row.get("time_window"), dict) else {}
        start_minute = int(time_window.get("start_minute", row.get("start_minute", 0)) or 0)
        end_minute = int(time_window.get("end_minute", row.get("end_minute", 0)) or 0)
        if end_minute <= start_minute:
            end_minute = start_minute + 1
        selected_windows.setdefault(vehicle_id, {}).setdefault(day, []).append([start_minute, end_minute])
        company_key = _normalize_candidate_company(chosen)
        if remaining_targets.get(company_key, 0) > 0:
            remaining_targets[company_key] -= 1

    applied_by_company: Dict[str, Dict[str, Any]] = {}
    for candidate in selected_assignments.values():
        company_key = str(candidate.get("company_id") or "unassigned")
        entry = applied_by_company.setdefault(
            company_key,
            {
                "company_id": candidate.get("company_id"),
                "company_name": candidate.get("company_name"),
                "assigned_count": 0,
            },
        )
        entry["assigned_count"] += 1

    return {
        "selected_assignments": selected_assignments,
        "unresolved": unresolved,
        "remaining_targets": remaining_targets,
        "applied_by_company": list(applied_by_company.values()),
    }


def _apply_reconciliation_assignments_to_schedule(
    schedule_by_day: Dict[str, Any],
    selected_assignments: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_schedule = db_crud.normalize_schedule_by_day(schedule_by_day or {})
    for day, day_payload in normalized_schedule.items():
        buses = day_payload.get("schedule", []) if isinstance(day_payload, dict) else []
        if not isinstance(buses, list):
            continue
        for bus in buses:
            if not isinstance(bus, dict):
                continue
            key = _reconciliation_key(day, bus.get("bus_id"))
            assignment = selected_assignments.get(key)
            if not isinstance(assignment, dict):
                continue
            bus["uses_fleet_profile"] = True
            bus["fleet_assignment_type"] = "real"
            bus["fleet_binding_state"] = "preview"
            bus["assigned_vehicle_id"] = str(assignment.get("vehicle_id") or "") or None
            bus["assigned_vehicle_code"] = str(assignment.get("vehicle_code") or "") or None
            bus["assigned_vehicle_plate"] = str(assignment.get("plate") or "") or None
            bus["assigned_company_id"] = str(assignment.get("company_id") or "") or None
            bus["assigned_company_name"] = str(assignment.get("company_name") or "") or None
            bus["assigned_vehicle_seats_base"] = int(assignment.get("seats_base", assignment.get("seats_min", 0)) or 0) or None
            bus["assigned_vehicle_seats_pmr"] = int(assignment.get("seats_pmr", 0) or 0)
            bus["assigned_vehicle_seats_min"] = int(assignment.get("seats_min", 0) or 0) or None
            bus["assigned_vehicle_seats_max"] = int(assignment.get("seats_max", 0) or 0) or None
    return normalized_schedule


def _build_publish_payload(
    workspace: OptimizationWorkspaceModel,
    payload: schemas.WorkspaceVersionCreate,
) -> schemas.WorkspaceVersionCreate:
    working = workspace.working_version
    schedule_by_day = payload.schedule_by_day
    if schedule_by_day is None and working is not None and isinstance(working.schedule_by_day, dict):
        schedule_by_day = working.schedule_by_day

    routes_payload = payload.routes_payload
    if routes_payload is None and working is not None:
        routes_payload = working.routes_payload

    parse_report = payload.parse_report
    if parse_report is None and working is not None and isinstance(working.parse_report, dict):
        parse_report = working.parse_report

    validation_report = payload.validation_report
    if validation_report is None and working is not None and isinstance(working.validation_report, dict):
        validation_report = working.validation_report

    summary_metrics = payload.summary_metrics
    if summary_metrics is None and working is not None and isinstance(working.summary_metrics, dict):
        summary_metrics = working.summary_metrics

    return payload.model_copy(
        update={
            "save_kind": "publish",
            "routes_payload": routes_payload,
            "schedule_by_day": schedule_by_day or {},
            "parse_report": parse_report,
            "validation_report": validation_report,
            "summary_metrics": summary_metrics,
        }
    )


@router.get("", response_model=schemas.WorkspaceListResponse)
async def list_workspaces(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    q: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    updated_from: Optional[datetime] = Query(default=None),
) -> schemas.WorkspaceListResponse:
    """List workspaces with optional filters."""
    if not is_database_available() or SessionLocal is None:
        return schemas.WorkspaceListResponse(items=[], total=0)
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspaces = db_crud.list_workspaces(
            db,
            status=status_filter,
            q=q,
            city=city,
            updated_from=updated_from,
        )
        workspaces = [_repair_workspace_primary_company(db, ws) for ws in workspaces]
        items = [_to_workspace_response(ws) for ws in workspaces]
        return schemas.WorkspaceListResponse(items=items, total=len(items))
    finally:
        db.close()


@router.post("", response_model=schemas.WorkspaceDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: schemas.WorkspaceCreateRequest = Body(...),
) -> schemas.WorkspaceDetailResponse:
    """Create a workspace and optional initial snapshot."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.create_workspace(db, payload)
        db_crud.set_app_meta(db, "last_open_workspace_id", str(workspace.id))
        hydrated = db_crud.get_workspace(db, str(workspace.id))
        if hydrated is None:
            raise HTTPException(status_code=500, detail="Workspace created but not readable")
        return _to_workspace_detail_response(hydrated)
    finally:
        db.close()


@router.get("/preferences")
async def get_workspace_preferences() -> Dict[str, Any]:
    """Get app-level workspace preferences."""
    if not is_database_available() or SessionLocal is None:
        return {"last_open_workspace_id": None}
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        meta = db_crud.get_app_meta(db, "last_open_workspace_id")
        value = meta.value if meta else None
        if isinstance(value, dict):
            value = value.get("workspace_id")
        if value is not None:
            value = str(value)
        return {"last_open_workspace_id": value}
    finally:
        db.close()


@router.post("/preferences/last-open")
async def set_last_open_workspace(workspace_id: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Persist last opened workspace."""
    if not is_database_available() or SessionLocal is None:
        return {"success": False, "workspace_id": workspace_id}
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        db_crud.set_app_meta(db, "last_open_workspace_id", workspace_id)
        return {"success": True, "workspace_id": workspace_id}
    finally:
        db.close()


@router.get(
    "/{workspace_id}/optimization-options",
    response_model=schemas.WorkspaceOptimizationOptions,
)
async def get_workspace_options(workspace_id: str) -> schemas.WorkspaceOptimizationOptions:
    """Get persisted optimization options for a workspace."""
    if not is_database_available() or SessionLocal is None:
        return schemas.WorkspaceOptimizationOptions(**DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS)
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        options = get_workspace_optimization_options(db, workspace_id)
        return schemas.WorkspaceOptimizationOptions(**options)
    finally:
        db.close()


@router.post(
    "/{workspace_id}/optimization-options",
    response_model=schemas.WorkspaceOptimizationOptions,
)
async def set_workspace_options(
    workspace_id: str,
    payload: schemas.WorkspaceOptimizationOptions = Body(default_factory=schemas.WorkspaceOptimizationOptions),
) -> schemas.WorkspaceOptimizationOptions:
    """Persist optimization options for a workspace."""
    if not is_database_available() or SessionLocal is None:
        normalized = sanitize_workspace_optimization_options(payload.model_dump())
        return schemas.WorkspaceOptimizationOptions(**normalized)
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        options = set_workspace_optimization_options(db, workspace_id, payload.model_dump())
        return schemas.WorkspaceOptimizationOptions(**options)
    finally:
        db.close()


@router.get("/{workspace_id}", response_model=schemas.WorkspaceDetailResponse)
async def get_workspace(workspace_id: str) -> schemas.WorkspaceDetailResponse:
    """Get workspace details and working/published snapshots."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        db_crud.set_app_meta(db, "last_open_workspace_id", workspace_id)
        return _to_workspace_detail_response(workspace)
    finally:
        db.close()


@router.get("/{workspace_id}/versions")
async def list_workspace_versions(workspace_id: str) -> Dict[str, Any]:
    """List workspace versions (metadata only)."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        versions = db_crud.get_workspace_versions(db, workspace_id)
        return {
            "workspace_id": workspace_id,
            "items": [
                schemas.WorkspaceVersionResponse(
                    id=str(v.id),
                    workspace_id=str(v.workspace_id),
                    version_number=int(v.version_number or 0),
                    save_kind=v.save_kind,  # type: ignore[arg-type]
                    checkpoint_name=v.checkpoint_name,
                    created_at=v.created_at,
                    summary_metrics=v.summary_metrics if isinstance(v.summary_metrics, dict) else None,
                ).model_dump()
                for v in versions
            ],
            "total": len(versions),
        }
    finally:
        db.close()


@router.get("/{workspace_id}/versions/{version_id}", response_model=schemas.WorkspaceVersionDetailResponse)
async def get_workspace_version(
    workspace_id: str,
    version_id: str,
) -> schemas.WorkspaceVersionDetailResponse:
    """Get full workspace version snapshot."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        version = db_crud.get_workspace_version(db, workspace_id, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Version not found")
        response = _to_version_response(version)
        if response is None:
            raise HTTPException(status_code=500, detail="Version serialization failed")
        return response
    finally:
        db.close()


@router.post("/{workspace_id}/save", response_model=schemas.WorkspaceVersionDetailResponse)
async def save_workspace(
    workspace_id: str,
    payload: schemas.WorkspaceVersionCreate = Body(default_factory=schemas.WorkspaceVersionCreate),
) -> schemas.WorkspaceVersionDetailResponse:
    """Create a save/autosave snapshot and update working pointer."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        normalized = payload.model_copy(update={"save_kind": payload.save_kind or "save"})
        if normalized.save_kind not in {"save", "autosave", "migration"}:
            normalized = normalized.model_copy(update={"save_kind": "save"})
        version = db_crud.create_workspace_version(db, workspace_id, normalized)
        if version is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        response = _to_version_response(version)
        if response is None:
            raise HTTPException(status_code=500, detail="Version serialization failed")
        return response
    finally:
        db.close()


@router.get("/{workspace_id}/fleet-preview")
async def get_workspace_fleet_preview(
    workspace_id: str,
    day: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Preview real/virtual fleet assignment for current working schedule."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        working_version = workspace.working_version or workspace.published_version
        if working_version is None:
            raise HTTPException(status_code=409, detail="Workspace has no version to preview")
        schedule_by_day = db_crud.normalize_schedule_by_day(working_version.schedule_by_day or {})
        scope = resolve_workspace_fleet_scope(db, workspace)
        options = get_workspace_optimization_options(db, workspace_id)
        virtual_policy = str(options.get("virtual_bus_publish_policy", "allow") or "allow").strip().lower()
        if virtual_policy not in {"allow", "block"}:
            virtual_policy = "allow"
        company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, workspace))
        scope_company_ids = [
            str(cid) for cid in (scope.get("scope_company_ids") or [])
            if str(cid).strip()
        ]
        scope_vehicle_count = len(fleet_repository.list_active_profiles(company_id=company_id, company_ids=scope_company_ids))
        scope_company_names = scope.get("scope_company_names") if isinstance(scope.get("scope_company_names"), dict) else {}
        preview = preview_workspace_publication(
            db,
            company_id=company_id,
            scope_company_ids=scope_company_ids,
            schedule_by_day=schedule_by_day,
            exclude_workspace_id=str(workspace.id),
        )
        normalized_reconciliation = _normalize_reconciliation_payload(
            preview.get("reconciliation", {}) if isinstance(preview.get("reconciliation"), dict) else {}
        )
        scope_label = _build_scope_label(scope.get("scope_mode"), scope.get("ute_name"))
        if day and day in preview.get("schedule_by_day", {}):
            return {
                "workspace_id": workspace_id,
                "company_id": company_id,
                "scope_mode": scope.get("scope_mode"),
                "scope_label": scope_label,
                "scope_company_ids": scope_company_ids,
                "scope_company_names": scope_company_names,
                "scope_vehicle_count": scope_vehicle_count,
                "ute_id": scope.get("ute_id"),
                "ute_name": scope.get("ute_name"),
                "day": day,
                "blocked": bool(preview.get("blocked", False)),
                "conflicts": [c for c in preview.get("conflicts", []) if c.get("day") == day],
                "real_assigned": int(preview.get("real_assigned", 0)),
                "virtual_created": int(preview.get("virtual_created", 0)),
                "virtual_publish_policy": virtual_policy,
                "requires_reconciliation": bool(
                    virtual_policy == "block"
                    and int(preview.get("virtual_created", 0) or 0) > 0
                ),
                "day_payload": preview.get("schedule_by_day", {}).get(day, {}),
                "reconciliation": normalized_reconciliation,
                "days": preview.get("days", {}),
            }
        return {
            "workspace_id": workspace_id,
            "company_id": company_id,
            "scope_mode": scope.get("scope_mode"),
            "scope_label": scope_label,
            "scope_company_ids": scope_company_ids,
            "scope_company_names": scope_company_names,
            "scope_vehicle_count": scope_vehicle_count,
            "ute_id": scope.get("ute_id"),
            "ute_name": scope.get("ute_name"),
            "blocked": bool(preview.get("blocked", False)),
            "conflicts": preview.get("conflicts", []),
            "real_assigned": int(preview.get("real_assigned", 0)),
            "virtual_created": int(preview.get("virtual_created", 0)),
            "virtual_publish_policy": virtual_policy,
            "requires_reconciliation": bool(
                virtual_policy == "block"
                and int(preview.get("virtual_created", 0) or 0) > 0
            ),
            "schedule_by_day": preview.get("schedule_by_day", {}),
            "reconciliation": normalized_reconciliation,
            "days": preview.get("days", {}),
        }
    finally:
        db.close()


@router.get("/{workspace_id}/fleet-reconciliation")
async def get_workspace_fleet_reconciliation(
    workspace_id: str,
    day: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Get pending virtual buses and candidate real replacements (post-optimization reconciliation)."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        working_version = workspace.working_version or workspace.published_version
        if working_version is None:
            raise HTTPException(status_code=409, detail="Workspace has no version to reconcile")

        schedule_by_day = db_crud.normalize_schedule_by_day(working_version.schedule_by_day or {})
        scope = resolve_workspace_fleet_scope(db, workspace)
        options = get_workspace_optimization_options(db, workspace_id)
        virtual_policy = str(options.get("virtual_bus_publish_policy", "allow") or "allow").strip().lower()
        if virtual_policy not in {"allow", "block"}:
            virtual_policy = "allow"
        company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, workspace))
        scope_company_ids = [
            str(cid) for cid in (scope.get("scope_company_ids") or [])
            if str(cid).strip()
        ]
        scope_vehicle_count = len(fleet_repository.list_active_profiles(company_id=company_id, company_ids=scope_company_ids))
        scope_company_names = scope.get("scope_company_names") if isinstance(scope.get("scope_company_names"), dict) else {}
        preview = preview_workspace_publication(
            db,
            company_id=company_id,
            scope_company_ids=scope_company_ids,
            schedule_by_day=schedule_by_day,
            exclude_workspace_id=str(workspace.id),
        )
        reconciliation = _normalize_reconciliation_payload(
            preview.get("reconciliation", {}) if isinstance(preview.get("reconciliation"), dict) else {}
        )
        response: Dict[str, Any] = {
            "workspace_id": workspace_id,
            "company_id": company_id,
            "scope_mode": scope.get("scope_mode"),
            "scope_label": _build_scope_label(scope.get("scope_mode"), scope.get("ute_name")),
            "scope_company_ids": scope_company_ids,
            "scope_company_names": scope_company_names,
            "scope_vehicle_count": scope_vehicle_count,
            "ute_id": scope.get("ute_id"),
            "ute_name": scope.get("ute_name"),
            "virtual_publish_policy": virtual_policy,
            "requires_reconciliation": bool(
                virtual_policy == "block"
                and int(preview.get("virtual_created", 0) or 0) > 0
            ),
            "real_assigned": int(preview.get("real_assigned", 0)),
            "virtual_created": int(preview.get("virtual_created", 0)),
            "reconciliation": reconciliation,
            "days": reconciliation.get("days", {}),
            "pending_assignments": reconciliation.get("pending_assignments", []),
        }
        if day:
            day_key = str(day)
            by_day = reconciliation.get("days", {}) if isinstance(reconciliation.get("days"), dict) else {}
            response["day"] = day_key
            response["reconciliation_day"] = by_day.get(day_key, {"pending_virtual": 0, "items": []})
        return response
    finally:
        db.close()


@router.post("/{workspace_id}/fleet-reconciliation/apply")
async def apply_workspace_fleet_reconciliation(
    workspace_id: str,
    payload: schemas.FleetReconciliationApplyRequest = Body(default_factory=schemas.FleetReconciliationApplyRequest),
) -> Dict[str, Any]:
    """Apply assisted real-bus reconciliation and persist it into the working workspace version."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        working_version = workspace.working_version or workspace.published_version
        if working_version is None:
            raise HTTPException(status_code=409, detail="Workspace has no version to reconcile")

        schedule_by_day = db_crud.normalize_schedule_by_day(working_version.schedule_by_day or {})
        scope = resolve_workspace_fleet_scope(db, workspace)
        options = get_workspace_optimization_options(db, workspace_id)
        virtual_policy = str(options.get("virtual_bus_publish_policy", "allow") or "allow").strip().lower()
        if virtual_policy not in {"allow", "block"}:
            virtual_policy = "allow"
        company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, workspace))
        scope_company_ids = [
            str(cid) for cid in (scope.get("scope_company_ids") or [])
            if str(cid).strip()
        ]
        scope_vehicle_count = len(fleet_repository.list_active_profiles(company_id=company_id, company_ids=scope_company_ids))
        scope_company_names = scope.get("scope_company_names") if isinstance(scope.get("scope_company_names"), dict) else {}

        preview = preview_workspace_publication(
            db,
            company_id=company_id,
            scope_company_ids=scope_company_ids,
            schedule_by_day=schedule_by_day,
            exclude_workspace_id=str(workspace.id),
        )
        reconciliation = _normalize_reconciliation_payload(
            preview.get("reconciliation", {}) if isinstance(preview.get("reconciliation"), dict) else {}
        )

        requested_day = str(payload.day or "").strip() or None
        target_rows = reconciliation.get("pending_assignments", []) if isinstance(reconciliation.get("pending_assignments"), list) else []
        if requested_day:
            target_rows = [row for row in target_rows if str(row.get("day") or "").strip() == requested_day]
        requested_bus_ids = {
            str(bus_id).strip()
            for bus_id in (payload.bus_ids or [])
            if str(bus_id).strip()
        }
        if requested_bus_ids:
            target_rows = [row for row in target_rows if str(row.get("bus_id") or "").strip() in requested_bus_ids]

        if not target_rows:
            return {
                "workspace_id": workspace_id,
                "applied_count": 0,
                "remaining_pending": int(reconciliation.get("pending_count", 0) or 0),
                "message": "No hay buses provisionales pendientes para el filtro seleccionado.",
                "schedule_by_day": schedule_by_day,
                "reconciliation": reconciliation,
            }

        company_targets = {
            str(row.company_id or "unassigned"): int(row.count or 0)
            for row in (payload.company_allocations or [])
            if int(row.count or 0) > 0
        }
        bus_preferences: Dict[str, Dict[str, Any]] = {}
        for selection in (payload.bus_selections or []):
            key = _reconciliation_key(selection.day or requested_day, selection.bus_id)
            bus_preferences[key] = {
                "company_id": str(selection.company_id or "").strip() or None,
                "vehicle_id": str(selection.vehicle_id or "").strip() or None,
                "excluded_vehicle_ids": [
                    str(vehicle_id).strip()
                    for vehicle_id in (selection.excluded_vehicle_ids or [])
                    if str(vehicle_id).strip()
                ],
            }
        applied = _select_reconciliation_assignments(target_rows, company_targets, bus_preferences)
        selected_assignments = applied.get("selected_assignments", {}) if isinstance(applied.get("selected_assignments"), dict) else {}
        if not selected_assignments:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "No se pudo aplicar la reconciliacion con las empresas seleccionadas",
                    "reason": "reconciliation_assignment_failed",
                    "unresolved": applied.get("unresolved", []),
                },
            )

        updated_schedule = _apply_reconciliation_assignments_to_schedule(schedule_by_day, selected_assignments)
        updated_preview = preview_workspace_publication(
            db,
            company_id=company_id,
            scope_company_ids=scope_company_ids,
            schedule_by_day=updated_schedule,
            exclude_workspace_id=str(workspace.id),
        )

        fleet_snapshot = {
            "company_id": company_id,
            "scope_mode": scope.get("scope_mode"),
            "scope_company_ids": scope_company_ids,
            "scope_company_names": scope_company_names,
            "scope_vehicle_count": scope_vehicle_count,
            "ute_id": scope.get("ute_id"),
            "ute_name": scope.get("ute_name"),
            "real_assigned": int(updated_preview.get("real_assigned", 0)),
            "virtual_created": int(updated_preview.get("virtual_created", 0)),
            "conflicts": updated_preview.get("conflicts", []),
            "blocked": bool(updated_preview.get("blocked", False)),
            "days": updated_preview.get("days", {}),
            "virtual_publish_policy": virtual_policy,
            "reconciliation": updated_preview.get("reconciliation", {}),
        }
        merged_summary = dict(working_version.summary_metrics or {})
        merged_summary["fleet_real_assigned"] = int(updated_preview.get("real_assigned", 0))
        merged_summary["fleet_virtual_created"] = int(updated_preview.get("virtual_created", 0))
        merged_summary["fleet_binding_state"] = "preview"
        merged_summary["fleet_reconciliation_applied_count"] = len(selected_assignments)

        version_payload = schemas.WorkspaceVersionCreate(
            checkpoint_name=payload.checkpoint_name or f"fleet-reconciliation-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            save_kind="save",
            routes_payload=working_version.routes_payload,
            schedule_by_day=updated_preview.get("schedule_by_day", updated_schedule),
            parse_report=working_version.parse_report,
            validation_report=working_version.validation_report,
            fleet_snapshot=fleet_snapshot,
            summary_metrics=merged_summary,
        )
        version = db_crud.create_workspace_version(db, workspace_id, version_payload)
        if version is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        response_version = _to_version_response(version)
        if response_version is None:
            raise HTTPException(status_code=500, detail="Version serialization failed")

        return {
            "workspace_id": workspace_id,
            "applied_count": len(selected_assignments),
            "applied_by_company": applied.get("applied_by_company", []),
            "remaining_targets": applied.get("remaining_targets", {}),
            "unresolved": applied.get("unresolved", []),
            "remaining_pending": int(
                _safe_dict(updated_preview.get("reconciliation")).get("pending_count", 0) or 0
            ),
            "schedule_by_day": updated_preview.get("schedule_by_day", updated_schedule),
            "reconciliation": _normalize_reconciliation_payload(
                updated_preview.get("reconciliation", {}) if isinstance(updated_preview.get("reconciliation"), dict) else {}
            ),
            "fleet_publication": {
                "company_id": company_id,
                "scope_mode": scope.get("scope_mode"),
                "scope_company_ids": scope_company_ids,
                "ute_id": scope.get("ute_id"),
                "ute_name": scope.get("ute_name"),
                "real_assigned": int(updated_preview.get("real_assigned", 0)),
                "virtual_created": int(updated_preview.get("virtual_created", 0)),
                "conflicts": updated_preview.get("conflicts", []),
                "blocked": bool(updated_preview.get("blocked", False)),
                "days": updated_preview.get("days", {}),
            },
            "workspace_version": response_version.model_dump(mode="json"),
        }
    finally:
        db.close()


@router.post("/{workspace_id}/publish", response_model=schemas.WorkspaceVersionDetailResponse)
async def publish_workspace(
    workspace_id: str,
    payload: schemas.WorkspaceVersionCreate = Body(default_factory=schemas.WorkspaceVersionCreate),
) -> schemas.WorkspaceVersionDetailResponse:
    """
    Create publish snapshot + commit operational fleet reservations.
    Blocks on real-vehicle conflicts with other published workspaces.
    """
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)

        scope = resolve_workspace_fleet_scope(db, workspace)
        options = get_workspace_optimization_options(db, workspace_id)
        virtual_policy = str(options.get("virtual_bus_publish_policy", "allow") or "allow").strip().lower()
        if virtual_policy not in {"allow", "block"}:
            virtual_policy = "allow"
        company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, workspace))
        scope_company_ids = [
            str(cid) for cid in (scope.get("scope_company_ids") or [])
            if str(cid).strip()
        ]
        scope_vehicle_count = len(fleet_repository.list_active_profiles(company_id=company_id, company_ids=scope_company_ids))
        publish_payload = _build_publish_payload(workspace, payload)
        normalized_schedule = db_crud.normalize_schedule_by_day(publish_payload.schedule_by_day or {})
        preview = preview_workspace_publication(
            db,
            company_id=company_id,
            scope_company_ids=scope_company_ids,
            schedule_by_day=normalized_schedule,
            exclude_workspace_id=str(workspace.id),
        )
        if bool(preview.get("blocked", False)):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Publicacion bloqueada por conflictos de flota publicados",
                    "fleet_publication": {
                        "company_id": company_id,
                        "scope_mode": scope.get("scope_mode"),
                        "scope_company_ids": scope_company_ids,
                        "scope_label": _build_scope_label(scope.get("scope_mode"), scope.get("ute_name")),
                        "scope_vehicle_count": scope_vehicle_count,
                        "ute_id": scope.get("ute_id"),
                        "ute_name": scope.get("ute_name"),
                        "real_assigned": int(preview.get("real_assigned", 0)),
                        "virtual_created": int(preview.get("virtual_created", 0)),
                        "conflicts": preview.get("conflicts", []),
                        "blocked": True,
                        "days": preview.get("days", {}),
                    },
                },
            )

        if virtual_policy == "block" and int(preview.get("virtual_created", 0) or 0) > 0:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Publicacion bloqueada: hay buses ficticios pendientes de asignar a flota real",
                    "reason": "virtual_reconciliation_required",
                    "fleet_publication": {
                        "company_id": company_id,
                        "scope_mode": scope.get("scope_mode"),
                        "scope_company_ids": scope_company_ids,
                        "scope_label": _build_scope_label(scope.get("scope_mode"), scope.get("ute_name")),
                        "scope_vehicle_count": scope_vehicle_count,
                        "ute_id": scope.get("ute_id"),
                        "ute_name": scope.get("ute_name"),
                        "real_assigned": int(preview.get("real_assigned", 0)),
                        "virtual_created": int(preview.get("virtual_created", 0)),
                        "conflicts": [],
                        "blocked": True,
                        "days": preview.get("days", {}),
                        "virtual_publish_policy": virtual_policy,
                        "reconciliation": preview.get("reconciliation", {}),
                    },
                },
            )

        fleet_snapshot = {
            "company_id": company_id,
            "scope_mode": scope.get("scope_mode"),
            "scope_company_ids": scope_company_ids,
            "ute_id": scope.get("ute_id"),
            "ute_name": scope.get("ute_name"),
            "real_assigned": int(preview.get("real_assigned", 0)),
            "virtual_created": int(preview.get("virtual_created", 0)),
            "conflicts": [],
            "blocked": False,
            "days": preview.get("days", {}),
            "virtual_publish_policy": virtual_policy,
            "reconciliation": preview.get("reconciliation", {}),
        }
        merged_summary = dict(publish_payload.summary_metrics or {})
        merged_summary["fleet_real_assigned"] = int(preview.get("real_assigned", 0))
        merged_summary["fleet_virtual_created"] = int(preview.get("virtual_created", 0))
        merged_summary["fleet_binding_state"] = "committed"
        merged_summary["fleet_virtual_publish_policy"] = virtual_policy

        final_payload = publish_payload.model_copy(
            update={
                "schedule_by_day": preview.get("schedule_by_day", normalized_schedule),
                "fleet_snapshot": fleet_snapshot,
                "summary_metrics": merged_summary,
            }
        )
        version = db_crud.create_workspace_version(
            db,
            workspace_id,
            final_payload,
            auto_commit=False,
        )
        if version is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        persist_publication_assignments(
            db,
            workspace_id=workspace_id,
            workspace_version_id=str(version.id),
            company_id=company_id,
            candidate_rows=preview.get("candidate_rows", []),
        )
        db.commit()
        db.refresh(version)
        response = _to_version_response(version)
        if response is None:
            raise HTTPException(status_code=500, detail="Version serialization failed")
        return response
    finally:
        db.close()


@router.post("/{workspace_id}/rename", response_model=schemas.WorkspaceResponse)
async def rename_workspace(
    workspace_id: str,
    payload: schemas.WorkspaceRenameRequest = Body(...),
) -> schemas.WorkspaceResponse:
    """Rename workspace."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.rename_workspace(db, workspace_id, payload.name)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        hydrated = db_crud.get_workspace(db, workspace_id)
        if hydrated is None:
            raise HTTPException(status_code=500, detail="Workspace serialization failed")
        return _to_workspace_response(hydrated)
    finally:
        db.close()


@router.post("/{workspace_id}/company", response_model=schemas.WorkspaceDetailResponse)
async def update_workspace_company(
    workspace_id: str,
    payload: schemas.WorkspaceCompanyUpdateRequest = Body(...),
) -> schemas.WorkspaceDetailResponse:
    """Update the primary company used by company-scope planning/publish flows."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        workspace = _repair_workspace_primary_company(db, workspace)
        company = db_crud.get_company(db, str(payload.company_id).strip())
        if company is None:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        workspace.company_id = str(company.id)
        workspace.updated_at = datetime.utcnow()
        db.commit()
        hydrated = db_crud.get_workspace(db, workspace_id)
        if hydrated is None:
            raise HTTPException(status_code=500, detail="Workspace serialization failed")
        return _to_workspace_detail_response(hydrated)
    finally:
        db.close()


@router.post("/{workspace_id}/archive", response_model=schemas.WorkspaceResponse)
async def archive_workspace(workspace_id: str) -> schemas.WorkspaceResponse:
    """Archive workspace (inactive) and disable operational reservations."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.set_workspace_archived(db, workspace_id, True)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        db.query(PublishedFleetAssignmentModel).filter(
            PublishedFleetAssignmentModel.workspace_id == str(workspace.id),
            PublishedFleetAssignmentModel.active.is_(True),
        ).update({"active": False})
        db.commit()
        hydrated = db_crud.get_workspace(db, workspace_id)
        if hydrated is None:
            raise HTTPException(status_code=500, detail="Workspace serialization failed")
        return _to_workspace_response(hydrated)
    finally:
        db.close()


@router.post("/{workspace_id}/restore", response_model=schemas.WorkspaceResponse)
async def restore_workspace(workspace_id: str) -> schemas.WorkspaceResponse:
    """
    Restore archived workspace.
    If it has a published version, conflicts are checked before reactivating reservations.
    """
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        restored = db_crud.set_workspace_archived(db, workspace_id, False)
        if restored is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Re-activate only if no conflict for published version.
        if restored.published_version and isinstance(restored.published_version.schedule_by_day, dict):
            scope = resolve_workspace_fleet_scope(db, restored)
            company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, restored))
            scope_company_ids = [
                str(cid) for cid in (scope.get("scope_company_ids") or [])
                if str(cid).strip()
            ]
            schedule_by_day = db_crud.normalize_schedule_by_day(restored.published_version.schedule_by_day)
            preview = preview_workspace_publication(
                db,
                company_id=company_id,
                scope_company_ids=scope_company_ids,
                schedule_by_day=schedule_by_day,
                exclude_workspace_id=str(restored.id),
            )
            if bool(preview.get("blocked", False)):
                db_crud.set_workspace_archived(db, workspace_id, True)
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "No se puede restaurar: conflictos de flota con optimizaciones publicadas",
                        "fleet_publication": {
                            "company_id": company_id,
                            "scope_mode": scope.get("scope_mode"),
                            "scope_company_ids": scope_company_ids,
                            "ute_id": scope.get("ute_id"),
                            "ute_name": scope.get("ute_name"),
                            "real_assigned": int(preview.get("real_assigned", 0)),
                            "virtual_created": int(preview.get("virtual_created", 0)),
                            "conflicts": preview.get("conflicts", []),
                            "blocked": True,
                            "days": preview.get("days", {}),
                        },
                    },
                )
            persist_publication_assignments(
                db,
                workspace_id=str(restored.id),
                workspace_version_id=str(restored.published_version.id),
                company_id=company_id,
                candidate_rows=preview.get("candidate_rows", []),
            )
            db.commit()

        hydrated = db_crud.get_workspace(db, workspace_id)
        if hydrated is None:
            raise HTTPException(status_code=500, detail="Workspace serialization failed")
        return _to_workspace_response(hydrated)
    finally:
        db.close()


@router.post("/{workspace_id}/delete", response_model=schemas.WorkspaceDeleteResponse)
async def delete_workspace_hard(
    workspace_id: str,
    payload: schemas.WorkspaceDeleteRequest = Body(...),
) -> schemas.WorkspaceDeleteResponse:
    """Permanently delete workspace after explicit name confirmation."""
    if not is_database_available() or SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not available")
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        workspace = db_crud.get_workspace(db, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        expected_name = str(workspace.name or "").strip()
        received_name = str(payload.confirm_name or "").strip()
        if received_name != expected_name:
            raise HTTPException(
                status_code=409,
                detail="Workspace confirmation name does not match",
            )

        deleted_name = db_crud.delete_workspace_hard(db, workspace_id)
        if deleted_name is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

        meta = db_crud.get_app_meta(db, "last_open_workspace_id")
        current_last_open = None
        if meta:
            value = meta.value
            if isinstance(value, dict):
                current_last_open = str(value.get("workspace_id") or "").strip() or None
            elif value is not None:
                current_last_open = str(value).strip() or None
        if current_last_open == workspace_id:
            db_crud.set_app_meta(db, "last_open_workspace_id", None)

        return schemas.WorkspaceDeleteResponse(
            success=True,
            workspace_id=workspace_id,
            deleted_name=deleted_name,
        )
    finally:
        db.close()


@router.post("/migrate-legacy", response_model=schemas.LegacyMigrationResponse)
async def migrate_legacy_workspaces() -> schemas.LegacyMigrationResponse:
    """Idempotent migration bootstrap from legacy jobs/manual schedules."""
    if not is_database_available() or SessionLocal is None:
        return schemas.LegacyMigrationResponse(
            success=False,
            migrated=False,
            workspace_id=None,
            workspace_name=None,
            details={"reason": "database_not_available"},
        )
    _ensure_tables_ready()

    db = SessionLocal()
    try:
        success, migrated, workspace, details = db_crud.migrate_legacy_workspace_bootstrap(db)
        return schemas.LegacyMigrationResponse(
            success=success,
            migrated=migrated,
            workspace_id=str(workspace.id) if workspace else None,
            workspace_name=str(workspace.name) if workspace else None,
            details=details,
        )
    finally:
        db.close()
