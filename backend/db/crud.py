"""
CRUD operations for Tutti database.

Provides functions to create, read, update, and delete:
- Routes with stops
- Optimization jobs
- Optimization results
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func

from . import models, schemas

logger = logging.getLogger(__name__)


# =============================================================================
# Route CRUD
# =============================================================================

def create_route(db: Session, route_data: schemas.RouteCreate) -> models.RouteModel:
    """
    Create a new route with its stops.
    
    Args:
        db: Database session
        route_data: Route data including stops
        
    Returns:
        Created RouteModel instance
    """
    # Create route without stops first
    db_route = models.RouteModel(
        id=route_data.id,
        name=route_data.name,
        type=route_data.type,
        school_id=route_data.school_id,
        school_name=route_data.school_name,
        arrival_time=route_data.arrival_time,
        departure_time=route_data.departure_time,
        capacity_needed=route_data.capacity_needed,
        contract_id=route_data.contract_id,
        days=route_data.days or []
    )
    
    # Add stops
    for stop_data in route_data.stops:
        db_stop = models.StopModel(
            name=stop_data.name,
            lat=stop_data.lat,
            lon=stop_data.lon,
            order=stop_data.order,
            time_from_start=stop_data.time_from_start,
            passengers=stop_data.passengers,
            is_school=stop_data.is_school
        )
        db_route.stops.append(db_stop)
    
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    
    logger.info(f"Created route {db_route.id} with {len(db_route.stops)} stops")
    return db_route


def create_routes_batch(db: Session, routes_data: List[schemas.RouteCreate]) -> List[models.RouteModel]:
    """
    Create multiple routes efficiently in a batch.
    
    Args:
        db: Database session
        routes_data: List of route data
        
    Returns:
        List of created RouteModel instances
    """
    created_routes = []
    
    for route_data in routes_data:
        db_route = models.RouteModel(
            id=route_data.id,
            name=route_data.name,
            type=route_data.type,
            school_id=route_data.school_id,
            school_name=route_data.school_name,
            arrival_time=route_data.arrival_time,
            departure_time=route_data.departure_time,
            capacity_needed=route_data.capacity_needed,
            contract_id=route_data.contract_id,
            days=route_data.days or []
        )
        
        for stop_data in route_data.stops:
            db_stop = models.StopModel(
                name=stop_data.name,
                lat=stop_data.lat,
                lon=stop_data.lon,
                order=stop_data.order,
                time_from_start=stop_data.time_from_start,
                passengers=stop_data.passengers,
                is_school=stop_data.is_school
            )
            db_route.stops.append(db_stop)
        
        db.add(db_route)
        created_routes.append(db_route)
    
    db.commit()
    
    # Refresh all to get generated IDs
    for route in created_routes:
        db.refresh(route)
    
    logger.info(f"Batch created {len(created_routes)} routes")
    return created_routes


def get_route(db: Session, route_id: str) -> Optional[models.RouteModel]:
    """
    Get a route by ID with all its stops.
    
    Args:
        db: Database session
        route_id: Route ID
        
    Returns:
        RouteModel instance or None
    """
    return db.query(models.RouteModel).options(
        joinedload(models.RouteModel.stops)
    ).filter(models.RouteModel.id == route_id).first()


def get_routes(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    route_type: Optional[str] = None
) -> List[models.RouteModel]:
    """
    Get multiple routes with pagination.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        route_type: Optional filter by type ('entry' or 'exit')
        
    Returns:
        List of RouteModel instances
    """
    query = db.query(models.RouteModel).options(
        joinedload(models.RouteModel.stops)
    )
    
    if route_type:
        query = query.filter(models.RouteModel.type == route_type)
    
    return query.offset(skip).limit(limit).all()


def get_all_route_ids(db: Session) -> List[str]:
    """
    Get all route IDs (lightweight query).
    
    Args:
        db: Database session
        
    Returns:
        List of route IDs
    """
    return [r[0] for r in db.query(models.RouteModel.id).all()]


def update_route(db: Session, route_id: str, route_data: schemas.RouteCreate) -> Optional[models.RouteModel]:
    """
    Update an existing route.
    
    Args:
        db: Database session
        route_id: Route ID to update
        route_data: New route data
        
    Returns:
        Updated RouteModel or None if not found
    """
    db_route = get_route(db, route_id)
    if not db_route:
        return None
    
    # Update fields
    db_route.name = route_data.name
    db_route.type = route_data.type
    db_route.school_id = route_data.school_id
    db_route.school_name = route_data.school_name
    db_route.arrival_time = route_data.arrival_time
    db_route.departure_time = route_data.departure_time
    db_route.capacity_needed = route_data.capacity_needed
    db_route.contract_id = route_data.contract_id
    db_route.days = route_data.days or []
    
    # Update stops (delete and recreate)
    for stop in db_route.stops:
        db.delete(stop)
    
    for stop_data in route_data.stops:
        db_stop = models.StopModel(
            name=stop_data.name,
            lat=stop_data.lat,
            lon=stop_data.lon,
            order=stop_data.order,
            time_from_start=stop_data.time_from_start,
            passengers=stop_data.passengers,
            is_school=stop_data.is_school
        )
        db_route.stops.append(db_stop)
    
    db.commit()
    db.refresh(db_route)
    
    logger.info(f"Updated route {route_id}")
    return db_route


def delete_route(db: Session, route_id: str) -> bool:
    """
    Delete a route and all its stops.
    
    Args:
        db: Database session
        route_id: Route ID to delete
        
    Returns:
        True if deleted, False if not found
    """
    db_route = get_route(db, route_id)
    if not db_route:
        return False
    
    db.delete(db_route)
    db.commit()
    
    logger.info(f"Deleted route {route_id}")
    return True


def delete_all_routes(db: Session) -> int:
    """
    Delete all routes (use with caution!).
    
    Args:
        db: Database session
        
    Returns:
        Number of routes deleted
    """
    count = db.query(models.RouteModel).delete()
    db.commit()
    
    logger.warning(f"Deleted all {count} routes")
    return count


# =============================================================================
# Optimization Job CRUD
# =============================================================================

def create_optimization_job(
    db: Session,
    job_data: schemas.OptimizationJobCreate
) -> models.OptimizationJob:
    """
    Create a new optimization job.
    
    Args:
        db: Database session
        job_data: Job creation data
        
    Returns:
        Created OptimizationJob instance
    """
    db_job = models.OptimizationJob(
        status="pending",
        algorithm=job_data.algorithm,
        input_data=job_data.input_data
    )
    
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    logger.info(f"Created optimization job {db_job.id} with algorithm {db_job.algorithm}")
    return db_job


def get_optimization_job(db: Session, job_id: UUID) -> Optional[models.OptimizationJob]:
    """
    Get an optimization job by ID.
    
    Args:
        db: Database session
        job_id: Job ID
        
    Returns:
        OptimizationJob instance or None
    """
    return db.query(models.OptimizationJob).filter(
        models.OptimizationJob.id == job_id
    ).first()


def get_optimization_jobs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None
) -> List[models.OptimizationJob]:
    """
    Get optimization jobs with pagination.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records
        status: Optional status filter
        
    Returns:
        List of OptimizationJob instances
    """
    query = db.query(models.OptimizationJob)
    
    if status:
        query = query.filter(models.OptimizationJob.status == status)
    
    return query.order_by(desc(models.OptimizationJob.created_at)).offset(skip).limit(limit).all()


def update_job_status(
    db: Session,
    job_id: UUID,
    status: str,
    result: Optional[dict] = None,
    stats: Optional[dict] = None,
    error_message: Optional[str] = None
) -> Optional[models.OptimizationJob]:
    """
    Update job status and optionally results.
    
    Args:
        db: Database session
        job_id: Job ID
        status: New status (pending, running, completed, failed)
        result: Optional result data
        stats: Optional statistics
        error_message: Optional error message
        
    Returns:
        Updated OptimizationJob or None if not found
    """
    db_job = get_optimization_job(db, job_id)
    if not db_job:
        return None
    
    db_job.status = status
    
    if status == "running" and not db_job.started_at:
        db_job.started_at = datetime.utcnow()
    
    if status in ("completed", "failed"):
        db_job.completed_at = datetime.utcnow()
    
    if result is not None:
        db_job.result = result
    
    if stats is not None:
        db_job.stats = stats
    
    if error_message is not None:
        db_job.error_message = error_message
    
    db.commit()
    db.refresh(db_job)
    
    logger.info(f"Updated job {job_id} status to {status}")
    return db_job


def delete_optimization_job(db: Session, job_id: UUID) -> bool:
    """
    Delete an optimization job and all its results.
    
    Args:
        db: Database session
        job_id: Job ID
        
    Returns:
        True if deleted, False if not found
    """
    db_job = get_optimization_job(db, job_id)
    if not db_job:
        return False
    
    db.delete(db_job)
    db.commit()
    
    logger.info(f"Deleted optimization job {job_id}")
    return True


# =============================================================================
# Optimization Result CRUD
# =============================================================================

def create_optimization_result(
    db: Session,
    result_data: schemas.OptimizationResultCreate
) -> models.OptimizationResultModel:
    """
    Create a single optimization result.
    
    Args:
        db: Database session
        result_data: Result creation data
        
    Returns:
        Created OptimizationResultModel instance
    """
    db_result = models.OptimizationResultModel(
        job_id=result_data.job_id,
        route_id=result_data.route_id,
        bus_id=result_data.bus_id,
        start_time=result_data.start_time,
        end_time=result_data.end_time,
        time_shift_minutes=result_data.time_shift_minutes,
        deadhead_minutes=result_data.deadhead_minutes
    )
    
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    
    return db_result


def create_optimization_results_batch(
    db: Session,
    job_id: UUID,
    schedule: List[schemas.BusScheduleSchema]
) -> List[models.OptimizationResultModel]:
    """
    Create optimization results from a complete schedule.
    
    Args:
        db: Database session
        job_id: Job ID
        schedule: List of bus schedules from optimizer
        
    Returns:
        List of created OptimizationResultModel instances
    """
    created_results = []
    
    for bus_schedule in schedule:
        for item in bus_schedule.items:
            db_result = models.OptimizationResultModel(
                job_id=job_id,
                route_id=item.route_id,
                bus_id=bus_schedule.bus_id,
                start_time=item.start_time,
                end_time=item.end_time,
                time_shift_minutes=item.time_shift_minutes,
                deadhead_minutes=item.deadhead_minutes
            )
            db.add(db_result)
            created_results.append(db_result)
    
    db.commit()
    
    # Refresh all
    for result in created_results:
        db.refresh(result)
    
    logger.info(f"Created {len(created_results)} optimization results for job {job_id}")
    return created_results


def get_job_results(
    db: Session,
    job_id: UUID
) -> List[models.OptimizationResultModel]:
    """
    Get all results for a job.
    
    Args:
        db: Database session
        job_id: Job ID
        
    Returns:
        List of OptimizationResultModel instances with route info
    """
    return db.query(models.OptimizationResultModel).options(
        joinedload(models.OptimizationResultModel.route)
    ).filter(
        models.OptimizationResultModel.job_id == job_id
    ).all()


def get_route_assignments(
    db: Session,
    route_id: str
) -> List[models.OptimizationResultModel]:
    """
    Get all optimization results for a specific route.
    
    Args:
        db: Database session
        route_id: Route ID
        
    Returns:
        List of OptimizationResultModel instances
    """
    return db.query(models.OptimizationResultModel).options(
        joinedload(models.OptimizationResultModel.job)
    ).filter(
        models.OptimizationResultModel.route_id == route_id
    ).order_by(desc(models.OptimizationResultModel.id)).all()


# =============================================================================
# Manual Schedule CRUD
# =============================================================================

def upsert_manual_schedule(
    db: Session,
    day: str,
    payload: dict,
) -> models.ManualScheduleModel:
    """
    Create or update a persisted manual schedule for a day.

    Args:
        db: Database session
        day: Day code (L, M, Mc, X, V)
        payload: Serialized schedule payload

    Returns:
        Upserted ManualScheduleModel
    """
    schedule = db.query(models.ManualScheduleModel).filter(
        models.ManualScheduleModel.day == day
    ).first()

    if schedule is None:
        schedule = models.ManualScheduleModel(day=day, payload=payload)
        db.add(schedule)
    else:
        schedule.payload = payload
        schedule.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(schedule)
    logger.info(f"Upserted manual schedule for day {day}")
    return schedule


def get_manual_schedule(db: Session, day: str) -> Optional[models.ManualScheduleModel]:
    """
    Get a persisted manual schedule by day.

    Args:
        db: Database session
        day: Day code

    Returns:
        ManualScheduleModel or None
    """
    return db.query(models.ManualScheduleModel).filter(
        models.ManualScheduleModel.day == day
    ).first()


# =============================================================================
# App Meta CRUD
# =============================================================================

def get_app_meta(db: Session, key: str) -> Optional[models.AppMetaModel]:
    """Get app metadata by key."""
    return db.query(models.AppMetaModel).filter(models.AppMetaModel.key == key).first()


def set_app_meta(db: Session, key: str, value: Any) -> models.AppMetaModel:
    """Upsert app metadata key/value."""
    row = get_app_meta(db, key)
    if row is None:
        row = models.AppMetaModel(key=key, value=value, updated_at=datetime.utcnow())
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


# =============================================================================
# Workspace CRUD
# =============================================================================

def _workspace_status(workspace: models.OptimizationWorkspaceModel) -> str:
    """Derive workspace status from current pointers/flags."""
    if bool(workspace.archived):
        return "inactive"
    if workspace.published_version_id:
        if workspace.working_version_id and workspace.working_version_id != workspace.published_version_id:
            return "draft"
        return "active"
    return "draft"


def _safe_dict(value: Any, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return default.copy() if default else {}


def _safe_list(value: Any, default: Optional[List[Any]] = None) -> List[Any]:
    if isinstance(value, list):
        return value
    return list(default or [])


def _count_routes_in_buses(buses: Any) -> int:
    if not isinstance(buses, list):
        return 0
    total = 0
    for bus in buses:
        if not isinstance(bus, dict):
            continue
        items = bus.get("items")
        if not isinstance(items, list):
            items = bus.get("routes") if isinstance(bus.get("routes"), list) else []
        total += len(items)
    return total


def _build_day_stats_from_buses(buses: Any, existing_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stats = dict(existing_stats or {})
    buses_list = buses if isinstance(buses, list) else []
    total_buses = len(buses_list)
    total_routes = _count_routes_in_buses(buses_list)
    total_entries = 0
    total_exits = 0
    for bus in buses_list:
        if not isinstance(bus, dict):
            continue
        items = bus.get("items")
        if not isinstance(items, list):
            items = bus.get("routes") if isinstance(bus.get("routes"), list) else []
        for item in items:
            item_type = str((item or {}).get("type", "")).lower()
            if item_type == "entry":
                total_entries += 1
            elif item_type == "exit":
                total_exits += 1

    stats.setdefault("total_buses", total_buses)
    stats.setdefault("total_routes", total_routes)
    stats.setdefault("total_entries", total_entries)
    stats.setdefault("total_exits", total_exits)
    if total_buses > 0 and "avg_routes_per_bus" not in stats:
        stats["avg_routes_per_bus"] = round(total_routes / total_buses, 2)
    elif total_buses == 0:
        stats.setdefault("avg_routes_per_bus", 0)
    return stats


def normalize_schedule_by_day(schedule_by_day: Any) -> Dict[str, Any]:
    """
    Normalize schedule payload into stable shape:
    {day: {"schedule": [...], "stats": {...}, "metadata": {...}, "unassigned_routes": [...]}}
    """
    days = ("L", "M", "Mc", "X", "V")
    normalized: Dict[str, Any] = {
        day: {"schedule": [], "stats": {}, "metadata": {}, "unassigned_routes": []}
        for day in days
    }
    if not isinstance(schedule_by_day, dict):
        return normalized

    for day in days:
        raw = schedule_by_day.get(day)
        if raw is None:
            continue
        if isinstance(raw, list):
            buses = raw
            metadata = {}
            unassigned = []
            stats = _build_day_stats_from_buses(buses)
        elif isinstance(raw, dict):
            buses = raw.get("schedule")
            if not isinstance(buses, list):
                buses = raw.get("buses") if isinstance(raw.get("buses"), list) else []
            metadata = _safe_dict(raw.get("metadata"))
            unassigned = _safe_list(raw.get("unassigned_routes"))
            stats = _build_day_stats_from_buses(buses, _safe_dict(raw.get("stats")))
        else:
            continue

        normalized[day] = {
            "schedule": buses,
            "stats": stats,
            "metadata": metadata,
            "unassigned_routes": unassigned,
        }
    return normalized


def _create_workspace_version_record(
    db: Session,
    workspace: models.OptimizationWorkspaceModel,
    version_payload: schemas.WorkspaceVersionCreate,
) -> models.OptimizationWorkspaceVersionModel:
    """Create immutable workspace version using explicit payload + working fallback."""
    latest_version = db.query(func.max(models.OptimizationWorkspaceVersionModel.version_number)).filter(
        models.OptimizationWorkspaceVersionModel.workspace_id == workspace.id
    ).scalar()
    next_version_number = int(latest_version or 0) + 1

    base_version = None
    if workspace.working_version_id:
        base_version = db.query(models.OptimizationWorkspaceVersionModel).filter(
            models.OptimizationWorkspaceVersionModel.id == workspace.working_version_id
        ).first()

    routes_payload = version_payload.routes_payload
    if routes_payload is None and base_version is not None:
        routes_payload = base_version.routes_payload
    if routes_payload is None:
        routes_payload = []

    schedule_by_day = version_payload.schedule_by_day
    if schedule_by_day is None and base_version is not None:
        schedule_by_day = base_version.schedule_by_day
    normalized_schedule = normalize_schedule_by_day(schedule_by_day or {})

    parse_report = version_payload.parse_report
    if parse_report is None and base_version is not None:
        parse_report = base_version.parse_report

    validation_report = version_payload.validation_report
    if validation_report is None and base_version is not None:
        validation_report = base_version.validation_report

    fleet_snapshot = version_payload.fleet_snapshot
    if fleet_snapshot is None and base_version is not None:
        fleet_snapshot = base_version.fleet_snapshot

    summary_metrics = version_payload.summary_metrics
    if summary_metrics is None and base_version is not None:
        summary_metrics = base_version.summary_metrics

    record = models.OptimizationWorkspaceVersionModel(
        workspace_id=workspace.id,
        version_number=next_version_number,
        save_kind=version_payload.save_kind,
        checkpoint_name=version_payload.checkpoint_name,
        routes_payload=routes_payload,
        schedule_by_day=normalized_schedule,
        parse_report=parse_report,
        validation_report=validation_report,
        fleet_snapshot=fleet_snapshot,
        summary_metrics=summary_metrics,
    )
    db.add(record)
    db.flush()
    return record


def _enforce_workspace_autosave_retention(db: Session, workspace_id: str, keep_last: int = 30) -> None:
    """Keep only latest N autosave versions for a workspace."""
    autosaves = db.query(models.OptimizationWorkspaceVersionModel).filter(
        models.OptimizationWorkspaceVersionModel.workspace_id == workspace_id,
        models.OptimizationWorkspaceVersionModel.save_kind == "autosave",
    ).order_by(desc(models.OptimizationWorkspaceVersionModel.version_number)).all()
    if len(autosaves) <= keep_last:
        return
    for old_version in autosaves[keep_last:]:
        if old_version.id in {None}:
            continue
        # Never delete pointer targets.
        workspace = db.query(models.OptimizationWorkspaceModel).filter(
            models.OptimizationWorkspaceModel.id == workspace_id
        ).first()
        if workspace and old_version.id in {workspace.working_version_id, workspace.published_version_id}:
            continue
        db.delete(old_version)
    db.flush()


def create_workspace(
    db: Session,
    payload: schemas.WorkspaceCreateRequest,
) -> models.OptimizationWorkspaceModel:
    """Create new workspace and optional initial snapshot."""
    workspace = models.OptimizationWorkspaceModel(
        name=payload.name.strip(),
        city_label=(payload.city_label or "").strip() or None,
        archived=False,
    )
    db.add(workspace)
    db.flush()

    if (
        payload.routes_payload is not None
        or payload.parse_report is not None
        or payload.schedule_by_day is not None
        or payload.summary_metrics is not None
    ):
        initial = schemas.WorkspaceVersionCreate(
            save_kind="save",
            routes_payload=payload.routes_payload,
            schedule_by_day=payload.schedule_by_day,
            parse_report=payload.parse_report,
            summary_metrics=payload.summary_metrics,
        )
        version = _create_workspace_version_record(db, workspace, initial)
        workspace.working_version_id = version.id

    workspace.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workspace)
    return workspace


def get_workspace(db: Session, workspace_id: str) -> Optional[models.OptimizationWorkspaceModel]:
    """Fetch workspace with versions/pointers."""
    return db.query(models.OptimizationWorkspaceModel).options(
        joinedload(models.OptimizationWorkspaceModel.versions),
        joinedload(models.OptimizationWorkspaceModel.working_version),
        joinedload(models.OptimizationWorkspaceModel.published_version),
    ).filter(models.OptimizationWorkspaceModel.id == workspace_id).first()


def list_workspaces(
    db: Session,
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
    city: Optional[str] = None,
    updated_from: Optional[datetime] = None,
) -> List[models.OptimizationWorkspaceModel]:
    """List workspaces with optional filters."""
    query = db.query(models.OptimizationWorkspaceModel).options(
        joinedload(models.OptimizationWorkspaceModel.versions),
        joinedload(models.OptimizationWorkspaceModel.working_version),
        joinedload(models.OptimizationWorkspaceModel.published_version),
    )
    if q:
        like_pattern = f"%{q.strip()}%"
        query = query.filter(models.OptimizationWorkspaceModel.name.ilike(like_pattern))
    if city:
        query = query.filter(models.OptimizationWorkspaceModel.city_label == city)
    if updated_from:
        query = query.filter(models.OptimizationWorkspaceModel.updated_at >= updated_from)

    workspaces = query.order_by(desc(models.OptimizationWorkspaceModel.updated_at)).all()
    if status:
        normalized = status.strip().lower()
        workspaces = [ws for ws in workspaces if _workspace_status(ws) == normalized]
    return workspaces


def create_workspace_version(
    db: Session,
    workspace_id: str,
    payload: schemas.WorkspaceVersionCreate,
) -> Optional[models.OptimizationWorkspaceVersionModel]:
    """Create snapshot and move working/published pointers according to save kind."""
    workspace = db.query(models.OptimizationWorkspaceModel).filter(
        models.OptimizationWorkspaceModel.id == workspace_id
    ).first()
    if workspace is None:
        return None

    record = _create_workspace_version_record(db, workspace, payload)
    workspace.working_version_id = record.id
    if payload.save_kind == "publish":
        workspace.published_version_id = record.id
    workspace.updated_at = datetime.utcnow()
    _enforce_workspace_autosave_retention(db, workspace.id, keep_last=30)
    db.commit()
    db.refresh(record)
    return record


def get_workspace_versions(db: Session, workspace_id: str) -> List[models.OptimizationWorkspaceVersionModel]:
    """List workspace versions newest first."""
    return db.query(models.OptimizationWorkspaceVersionModel).filter(
        models.OptimizationWorkspaceVersionModel.workspace_id == workspace_id
    ).order_by(desc(models.OptimizationWorkspaceVersionModel.version_number)).all()


def get_workspace_version(
    db: Session,
    workspace_id: str,
    version_id: str,
) -> Optional[models.OptimizationWorkspaceVersionModel]:
    """Get a specific version."""
    return db.query(models.OptimizationWorkspaceVersionModel).filter(
        models.OptimizationWorkspaceVersionModel.workspace_id == workspace_id,
        models.OptimizationWorkspaceVersionModel.id == version_id,
    ).first()


def rename_workspace(db: Session, workspace_id: str, name: str) -> Optional[models.OptimizationWorkspaceModel]:
    """Rename workspace."""
    workspace = db.query(models.OptimizationWorkspaceModel).filter(
        models.OptimizationWorkspaceModel.id == workspace_id
    ).first()
    if workspace is None:
        return None
    workspace.name = name.strip()
    workspace.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workspace)
    return workspace


def set_workspace_archived(
    db: Session,
    workspace_id: str,
    archived: bool,
) -> Optional[models.OptimizationWorkspaceModel]:
    """Archive or restore workspace."""
    workspace = db.query(models.OptimizationWorkspaceModel).filter(
        models.OptimizationWorkspaceModel.id == workspace_id
    ).first()
    if workspace is None:
        return None
    workspace.archived = bool(archived)
    workspace.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workspace)
    return workspace


def _extract_latest_completed_job_seed(
    db: Session,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Extract best-effort legacy seed from latest completed optimization job.
    Returns (routes_payload, schedule_by_day, summary_metrics, source_job_id).
    """
    jobs = db.query(models.OptimizationJob).filter(
        models.OptimizationJob.status == "completed"
    ).order_by(
        desc(models.OptimizationJob.completed_at),
        desc(models.OptimizationJob.created_at),
    ).all()

    for job in jobs:
        raw_input = job.input_data
        routes_payload: Optional[List[Dict[str, Any]]] = None
        if isinstance(raw_input, list):
            routes_payload = raw_input
        elif isinstance(raw_input, dict):
            raw_routes = raw_input.get("routes")
            if isinstance(raw_routes, list):
                routes_payload = raw_routes

        raw_result = job.result if isinstance(job.result, dict) else {}
        schedule_by_day = raw_result.get("schedule_by_day") if isinstance(raw_result, dict) else None
        if not isinstance(schedule_by_day, dict):
            continue

        summary_metrics = raw_result.get("summary_metrics") if isinstance(raw_result, dict) else None
        return routes_payload, schedule_by_day, summary_metrics if isinstance(summary_metrics, dict) else None, str(job.id)

    return None, None, None, None


def migrate_legacy_workspace_bootstrap(
    db: Session,
) -> Tuple[bool, bool, Optional[models.OptimizationWorkspaceModel], Dict[str, Any]]:
    """
    Idempotent migration bootstrap.
    Returns (success, migrated, workspace, details).
    """
    flag = get_app_meta(db, "workspace_migration_v1_done")
    if flag and bool(flag.value):
        details = {"reason": "already_migrated"}
        return True, False, None, details

    workspace_count = db.query(func.count(models.OptimizationWorkspaceModel.id)).scalar() or 0
    if int(workspace_count) > 0:
        set_app_meta(db, "workspace_migration_v1_done", True)
        details = {"reason": "workspaces_already_exist", "workspace_count": int(workspace_count)}
        return True, False, None, details

    routes_payload, schedule_seed, summary_metrics, source_job_id = _extract_latest_completed_job_seed(db)
    normalized_schedule = normalize_schedule_by_day(schedule_seed or {})
    manual_rows = db.query(models.ManualScheduleModel).all()
    manual_days_applied: List[str] = []
    for row in manual_rows:
        day = str(row.day)
        if day not in normalized_schedule:
            continue
        payload = row.payload if isinstance(row.payload, dict) else {}
        buses = payload.get("buses")
        if not isinstance(buses, list):
            buses = payload.get("schedule") if isinstance(payload.get("schedule"), list) else []
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        unassigned = payload.get("unassigned_routes") if isinstance(payload.get("unassigned_routes"), list) else []
        normalized_schedule[day] = {
            "schedule": buses,
            "stats": _build_day_stats_from_buses(buses, normalized_schedule[day].get("stats")),
            "metadata": metadata,
            "unassigned_routes": unassigned,
        }
        manual_days_applied.append(day)

    has_seed_data = bool(routes_payload) or any(
        bool((normalized_schedule.get(day) or {}).get("schedule"))
        for day in ("L", "M", "Mc", "X", "V")
    )
    if not has_seed_data:
        set_app_meta(db, "workspace_migration_v1_done", True)
        details = {"reason": "no_legacy_data_found"}
        return True, False, None, details

    migration_name = f"Migrado - {datetime.utcnow().strftime('%Y-%m-%d')}"
    workspace = models.OptimizationWorkspaceModel(
        name=migration_name,
        city_label=None,
        archived=False,
    )
    db.add(workspace)
    db.flush()

    version = _create_workspace_version_record(
        db,
        workspace,
        schemas.WorkspaceVersionCreate(
            save_kind="migration",
            checkpoint_name="legacy-bootstrap",
            routes_payload=routes_payload or [],
            schedule_by_day=normalized_schedule,
            summary_metrics=summary_metrics,
        ),
    )
    workspace.working_version_id = version.id
    workspace.published_version_id = version.id
    workspace.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(workspace)

    set_app_meta(db, "workspace_migration_v1_done", True)
    set_app_meta(db, "last_open_workspace_id", workspace.id)

    details = {
        "source_job_id": source_job_id,
        "manual_days_applied": manual_days_applied,
        "routes_count": len(routes_payload or []),
        "has_schedule_seed": any(
            bool((normalized_schedule.get(day) or {}).get("schedule"))
            for day in ("L", "M", "Mc", "X", "V")
        ),
    }
    return True, True, workspace, details
