"""
CRUD operations for Tutti database.

Provides functions to create, read, update, and delete:
- Routes with stops
- Optimization jobs
- Optimization results
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

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
