"""
Workspace API.

Provides versioned optimization workspaces with save/publish semantics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

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
from services.fleet_scope import resolve_workspace_fleet_scope
from services.workspace_options import (
    DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS,
    get_workspace_optimization_options,
    sanitize_workspace_optimization_options,
    set_workspace_optimization_options,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


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
    status_value = "inactive" if workspace.archived else (
        "active"
        if workspace.published_version_id and (
            workspace.working_version_id is None
            or workspace.published_version_id == workspace.working_version_id
        )
        else "draft"
    )
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
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
    )


def _to_workspace_detail_response(workspace: OptimizationWorkspaceModel) -> schemas.WorkspaceDetailResponse:
    base = _to_workspace_response(workspace)
    return schemas.WorkspaceDetailResponse(
        **base.model_dump(),
        working_version=_to_version_response(workspace.working_version),
        published_version=_to_version_response(workspace.published_version),
    )


def _workspace_company_id(db, workspace: OptimizationWorkspaceModel) -> str:
    default_company = db_crud.ensure_default_company(db)
    company_id = str(workspace.company_id or "").strip() or str(default_company.id)
    return company_id


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
        working_version = workspace.working_version or workspace.published_version
        if working_version is None:
            raise HTTPException(status_code=409, detail="Workspace has no version to preview")
        schedule_by_day = db_crud.normalize_schedule_by_day(working_version.schedule_by_day or {})
        scope = resolve_workspace_fleet_scope(db, workspace)
        company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, workspace))
        scope_company_ids = [
            str(cid) for cid in (scope.get("scope_company_ids") or [])
            if str(cid).strip()
        ]
        preview = preview_workspace_publication(
            db,
            company_id=company_id,
            scope_company_ids=scope_company_ids,
            schedule_by_day=schedule_by_day,
            exclude_workspace_id=str(workspace.id),
        )
        if day and day in preview.get("schedule_by_day", {}):
            return {
                "workspace_id": workspace_id,
                "company_id": company_id,
                "scope_mode": scope.get("scope_mode"),
                "scope_company_ids": scope_company_ids,
                "ute_id": scope.get("ute_id"),
                "ute_name": scope.get("ute_name"),
                "day": day,
                "blocked": bool(preview.get("blocked", False)),
                "conflicts": [c for c in preview.get("conflicts", []) if c.get("day") == day],
                "real_assigned": int(preview.get("real_assigned", 0)),
                "virtual_created": int(preview.get("virtual_created", 0)),
                "day_payload": preview.get("schedule_by_day", {}).get(day, {}),
                "days": preview.get("days", {}),
            }
        return {
            "workspace_id": workspace_id,
            "company_id": company_id,
            "scope_mode": scope.get("scope_mode"),
            "scope_company_ids": scope_company_ids,
            "ute_id": scope.get("ute_id"),
            "ute_name": scope.get("ute_name"),
            "blocked": bool(preview.get("blocked", False)),
            "conflicts": preview.get("conflicts", []),
            "real_assigned": int(preview.get("real_assigned", 0)),
            "virtual_created": int(preview.get("virtual_created", 0)),
            "schedule_by_day": preview.get("schedule_by_day", {}),
            "days": preview.get("days", {}),
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

        scope = resolve_workspace_fleet_scope(db, workspace)
        company_id = str(scope.get("primary_company_id") or _workspace_company_id(db, workspace))
        scope_company_ids = [
            str(cid) for cid in (scope.get("scope_company_ids") or [])
            if str(cid).strip()
        ]
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
        }
        merged_summary = dict(publish_payload.summary_metrics or {})
        merged_summary["fleet_real_assigned"] = int(preview.get("real_assigned", 0))
        merged_summary["fleet_virtual_created"] = int(preview.get("virtual_created", 0))
        merged_summary["fleet_binding_state"] = "committed"

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
