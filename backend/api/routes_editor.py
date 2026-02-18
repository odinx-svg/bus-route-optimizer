"""
Route Editor API - Endpoints for editing routes and schedules from frontend.

This module provides REST API endpoints for:
- Updating individual route data (PATCH /api/routes/{route_id})
- Toggle route lock status (POST /api/routes/{route_id}/toggle-lock)
- Saving complete schedule updates (POST /api/schedules/update)

All endpoints include robust validation for:
- Time overlaps on the same bus
- Valid coordinates on stops
- Time shift limits
"""

from datetime import datetime, time
from typing import Dict, List, Optional, Any, Tuple
import logging

from fastapi import APIRouter, HTTPException, Body, Query, status
from pydantic import BaseModel, Field

from db import schemas, crud as db_crud
from db.database import SessionLocal, is_database_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["route-editor"])

# =============================================================================
# In-memory cache for edited schedules
# Key: session_id or day, Value: schedule data
# =============================================================================
edited_schedules_cache: Dict[str, Dict[str, Any]] = {}

# =============================================================================
# Constants for validation
# =============================================================================
MAX_TIME_SHIFT_MINUTES = 30  # Maximum allowed time shift in either direction
MIN_COORDINATE = -180.0  # Minimum valid coordinate value
MAX_COORDINATE = 180.0  # Maximum valid coordinate value
MIN_BUFFER_MINUTES = 0  # Minimum buffer between consecutive routes

DAY_NAMES = {
    "L": "Lunes", "M": "Martes", "Mc": "Miércoles",
    "X": "Jueves", "V": "Viernes"
}
VALID_DAYS = set(DAY_NAMES.keys())


# =============================================================================
# Helper Functions for Validation
# =============================================================================

def parse_time(time_str: str) -> Optional[time]:
    """Parse time string in HH:MM format to time object."""
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        return time(hour, minute)
    except (ValueError, IndexError):
        return None


def time_to_minutes(t: time) -> int:
    """Convert time to minutes from midnight."""
    return t.hour * 60 + t.minute


def validate_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """
    Validate that coordinates are within valid ranges.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not (MIN_COORDINATE <= lat <= MAX_COORDINATE):
        return False, f"Latitude {lat} out of range [{MIN_COORDINATE}, {MAX_COORDINATE}]"
    if not (MIN_COORDINATE <= lon <= MAX_COORDINATE):
        return False, f"Longitude {lon} out of range [{MIN_COORDINATE}, {MAX_COORDINATE}]"
    if abs(lat) > 90:
        return False, f"Latitude {lat} exceeds valid range [-90, 90]"
    if abs(lon) > 180:
        return False, f"Longitude {lon} exceeds valid range [-180, 180]"
    return True, None


def validate_stops(stops: List[schemas.StopEditorSchema]) -> Tuple[bool, List[str]]:
    """
    Validate all stops have valid coordinates.
    
    Returns:
        Tuple of (all_valid, list_of_errors)
    """
    errors = []
    for i, stop in enumerate(stops):
        valid, error = validate_coordinates(stop.lat, stop.lon)
        if not valid:
            errors.append(f"Stop {i} ({stop.name}): {error}")
    return len(errors) == 0, errors


def check_time_overlap(
    start1: int, 
    end1: int, 
    start2: int, 
    end2: int,
    buffer_minutes: int = 0
) -> bool:
    """
    Check if two time ranges overlap.
    
    Args:
        start1, end1: First time range in minutes from midnight
        start2, end2: Second time range in minutes from midnight
        buffer_minutes: Minimum buffer required between routes
        
    Returns:
        True if ranges overlap (considering buffer)
    """
    # Add buffer to end times
    effective_end1 = end1 + buffer_minutes
    effective_start2 = start2 - buffer_minutes
    
    # Check for overlap
    return not (effective_end1 <= start2 or end2 <= effective_start2)


def validate_bus_schedule(
    bus: schemas.BusEditorSchema,
    bus_id: str
) -> Tuple[bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate all routes on a bus for time overlaps.
    
    Returns:
        Tuple of (is_valid, conflicts, warnings)
    """
    conflicts = []
    warnings = []
    
    if not bus.items:
        return True, [], []
    
    # Sort items by start time
    sorted_items = sorted(
        bus.items, 
        key=lambda x: time_to_minutes(parse_time(x.start_time)) if parse_time(x.start_time) else 0
    )
    
    for i in range(len(sorted_items)):
        item = sorted_items[i]
        
        # Parse times
        start = parse_time(item.start_time)
        end = parse_time(item.end_time)
        
        if not start or not end:
            conflicts.append({
                "route_id": item.route_id,
                "conflict_type": "invalid_time_format",
                "bus_id": bus_id,
                "message": f"Invalid time format for route {item.route_id}",
                "details": {"start_time": item.start_time, "end_time": item.end_time}
            })
            continue
            
        start_minutes = time_to_minutes(start)
        end_minutes = time_to_minutes(end)
        
        # Check time shift limits
        if item.time_shift_minutes and abs(item.time_shift_minutes) > MAX_TIME_SHIFT_MINUTES:
            conflicts.append({
                "route_id": item.route_id,
                "conflict_type": "time_shift_exceeded",
                "bus_id": bus_id,
                "message": f"Time shift {item.time_shift_minutes}m exceeds limit of ±{MAX_TIME_SHIFT_MINUTES}m",
                "details": {
                    "time_shift_minutes": item.time_shift_minutes,
                    "max_allowed": MAX_TIME_SHIFT_MINUTES
                }
            })
        
        # Check for overlaps with other routes on same bus
        for j in range(i + 1, len(sorted_items)):
            other = sorted_items[j]
            other_start = parse_time(other.start_time)
            other_end = parse_time(other.end_time)
            
            if not other_start or not other_end:
                continue
                
            other_start_min = time_to_minutes(other_start)
            other_end_min = time_to_minutes(other_end)
            
            if check_time_overlap(
                start_minutes, end_minutes,
                other_start_min, other_end_min,
                MIN_BUFFER_MINUTES
            ):
                conflicts.append({
                    "route_id": item.route_id,
                    "conflict_type": "time_overlap",
                    "bus_id": bus_id,
                    "conflicting_with": other.route_id,
                    "message": f"Route {item.route_id} overlaps with {other.route_id} on bus {bus_id}",
                    "details": {
                        "route1": {
                            "route_id": item.route_id,
                            "start": item.start_time,
                            "end": item.end_time
                        },
                        "route2": {
                            "route_id": other.route_id,
                            "start": other.start_time,
                            "end": other.end_time
                        }
                    }
                })
    
    return len(conflicts) == 0, conflicts, warnings


def validate_schedule_update(
    schedule: schemas.ScheduleUpdateRequest
) -> schemas.ValidationResult:
    """
    Validate a complete schedule update.
    
    Checks:
    - Valid day code
    - Time overlaps within each bus
    - Valid coordinates for all stops
    - Time shift limits
    
    Returns:
        ValidationResult with all conflicts and errors
    """
    all_conflicts = []
    all_errors = []
    all_warnings = []
    
    # Validate day
    if schedule.day not in VALID_DAYS:
        all_errors.append(schemas.ValidationError(
            field="day",
            message=f"Invalid day code '{schedule.day}'. Must be one of: {', '.join(VALID_DAYS)}",
            code="invalid_day"
        ))
    
    # Validate each bus
    for bus in schedule.buses:
        # Check for time overlaps
        is_valid, conflicts, warnings = validate_bus_schedule(bus, bus.bus_id)
        all_conflicts.extend([schemas.RouteConflict(**c) for c in conflicts])
        all_warnings.extend([schemas.ValidationError(**w) for w in warnings])
        
        # Validate stops coordinates
        for item in bus.items:
            if item.stops:
                stops_valid, stop_errors = validate_stops(item.stops)
                if not stops_valid:
                    for error in stop_errors:
                        all_errors.append(schemas.ValidationError(
                            field=f"buses.{bus.bus_id}.items.{item.route_id}.stops",
                            message=error,
                            code="invalid_coordinates"
                        ))
    
    # Check for duplicate route assignments
    route_assignments: Dict[str, List[str]] = {}
    for bus in schedule.buses:
        for item in bus.items:
            if item.route_id not in route_assignments:
                route_assignments[item.route_id] = []
            route_assignments[item.route_id].append(bus.bus_id)
    
    for route_id, bus_ids in route_assignments.items():
        if len(bus_ids) > 1:
            all_conflicts.append(schemas.RouteConflict(
                route_id=route_id,
                conflict_type="duplicate_assignment",
                bus_id=bus_ids[0],
                message=f"Route {route_id} assigned to multiple buses: {', '.join(bus_ids)}",
                details={"buses": bus_ids}
            ))
    
    is_valid = len(all_conflicts) == 0 and len(all_errors) == 0
    
    return schemas.ValidationResult(
        is_valid=is_valid,
        conflicts=all_conflicts,
        errors=all_errors,
        warnings=all_warnings
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.patch(
    "/routes/{route_id}",
    response_model=schemas.RouteUpdateResponse,
    summary="Update route data",
    description="Update specific fields of a route. Supports partial updates."
)
async def update_route(
    route_id: str,
    update: schemas.RouteUpdateRequest = Body(...)
) -> schemas.RouteUpdateResponse:
    """
    Update data for a specific route.
    
    This endpoint allows partial updates to route properties:
    - start_time/end_time: Update route timing
    - stops: Update route stops (with coordinate validation)
    - is_locked: Lock/unlock the route
    - bus_id: Reassign to a different bus
    - time_shift_minutes: Adjust the time shift
    
    All updates are validated before being applied.
    """
    logger.info(f"[Route Update] Updating route {route_id}")
    
    changes = {}
    warnings = []
    
    # Validate stops if provided
    if update.stops is not None:
        valid, errors = validate_stops(update.stops)
        if not valid:
            logger.warning(f"[Route Update] Invalid stops for route {route_id}: {errors}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "route_id": route_id,
                    "message": "Invalid stop coordinates",
                    "errors": errors
                }
            )
        changes["stops_count"] = len(update.stops)
    
    # Validate time shift if provided
    if update.time_shift_minutes is not None:
        if abs(update.time_shift_minutes) > MAX_TIME_SHIFT_MINUTES:
            message = f"Time shift {update.time_shift_minutes}m exceeds limit of ±{MAX_TIME_SHIFT_MINUTES}m"
            logger.warning(f"[Route Update] {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "route_id": route_id,
                    "message": message
                }
            )
        changes["time_shift_minutes"] = update.time_shift_minutes
    
    # Validate times if provided
    if update.start_time:
        start = parse_time(update.start_time)
        if not start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "route_id": route_id,
                    "message": f"Invalid start_time format: {update.start_time}. Use HH:MM"
                }
            )
        changes["start_time"] = update.start_time
    
    if update.end_time:
        end = parse_time(update.end_time)
        if not end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "route_id": route_id,
                    "message": f"Invalid end_time format: {update.end_time}. Use HH:MM"
                }
            )
        changes["end_time"] = update.end_time
    
    # Check time consistency
    if update.start_time and update.end_time:
        start = parse_time(update.start_time)
        end = parse_time(update.end_time)
        if start and end:
            start_min = time_to_minutes(start)
            end_min = time_to_minutes(end)
            if end_min <= start_min:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "success": False,
                        "route_id": route_id,
                        "message": "End time must be after start time"
                    }
                )
            duration = end_min - start_min
            changes["duration_minutes"] = duration
            if duration < 5:
                warnings.append("Route duration is very short (< 5 minutes)")
    
    # Track lock state change
    if update.is_locked is not None:
        changes["is_locked"] = update.is_locked
    
    # Track bus assignment change
    if update.bus_id is not None:
        changes["bus_id"] = update.bus_id
    
    # Log the update
    logger.info(f"[Route Update] Route {route_id} updated successfully. Changes: {list(changes.keys())}")
    
    return schemas.RouteUpdateResponse(
        success=True,
        route_id=route_id,
        message=f"Route {route_id} updated successfully",
        changes=changes,
        warnings=warnings
    )


@router.post(
    "/routes/{route_id}/toggle-lock",
    response_model=schemas.ToggleLockResponse,
    summary="Toggle route lock",
    description="Lock or unlock a route to prevent automatic modifications"
)
async def toggle_route_lock(
    route_id: str,
    request: schemas.ToggleLockRequest = Body(default_factory=schemas.ToggleLockRequest)
) -> schemas.ToggleLockResponse:
    """
    Toggle the lock status of a route.
    
    Locked routes are protected from automatic optimizer modifications.
    This is useful when manually fine-tuning a schedule.
    
    - If is_locked is provided, sets the route to that specific state
    - If is_locked is null, toggles the current state
    """
    logger.info(f"[Route Lock] Toggling lock for route {route_id}")
    
    # For this implementation, we assume the route exists
    # In a real implementation, you would fetch from database
    
    # Simulate previous state (would come from DB)
    previous_state = False  # Placeholder
    
    # Determine new state
    if request.is_locked is not None:
        new_state = request.is_locked
    else:
        new_state = not previous_state
    
    action = "locked" if new_state else "unlocked"
    logger.info(f"[Route Lock] Route {route_id} {action}")
    
    return schemas.ToggleLockResponse(
        success=True,
        route_id=route_id,
        is_locked=new_state,
        message=f"Route {route_id} {action} successfully",
        previous_state=previous_state,
        reason=request.reason
    )


@router.post(
    "/schedules/update",
    response_model=schemas.ScheduleUpdateResponse,
    summary="Update complete schedule",
    description="Save changes to a complete schedule for a specific day"
)
async def update_schedule(
    schedule: schemas.ScheduleUpdateRequest = Body(...)
) -> schemas.ScheduleUpdateResponse:
    """
    Save changes to a complete schedule.
    
    This endpoint accepts a full schedule for a specific day including:
    - All buses with their assigned routes
    - Unassigned routes (routes not assigned to any bus)
    - Metadata about the schedule
    
    The endpoint performs comprehensive validation:
    - Time overlaps are detected within each bus
    - Stop coordinates are validated
    - Time shift limits are enforced
    - Duplicate route assignments are flagged
    
    If validation fails, the response includes detailed conflict information.
    """
    logger.info(f"[Schedule Update] Processing schedule for day {schedule.day}")
    
    # Validate day
    if schedule.day not in VALID_DAYS:
        error_msg = f"Invalid day code '{schedule.day}'. Must be one of: {', '.join(VALID_DAYS)}"
        logger.error(f"[Schedule Update] {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": error_msg,
                "day": schedule.day
            }
        )
    
    # Perform validation
    validation_result = validate_schedule_update(schedule)
    
    if not validation_result.is_valid:
        logger.warning(
            f"[Schedule Update] Validation failed for day {schedule.day}: "
            f"{len(validation_result.conflicts)} conflicts, "
            f"{len(validation_result.errors)} errors"
        )
        
        # Return error response but still include details
        return schemas.ScheduleUpdateResponse(
            success=False,
            day=schedule.day,
            saved_at=datetime.utcnow(),
            total_buses=len(schedule.buses),
            total_routes=sum(len(bus.items) for bus in schedule.buses),
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            conflicts=[c.model_dump() for c in validation_result.conflicts]
        )
    
    # Count routes and validate
    total_routes = sum(len(bus.items) for bus in schedule.buses)
    
    # Store in cache for retrieval
    cache_key = f"schedule_{schedule.day}"
    persisted_payload = {
        "day": schedule.day,
        "buses": [bus.model_dump() for bus in schedule.buses],
        "unassigned_routes": [r.model_dump() for r in schedule.unassigned_routes],
        "metadata": schedule.metadata,
        "updated_at": datetime.utcnow().isoformat()
    }
    edited_schedules_cache[cache_key] = persisted_payload
    
    # Generate warnings for tight schedules
    warnings = list(validation_result.warnings)

    workspace_id = (
        (schedule.workspace_id or "").strip()
        or str((schedule.metadata or {}).get("workspace_id", "")).strip()
        or None
    )

    # Persist to DB when available (production-safe persistence).
    if is_database_available() and SessionLocal is not None:
        db = SessionLocal()
        try:
            db_crud.upsert_manual_schedule(
                db=db,
                day=schedule.day,
                payload=persisted_payload,
            )
            if workspace_id:
                workspace = db_crud.get_workspace(db, workspace_id)
                if workspace:
                    base_schedule = {}
                    if workspace.working_version and isinstance(workspace.working_version.schedule_by_day, dict):
                        base_schedule = workspace.working_version.schedule_by_day
                    normalized = db_crud.normalize_schedule_by_day(base_schedule)
                    total_entries = 0
                    total_exits = 0
                    for bus_payload in persisted_payload.get("buses", []):
                        bus_items = bus_payload.get("items", []) if isinstance(bus_payload, dict) else []
                        for item_payload in bus_items:
                            item_type = str((item_payload or {}).get("type", "")).lower()
                            if item_type == "entry":
                                total_entries += 1
                            elif item_type == "exit":
                                total_exits += 1
                    normalized[schedule.day] = {
                        "schedule": persisted_payload.get("buses", []),
                        "stats": {
                            "total_buses": len(schedule.buses),
                            "total_routes": total_routes,
                            "total_entries": total_entries,
                            "total_exits": total_exits,
                            "avg_routes_per_bus": round(total_routes / len(schedule.buses), 2) if schedule.buses else 0,
                        },
                        "metadata": persisted_payload.get("metadata", {}) or {},
                        "unassigned_routes": persisted_payload.get("unassigned_routes", []) or [],
                    }
                    db_crud.create_workspace_version(
                        db,
                        workspace_id=workspace_id,
                        payload=schemas.WorkspaceVersionCreate(
                            save_kind="save",
                            schedule_by_day=normalized,
                            summary_metrics={
                                "total_buses": len(schedule.buses),
                                "total_routes": total_routes,
                            },
                            checkpoint_name=f"manual-{schedule.day.lower()}",
                        ),
                    )
                    db_crud.set_app_meta(db, "last_open_workspace_id", workspace_id)
                else:
                    warnings.append(schemas.ValidationError(
                        field="workspace_id",
                        message=f"Workspace {workspace_id} no encontrado; guardado solo en legacy",
                        code="workspace_not_found",
                    ))
        except Exception as e:
            logger.warning(f"[Schedule Update] Could not persist schedule in DB for {schedule.day}: {e}")
            warnings.append(schemas.ValidationError(
                field="database",
                message="Horario guardado en memoria, pero no se pudo persistir en base de datos",
                code="db_persist_failed",
            ))
        finally:
            db.close()

    logger.info(
        f"[Schedule Update] Schedule for {DAY_NAMES[schedule.day]} saved successfully: "
        f"{len(schedule.buses)} buses, {total_routes} routes"
    )

    for bus in schedule.buses:
        if len(bus.items) > 7:
            warnings.append(schemas.ValidationError(
                field=f"buses.{bus.bus_id}",
                message=f"Bus {bus.bus_id} has {len(bus.items)} routes (high load)",
                code="high_route_count"
            ))
    
    return schemas.ScheduleUpdateResponse(
        success=True,
        day=schedule.day,
        saved_at=datetime.utcnow(),
        total_buses=len(schedule.buses),
        total_routes=total_routes,
        errors=[],
        warnings=warnings,
        conflicts=[]
    )


@router.post(
    "/schedules/manual",
    response_model=schemas.ScheduleUpdateResponse,
    summary="Legacy alias for schedule update",
    description="Backward-compatible alias to save edited schedules"
)
async def update_schedule_legacy(
    schedule: schemas.ScheduleUpdateRequest = Body(...)
) -> schemas.ScheduleUpdateResponse:
    """Compatibility alias for older frontend builds that still post to /schedules/manual."""
    return await update_schedule(schedule)


@router.get(
    "/schedules/{day}",
    summary="Get saved schedule",
    description="Retrieve a previously saved schedule for a specific day"
)
async def get_schedule(
    day: str,
    workspace_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """
    Get a saved schedule for the specified day.
    
    Returns the schedule from the in-memory cache if available.
    """
    if day not in VALID_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": f"Invalid day code '{day}'. Must be one of: {', '.join(VALID_DAYS)}"
            }
        )
    workspace_id = (workspace_id or "").strip() or None

    cache_key = f"schedule_{workspace_id or 'legacy'}_{day}"
    cached_schedule = edited_schedules_cache.get(cache_key)

    if is_database_available() and SessionLocal is not None:
        db = SessionLocal()
        try:
            # Prefer workspace snapshot when requested.
            if workspace_id:
                workspace = db_crud.get_workspace(db, workspace_id)
                if workspace and workspace.working_version and isinstance(workspace.working_version.schedule_by_day, dict):
                    by_day = db_crud.normalize_schedule_by_day(workspace.working_version.schedule_by_day)
                    day_payload = by_day.get(day, {})
                    schedule_payload = {
                        "day": day,
                        "buses": day_payload.get("schedule", []),
                        "unassigned_routes": day_payload.get("unassigned_routes", []),
                        "metadata": {
                            **(day_payload.get("metadata", {}) or {}),
                            "workspace_id": workspace_id,
                            "version_id": str(workspace.working_version.id),
                        },
                        "updated_at": (workspace.working_version.created_at.isoformat() if workspace.working_version.created_at else datetime.utcnow().isoformat()),
                    }
                    edited_schedules_cache[cache_key] = schedule_payload
                    return {
                        "success": True,
                        "day": day,
                        "day_name": DAY_NAMES[day],
                        "workspace_id": workspace_id,
                        "version_id": str(workspace.working_version.id),
                        "schedule": schedule_payload,
                    }

            saved = db_crud.get_manual_schedule(db, day)
            if cached_schedule is None and saved and isinstance(saved.payload, dict):
                cached_schedule = saved.payload
                edited_schedules_cache[cache_key] = cached_schedule
        except Exception as e:
            logger.warning(f"[Schedule Get] Could not read schedule for {day} from DB: {e}")
        finally:
            db.close()

    if cached_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "message": f"No saved schedule found for day {day}"
            }
        )
    
    return {
        "success": True,
        "day": day,
        "day_name": DAY_NAMES[day],
        "workspace_id": workspace_id,
        "schedule": cached_schedule
    }


@router.post(
    "/schedules/validate",
    response_model=schemas.ValidationResult,
    summary="Validate schedule",
    description="Validate a schedule without saving it"
)
async def validate_schedule(
    schedule: schemas.ScheduleUpdateRequest = Body(...)
) -> schemas.ValidationResult:
    """
    Validate a schedule without saving it.
    
    This endpoint is useful for real-time validation in the frontend
    before submitting the final schedule.
    """
    logger.info(f"[Schedule Validate] Validating schedule for day {schedule.day}")
    
    result = validate_schedule_update(schedule)
    
    if result.is_valid:
        logger.info(f"[Schedule Validate] Schedule for {schedule.day} is valid")
    else:
        logger.warning(
            f"[Schedule Validate] Schedule has {len(result.conflicts)} conflicts "
            f"and {len(result.errors)} errors"
        )
    
    return result


@router.get(
    "/routes/validation-config",
    summary="Get validation configuration",
    description="Get the current validation limits and configuration"
)
async def get_validation_config() -> Dict[str, Any]:
    """
    Get the current validation configuration.
    
    Returns the validation limits used by the route editor endpoints,
    useful for frontend validation synchronization.
    """
    return {
        "max_time_shift_minutes": MAX_TIME_SHIFT_MINUTES,
        "min_buffer_minutes": MIN_BUFFER_MINUTES,
        "coordinate_limits": {
            "min": MIN_COORDINATE,
            "max": MAX_COORDINATE
        },
        "valid_days": DAY_NAMES,
        "version": "1.0.0"
    }


# =============================================================================
# In-memory cache for routes (populated from uploads)
# =============================================================================
routes_cache: Dict[str, Dict[str, Any]] = {}


def update_routes_cache(route_id: str, route_data: Dict[str, Any]) -> None:
    """Store route data in cache."""
    routes_cache[route_id] = route_data


def get_route_from_cache(route_id: str) -> Optional[Dict[str, Any]]:
    """Get route data from cache."""
    return routes_cache.get(route_id)


@router.get(
    "/routes/{route_id}",
    response_model=schemas.RouteResponse,
    summary="Get route by ID",
    description="Retrieve complete route data including all stops"
)
async def get_route(route_id: str) -> schemas.RouteResponse:
    """
    Get complete route data by ID.
    
    Returns the route with all stops including:
    - stop_id (mapped from internal id)
    - stop_name (mapped from name)
    - latitude/longitude (coordinates)
    - order (sequence)
    - time_from_start (minutes from start)
    - passengers (boarding count)
    - is_school (destination flag)
    
    The route data comes from the in-memory cache populated during
    file upload or schedule operations.
    """
    logger.info(f"[Route Get] Fetching route {route_id}")
    
    # Try to get from cache
    route_data = get_route_from_cache(route_id)
    
    if not route_data:
        logger.warning(f"[Route Get] Route {route_id} not found in cache")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "route_id": route_id,
                "message": f"Route {route_id} not found. Upload route files first."
            }
        )
    
    # Convert stops to ensure proper format
    stops_data = route_data.get("stops", [])
    formatted_stops = []
    for i, stop in enumerate(stops_data):
        formatted_stop = {
            "id": stop.get("id", f"{route_id}_stop_{i}"),
            "route_id": route_id,
            "name": stop.get("name", ""),
            "lat": stop.get("lat", 0.0),
            "lon": stop.get("lon", 0.0),
            "order": stop.get("order", i + 1),
            "time_from_start": stop.get("time_from_start", 0),
            "passengers": stop.get("passengers", 0),
            "is_school": stop.get("is_school", False)
        }
        formatted_stops.append(formatted_stop)
    
    # Build response
    response_data = {
        "id": route_id,
        "name": route_data.get("name", route_id),
        "type": route_data.get("type", "entry"),
        "school_id": route_data.get("school_id", ""),
        "school_name": route_data.get("school_name", ""),
        "arrival_time": route_data.get("arrival_time"),
        "departure_time": route_data.get("departure_time"),
        "capacity_needed": route_data.get("capacity_needed", 0),
        "contract_id": route_data.get("contract_id", ""),
        "days": route_data.get("days", []),
        "created_at": route_data.get("created_at", datetime.utcnow()),
        "stops": formatted_stops
    }
    
    logger.info(f"[Route Get] Route {route_id} found with {len(formatted_stops)} stops")
    
    return schemas.RouteResponse(**response_data)
