"""
Celery tasks for Tutti optimization.

Provides async task processing for route optimization jobs.
"""

from celery_app import celery_app
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import logging
import os
import asyncio

from models import Route, BusSchedule
from db.database import SessionLocal, is_database_available
from db.models import OptimizationJob
from optimizer_v6 import optimize_v6
try:
    from services.fleet_assignment import assign_fleet_profiles_to_schedule
except ImportError:
    from backend.services.fleet_assignment import assign_fleet_profiles_to_schedule

logger = logging.getLogger(__name__)

# Import config if available
try:
    from config import config
    CELERY_ENABLED = config.CELERY_ENABLED
except ImportError:
    CELERY_ENABLED = os.getenv("CELERY_ENABLED", "true").lower() == "true"


def _create_progress_callback(
    celery_task, 
    job_id: str,
    update_interval: float = 1.0
) -> Callable:
    """
    Create a progress callback function that updates Celery state and Redis.
    
    Args:
        celery_task: The Celery task instance (self)
        job_id: The job ID for tracking
        update_interval: Minimum seconds between updates
        
    Returns:
        Callback function for optimizer_v6
    """
    last_update_time = [0.0]  # Use list for mutable closure
    last_progress = [0]  # Track last progress to avoid duplicate updates
    
    def callback(phase: str, progress: int, message: str):
        import time
        
        current_time = time.time()
        
        # Skip if progress hasn't changed significantly and interval hasn't passed
        if (progress - last_progress[0] < 5 and 
            current_time - last_update_time[0] < update_interval and
            progress not in [0, 100]):  # Always send 0% and 100%
            return
        
        last_update_time[0] = current_time
        last_progress[0] = progress
        
        # Update Celery task state
        try:
            celery_task.update_state(
                state="PROGRESS",
                meta={
                    "phase": phase,
                    "progress": progress,
                    "message": message,
                    "job_id": job_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update Celery state: {e}")
        
        # Publish to Redis for WebSocket if available
        try:
            _publish_to_redis(job_id, phase, progress, message)
        except Exception as e:
            logger.debug(f"Redis publish failed (WebSocket may be unavailable): {e}")
    
    return callback


def _publish_to_redis(job_id: str, phase: str, progress: int, message: str) -> bool:
    """
    Publish progress update to Redis for WebSocket distribution.
    
    Args:
        job_id: The job ID
        phase: Current optimization phase
        progress: Progress percentage
        message: Human-readable message
        
    Returns:
        True if published successfully
    """
    try:
        import redis
        import json
        
        from config import config
        
        if not config.is_redis_available():
            return False
        
        client = redis.Redis.from_url(config.REDIS_URL)
        
        data = {
            "job_id": job_id,
            "type": "progress",
            "phase": phase,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Publish to channel specific to this job
        client.publish(f"job_progress:{job_id}", json.dumps(data))
        
        # Also publish to general progress channel
        client.publish("job_progress:all", json.dumps(data))
        
        return True
        
    except Exception as e:
        logger.debug(f"Redis publish error: {e}")
        return False


def _publish_dict_to_redis(job_id: str, data: Dict[str, Any]) -> bool:
    """
    Publica un payload arbitrario en el canal del job.
    """
    try:
        import redis
        import json
        from config import config

        if not config.is_redis_available():
            return False

        client = redis.Redis.from_url(config.REDIS_URL)
        payload = dict(data)
        payload["job_id"] = job_id
        payload.setdefault("timestamp", datetime.utcnow().isoformat())
        client.publish(f"job_progress:{job_id}", json.dumps(payload))
        client.publish("job_progress:all", json.dumps(payload))
        return True
    except Exception as e:
        logger.debug(f"Redis publish payload error: {e}")
        return False


@celery_app.task(bind=True, max_retries=3)
def optimize_task(
    self,
    routes_data: List[Dict[str, Any]],
    job_id: str,
    use_ml_assignment: bool = True,
) -> Dict[str, Any]:
    """
    Tarea Celery para optimizar rutas con reporte de progreso en tiempo real.
    
    Args:
        routes_data: Lista de rutas serializadas
        job_id: ID del job en PostgreSQL
    
    Returns:
        dict: Resultado de la optimización
    """
    db = None
    job = None
    
    # Create progress callback
    progress_callback = _create_progress_callback(self, job_id)
    
    try:
        # Report initial progress
        progress_callback("starting", 0, "Iniciando optimización...")
        
        # Actualizar estado a running si la base de datos está disponible
        if is_database_available():
            try:
                db = SessionLocal()
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "running"
                    job.started_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update job status in database: {e}")
        
        # Convertir datos a modelos Pydantic
        progress_callback("loading", 2, "Cargando datos de rutas...")
        routes = [Route(**r) for r in routes_data]
        
        logger.info(f"[Celery] Starting optimization for job {job_id} with {len(routes)} routes")
        
        # Ejecutar optimización con callback de progreso
        schedule = optimize_v6(
            routes,
            progress_callback=progress_callback,
            use_ml_assignment=use_ml_assignment,
        )
        schedule, fleet_assignment = assign_fleet_profiles_to_schedule(schedule)
        
        # Calcular estadísticas
        progress_callback("calculating_stats", 95, "Calculando estadísticas...")
        stats = _calculate_stats(schedule)
        
        # Serializar resultado
        result = {
            "schedule": [s.dict() for s in schedule],
            "stats": stats,
            "optimization_options": {
                "use_ml_assignment": bool(use_ml_assignment),
            },
            "fleet_assignment": fleet_assignment,
        }
        
        logger.info(f"[Celery] Optimization completed for job {job_id}: {stats['total_buses']} buses")
        
        # Actualizar job en DB si está disponible
        if is_database_available():
            try:
                db = SessionLocal() if db is None else db
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.result = result
                    job.stats = stats
                    job.completed_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update job result in database: {e}")
        
        # Notify completion via Redis
        try:
            _publish_to_redis(job_id, "completed", 100, "Optimización completada exitosamente")
        except Exception:
            pass
        
        return result
        
    except Exception as exc:
        error_message = str(exc)
        logger.error(f"[Celery] Optimization failed for job {job_id}: {exc}")
        
        # Notify error via Redis
        try:
            import json
            from config import config
            import redis
            
            if config.is_redis_available():
                client = redis.Redis.from_url(config.REDIS_URL)
                error_data = {
                    "job_id": job_id,
                    "type": "error",
                    "error_code": "OPTIMIZATION_FAILED",
                    "message": error_message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                client.publish(f"job_progress:{job_id}", json.dumps(error_data))
        except Exception:
            pass
        
        # Actualizar estado a failed si la DB está disponible
        if is_database_available():
            try:
                db = SessionLocal() if db is None else db
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = error_message
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update job error status: {e}")
        
        # Retry automático con backoff
        retry_count = self.request.retries
        countdown = 60 * (2 ** retry_count)  # 60s, 120s, 240s
        
        logger.info(f"[Celery] Retrying job {job_id} in {countdown}s (attempt {retry_count + 1}/3)")
        raise self.retry(exc=exc, countdown=countdown)
        
    finally:
        if db:
            db.close()


def _calculate_stats(schedule: List[BusSchedule]) -> Dict[str, Any]:
    """Calcular estadísticas del schedule."""
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


@celery_app.task(bind=True, max_retries=3)
def optimize_advanced_task(
    self, 
    routes_data: List[Dict[str, Any]], 
    job_id: str,
    weights: Optional[Dict[str, float]] = None,
    preset: Optional[str] = None,
    use_lns: bool = True,
    use_ml_assignment: bool = True,
) -> Dict[str, Any]:
    """
    Tarea Celery para optimización avanzada con multi-objetivo y LNS.
    
    Args:
        routes_data: Lista de rutas serializadas
        job_id: ID del job en PostgreSQL
        weights: Pesos personalizados para función objetivo
        preset: Nombre del preset a usar
        use_lns: Usar LNS para mejorar solución
    
    Returns:
        dict: Resultado de la optimización con métricas multi-objetivo
    """
    db = None
    
    # Create progress callback
    progress_callback = _create_progress_callback(self, job_id)
    
    try:
        # Report initial progress
        progress_callback("starting", 0, "Iniciando optimización avanzada...")
        
        # Actualizar estado a running si la base de datos está disponible
        if is_database_available():
            try:
                db = SessionLocal()
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "running"
                    job.started_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update job status in database: {e}")
        
        # Convertir datos a modelos Pydantic
        progress_callback("loading", 2, "Cargando datos de rutas...")
        routes = [Route(**r) for r in routes_data]
        
        logger.info(f"[Celery-Advanced] Starting optimization for job {job_id} with {len(routes)} routes")
        
        # Importar aquí para evitar circular imports
        from optimizer_multi import ObjectiveWeights, MultiObjectiveOptimizer
        from optimizer_lns import optimize_v6_lns
        
        # Determinar pesos
        if preset:
            from config import ObjectivePresets
            weights_dict = ObjectivePresets.get_preset(preset)
            logger.info(f"[Celery-Advanced] Using preset: {preset}")
        else:
            weights_dict = weights
            logger.info(f"[Celery-Advanced] Using custom/default weights")
        
        # Crear objetos de pesos
        if weights_dict:
            weights_obj = ObjectiveWeights(**weights_dict)
        else:
            weights_obj = ObjectiveWeights()
        
        # Ejecutar optimización
        progress_callback("optimizing", 10, f"Optimizando con {'LNS' if use_lns else 'Greedy'}...")
        schedule = optimize_v6_lns(
            routes,
            weights=weights_obj,
            use_lns=use_lns,
            progress_callback=progress_callback,
            use_ml_assignment=use_ml_assignment,
        )
        schedule, fleet_assignment = assign_fleet_profiles_to_schedule(schedule)
        
        # Calcular estadísticas
        progress_callback("calculating_stats", 95, "Calculando estadísticas...")
        stats = _calculate_stats(schedule)
        
        # Calcular métricas multi-objetivo
        evaluator = MultiObjectiveOptimizer(weights_obj)
        metrics = evaluator.calculate_metrics(schedule)
        score = evaluator.evaluate_schedule(schedule)
        
        # Serializar resultado
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
            },
            "fleet_assignment": fleet_assignment,
        }
        
        logger.info(f"[Celery-Advanced] Optimization completed for job {job_id}: {stats['total_buses']} buses, score={score:.2f}")
        
        # Actualizar job en DB si está disponible
        if is_database_available():
            try:
                db = SessionLocal() if db is None else db
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.result = result
                    job.stats = stats
                    job.completed_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update job result in database: {e}")
        
        # Notify completion via Redis
        try:
            _publish_to_redis(job_id, "completed", 100, "Optimización completada exitosamente")
        except Exception:
            pass
        
        return result
        
    except Exception as exc:
        error_message = str(exc)
        logger.error(f"[Celery-Advanced] Optimization failed for job {job_id}: {exc}")
        
        # Notify error via Redis
        try:
            import json
            from config import config
            import redis
            
            if config.is_redis_available():
                client = redis.Redis.from_url(config.REDIS_URL)
                error_data = {
                    "job_id": job_id,
                    "type": "error",
                    "error_code": "OPTIMIZATION_FAILED",
                    "message": error_message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                client.publish(f"job_progress:{job_id}", json.dumps(error_data))
        except Exception:
            pass
        
        # Actualizar estado a failed si la DB está disponible
        if is_database_available():
            try:
                db = SessionLocal() if db is None else db
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = error_message
                    db.commit()
            except Exception as e:
                logger.warning(f"Could not update job error status: {e}")
        
        # Retry automático con backoff
        retry_count = self.request.retries
        countdown = 60 * (2 ** retry_count)  # 60s, 120s, 240s
        
        logger.info(f"[Celery-Advanced] Retrying job {job_id} in {countdown}s (attempt {retry_count + 1}/3)")
        raise self.retry(exc=exc, countdown=countdown)
        
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=2)
def optimize_pipeline_task(
    self,
    routes_data: List[Dict[str, Any]],
    job_id: str,
    pipeline_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Tarea Celery para pipeline de optimización + validación global OSRM.
    """
    db = None
    current_stage = "starting"

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

    def progress_callback(phase: str, progress: int, message: str, extra: Optional[Dict[str, Any]] = None):
        nonlocal current_stage
        current_stage = phase
        extra_data = extra or {}
        meta = {
            "phase": phase,
            "progress": progress,
            "message": message,
            "job_id": job_id,
            "stage": extra_data.get("stage", phase),
            "day": extra_data.get("day"),
            "iteration": extra_data.get("iteration"),
            "metrics": extra_data.get("metrics"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        for key, value in extra_data.items():
            if key in {"phase", "progress", "message", "job_id", "timestamp"}:
                continue
            meta[key] = value
        try:
            self.update_state(state="PROGRESS", meta=meta)
        except Exception as e:
            logger.warning(f"[Pipeline] Failed to update celery state: {e}")

        _publish_dict_to_redis(job_id, {
            "type": "progress",
            **meta,
        })

    try:
        progress_callback("starting", 0, "Iniciando pipeline automático...")

        # Marcar job como running
        if is_database_available():
            try:
                db = SessionLocal()
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "running"
                    job.started_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"[Pipeline] Could not mark job running: {e}")

        routes = [Route(**route_data) for route_data in routes_data]
        config_obj = PipelineConfig.from_dict(pipeline_config)

        result = asyncio.run(
            run_optimization_pipeline_by_day(
                routes=routes,
                config=config_obj,
                progress_callback=progress_callback,
            )
        )

        if is_database_available():
            try:
                db = SessionLocal() if db is None else db
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.result = result
                    job.stats = result.get("summary_metrics")
                    job.completed_at = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"[Pipeline] Could not persist job result: {e}")

        _publish_dict_to_redis(job_id, {
            "type": "progress",
            "phase": "completed",
            "progress": 100,
            "stage": "completed",
            "message": "Pipeline completado exitosamente",
            "metrics": result.get("summary_metrics"),
        })

        return result

    except Exception as exc:
        error_message = str(exc)
        logger.error(f"[Pipeline] Failed for job {job_id}: {error_message}")

        _publish_dict_to_redis(job_id, {
            "type": "error",
            "error_code": "PIPELINE_FAILED",
            "message": error_message,
            "stage": current_stage,
        })

        if is_database_available():
            try:
                db = SessionLocal() if db is None else db
                job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = f"{current_stage}: {error_message}"
                    db.commit()
            except Exception as e:
                logger.warning(f"[Pipeline] Could not mark job failed: {e}")

        retry_count = self.request.retries
        countdown = 30 * (2 ** retry_count)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        if db:
            db.close()


@celery_app.task
def cleanup_old_jobs(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up old completed/failed jobs from database.
    
    Args:
        max_age_hours: Maximum age of jobs to keep
        
    Returns:
        dict: Cleanup statistics
    """
    if not is_database_available():
        return {"cleaned": 0, "error": "Database not available"}
    
    from datetime import timedelta
    
    db = SessionLocal()
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Find old completed/failed jobs
        old_jobs = db.query(OptimizationJob).filter(
            OptimizationJob.status.in_(["completed", "failed", "cancelled"]),
            OptimizationJob.created_at < cutoff_time
        ).all()
        
        count = len(old_jobs)
        
        # Delete them
        for job in old_jobs:
            db.delete(job)
        
        db.commit()
        
        logger.info(f"[Celery] Cleaned up {count} old jobs")
        return {"cleaned": count, "max_age_hours": max_age_hours}
        
    except Exception as e:
        logger.error(f"[Celery] Cleanup failed: {e}")
        return {"cleaned": 0, "error": str(e)}
    finally:
        db.close()
