"""
WebSocket endpoint for Monte Carlo simulation with progressive streaming.

Provides real-time Monte Carlo validation results via WebSocket,
streaming batches of simulations as they complete.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional, Tuple
import json
import asyncio
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

# Import Monte Carlo components
try:
    from validation.monte_carlo import (
        MonteCarloValidator,
        check_schedule_feasibility,
        extract_travel_times_from_schedule,
        estimate_base_travel_times,
    )
    from models import Route, BusSchedule
    MONTE_CARLO_AVAILABLE = True
except ImportError:
    try:
        from backend.validation.monte_carlo import (
            MonteCarloValidator,
            check_schedule_feasibility,
            extract_travel_times_from_schedule,
            estimate_base_travel_times,
        )
        from backend.models import Route, BusSchedule
        MONTE_CARLO_AVAILABLE = True
    except ImportError:
        MONTE_CARLO_AVAILABLE = False


# Reference to validation jobs cache (injected from main.py)
validation_jobs_ref: Dict[str, Dict[str, Any]] = {}


def set_validation_jobs_cache(cache: Dict[str, Dict[str, Any]]):
    """Set the validation jobs cache reference."""
    global validation_jobs_ref
    validation_jobs_ref = cache


class MonteCarloStreamingValidator:
    """
    Extended Monte Carlo validator with streaming support.
    
    Validates schedules and yields results in batches for real-time
    streaming to clients via WebSocket.
    """
    
    def __init__(
        self,
        n_simulations: int = 1000,
        time_uncertainty: float = 0.2,
        distribution: str = "lognormal",
        batch_size: int = 50,
        seed: Optional[int] = None
    ):
        self.n_simulations = n_simulations
        self.time_uncertainty = time_uncertainty
        self.distribution = distribution
        self.batch_size = batch_size
        
        if seed is not None:
            random.seed(seed)
        
        # Results tracking
        self.completed = 0
        self.feasible_count = 0
        self.infeasible_count = 0
        self.scenarios: List[Dict[str, Any]] = []
        self.violation_distribution: Dict[int, int] = {}
        self.total_violations = 0
    
    def reset(self):
        """Reset validation state for new run."""
        self.completed = 0
        self.feasible_count = 0
        self.infeasible_count = 0
        self.scenarios = []
        self.violation_distribution = {}
        self.total_violations = 0
    
    def calculate_grade(self, feasible_rate: float) -> str:
        """
        Calculate robustness grade from feasible rate.
        
        Args:
            feasible_rate: Rate of feasible scenarios (0.0 - 1.0)
            
        Returns:
            Grade: 'A' (>95%), 'B' (>85%), 'C' (>70%), 'D' (>50%), 'F' (<50%)
        """
        if feasible_rate >= 0.95:
            return "A"
        elif feasible_rate >= 0.85:
            return "B"
        elif feasible_rate >= 0.70:
            return "C"
        elif feasible_rate >= 0.50:
            return "D"
        else:
            return "F"
    
    def get_grade_interpretation(self, grade: str, feasible_rate: float) -> Dict[str, str]:
        """
        Get human-readable interpretation of the grade.
        
        Args:
            grade: Grade letter (A, B, C, D, F)
            feasible_rate: The actual feasible rate
            
        Returns:
            Dictionary with interpretation details
        """
        interpretations = {
            "A": {
                "meaning": "Más del 95% de escenarios válidos",
                "description": "El horario es muy robusto. Incluso con variaciones significativas de tráfico, el horario cumple casi siempre.",
                "recommendation": "El horario está listo para producción. No se requieren cambios."
            },
            "B": {
                "meaning": "Entre 85% y 95% de escenarios válidos",
                "description": "El horario es robusto. Funciona bien en la mayoría de las condiciones de tráfico.",
                "recommendation": "El horario es aceptable. Considere añadir pequeños buffers si el contexto lo permite."
            },
            "C": {
                "meaning": "Entre 70% y 85% de escenarios válidos",
                "description": "El horario es moderadamente frágil. En condiciones de tráfico elevado, puede haber incumplimientos.",
                "recommendation": "Se recomienda revisar los tiempos de traslado y considerar aumentar buffers entre rutas consecutivas."
            },
            "D": {
                "meaning": "Entre 50% y 70% de escenarios válidos",
                "description": "El horario es frágil. Con variaciones normales de tráfico, falla frecuentemente.",
                "recommendation": "Se requiere ajustar los tiempos de traslado y aumentar buffers. Considere re-optimizar con márgenes más amplios."
            },
            "F": {
                "meaning": "Menos del 50% de escenarios válidos",
                "description": "El horario es muy frágil. Con pequeñas variaciones de tráfico, falla la mayoría de las veces.",
                "recommendation": "Se recomienda aumentar buffers entre rutas o revisar tiempos de traslado. Re-optimización necesaria."
            }
        }
        
        interp = interpretations.get(grade, interpretations["F"])
        return {
            "grade": grade,
            "feasible_rate": f"{feasible_rate:.1%}",
            **interp
        }
    
    def simulate_travel_times(
        self,
        base_times: Dict[Tuple[str, str], float]
    ) -> Dict[Tuple[str, str], float]:
        """
        Simulate travel times with uncertainty.
        
        Args:
            base_times: Base travel times dict (route_i, route_j) -> minutes
            
        Returns:
            Simulated travel times with variation
        """
        import math
        simulated = {}
        
        for key, base in base_times.items():
            if self.distribution == "lognormal":
                sigma = self.time_uncertainty
                mu = math.log(base) - (sigma ** 2) / 2
                simulated[key] = random.lognormvariate(mu, sigma)
            elif self.distribution == "normal":
                variation = base * self.time_uncertainty
                time_val = random.gauss(base, variation)
                simulated[key] = max(1, time_val)
            elif self.distribution == "uniform":
                variation = base * self.time_uncertainty
                time_val = base + random.uniform(-variation, variation)
                simulated[key] = max(1, time_val)
            else:
                raise ValueError(f"Unsupported distribution: {self.distribution}")
        
        return simulated
    
    def calculate_schedule_duration(
        self,
        schedule: List[BusSchedule],
        travel_times: Dict[Tuple[str, str], float]
    ) -> float:
        """
        Calculate total schedule duration including travel times.
        
        Args:
            schedule: List of BusSchedule
            travel_times: Travel times between routes
            
        Returns:
            Total duration in minutes
        """
        total_duration = 0.0
        
        for bus in schedule:
            items = sorted(bus.items, key=lambda x: self._time_to_minutes(x.start_time))
            
            for i, item in enumerate(items):
                # Add route duration
                duration = self._time_to_minutes(item.end_time) - self._time_to_minutes(item.start_time)
                total_duration += max(0, duration)
                
                # Add travel time to next route (if exists)
                if i < len(items) - 1:
                    next_item = items[i + 1]
                    tt_key = (item.route_id, next_item.route_id)
                    travel_time = travel_times.get(tt_key, 15.0)
                    total_duration += travel_time
        
        return total_duration
    
    def _time_to_minutes(self, t) -> int:
        """Convert time to minutes from midnight."""
        from datetime import time as dt_time
        if isinstance(t, dt_time):
            return t.hour * 60 + t.minute
        # Handle string time format "HH:MM"
        if isinstance(t, str):
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    
    def run_single_simulation(
        self,
        schedule: List[BusSchedule],
        base_travel_times: Dict[Tuple[str, str], float],
        sim_id: int
    ) -> Dict[str, Any]:
        """
        Execute a single simulation and return detailed results.
        
        Args:
            schedule: Schedule to validate
            base_travel_times: Base travel times
            sim_id: Simulation identifier
            
        Returns:
            Dictionary with simulation results including 3D scatter data
        """
        # Simulate travel times with uncertainty
        simulated_times = self.simulate_travel_times(base_travel_times)
        
        # Check feasibility
        is_feasible, violations = check_schedule_feasibility(schedule, simulated_times)
        
        # DEBUG: Log detailed info for first few simulations
        if sim_id < 3:
            logger.info(f"[MC DEBUG] Simulation {sim_id}:")
            logger.info(f"  - Feasible: {is_feasible}, Violations: {violations}")
            logger.info(f"  - Base travel times: {base_travel_times}")
            logger.info(f"  - Simulated times: {simulated_times}")
            
            # Check each bus for violations
            for bus_idx, bus in enumerate(schedule):
                items = sorted(bus.items, key=lambda x: self._time_to_minutes(x.start_time))
                for i in range(len(items) - 1):
                    current = items[i]
                    next_item = items[i + 1]
                    
                    tt_key = (current.route_id, next_item.route_id)
                    base_time = base_travel_times.get(tt_key, 15.0)
                    sim_time = simulated_times.get(tt_key, 15.0)
                    
                    end_current = self._time_to_minutes(current.end_time)
                    start_next = self._time_to_minutes(next_item.start_time)
                    buffer = start_next - end_current
                    
                    if buffer < sim_time:
                        logger.info(f"  - VIOLATION Bus {bus_idx}, pair ({current.route_id} -> {next_item.route_id}):")
                        logger.info(f"    Buffer: {buffer} min, Base travel: {base_time:.2f} min, Sim travel: {sim_time:.2f} min")
                        logger.info(f"    End current: {current.end_time}, Start next: {next_item.start_time}")
                        logger.info(f"    Deadhead recorded: {next_item.deadhead_minutes} min")
        
        # Calculate metrics for 3D scatter plot
        # X: Time deviation (how much times varied from base)
        time_deviation = self._calculate_time_deviation(base_travel_times, simulated_times)
        
        # Y: Total schedule duration
        duration = self.calculate_schedule_duration(schedule, simulated_times)
        
        # Z: Feasibility (1 = feasible, 0 = infeasible) - for coloring points
        
        # Convert simulated_times keys from tuples to strings for JSON serialization
        simulated_times_serializable = {
            f"{k[0]},{k[1]}": v for k, v in simulated_times.items()
        }
        
        return {
            "id": sim_id,
            "x": round(time_deviation, 2),  # Time deviation
            "y": round(duration, 2),         # Total duration
            "z": 1 if is_feasible else 0,    # Feasibility flag
            "feasible": is_feasible,
            "violations": violations,
            "simulated_times": simulated_times_serializable
        }
    
    def _calculate_time_deviation(
        self,
        base_times: Dict[Tuple[str, str], float],
        simulated_times: Dict[Tuple[str, str], float]
    ) -> float:
        """
        Calculate average time deviation between base and simulated times.
        
        Args:
            base_times: Base travel times
            simulated_times: Simulated travel times
            
        Returns:
            Average deviation ratio
        """
        if not base_times:
            return 0.0
        
        deviations = []
        for key, base in base_times.items():
            simulated = simulated_times.get(key, base)
            if base > 0:
                deviation = abs(simulated - base) / base
                deviations.append(deviation)
        
        return sum(deviations) / len(deviations) if deviations else 0.0
    
    async def validate_streaming(
        self,
        schedule: List[BusSchedule],
        base_travel_times: Dict[Tuple[str, str], float],
        websocket: WebSocket
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo validation with streaming results.
        
        Args:
            schedule: Schedule to validate
            base_travel_times: Base travel times
            websocket: WebSocket connection for streaming
            
        Returns:
            Final results dictionary
        """
        self.reset()
        
        for batch_start in range(0, self.n_simulations, self.batch_size):
            batch_end = min(batch_start + self.batch_size, self.n_simulations)
            batch_scenarios = []
            
            for i in range(batch_start, batch_end):
                # Run single simulation
                scenario = self.run_single_simulation(
                    schedule, base_travel_times, i
                )
                
                # Update tracking
                self.scenarios.append(scenario)
                batch_scenarios.append(scenario)
                
                if scenario["feasible"]:
                    self.feasible_count += 1
                else:
                    self.infeasible_count += 1
                
                # Track violation distribution
                violations = scenario["violations"]
                self.total_violations += violations
                self.violation_distribution[violations] = \
                    self.violation_distribution.get(violations, 0) + 1
                
                self.completed += 1
            
            # Calculate current stats
            feasible_rate = self.feasible_count / self.completed if self.completed > 0 else 0.0
            
            # Send batch progress
            progress_msg = {
                "type": "progress",
                "completed": self.completed,
                "total": self.n_simulations,
                "feasible_rate": round(feasible_rate, 4),
                "feasible_rate_pct": f"{feasible_rate:.1%}",
                "scenarios": batch_scenarios,  # Only new scenarios
                "grade": self.calculate_grade(feasible_rate),
                "batch_start": batch_start,
                "batch_end": batch_end - 1,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            try:
                await websocket.send_json(progress_msg)
            except Exception as e:
                logger.error(f"Failed to send progress: {e}")
                raise
            
            # Small pause to prevent overwhelming the client
            await asyncio.sleep(0.01)
        
        # Calculate final results
        final_feasible_rate = self.feasible_count / self.n_simulations if self.n_simulations > 0 else 0.0
        
        # Calculate average violations per scenario
        avg_violations = self.total_violations / self.n_simulations if self.n_simulations > 0 else 0.0
        
        return {
            "completed": self.completed,
            "feasible": self.feasible_count,
            "infeasible": self.infeasible_count,
            "feasible_rate": round(final_feasible_rate, 4),
            "feasible_rate_pct": f"{final_feasible_rate:.1%}",
            "final_grade": self.calculate_grade(final_feasible_rate),
            "total_scenarios": self.n_simulations,
            "all_scenarios": self.scenarios,
            "violation_distribution": self.violation_distribution,
            "avg_violations_per_scenario": round(avg_violations, 2),
            "interpretation": self.get_grade_interpretation(
                self.calculate_grade(final_feasible_rate), 
                final_feasible_rate
            )
        }


# Global validator instance cache
_validator_cache: Dict[str, MonteCarloStreamingValidator] = {}


def get_validator(job_id: str) -> Optional[MonteCarloStreamingValidator]:
    """Get cached validator for job."""
    return _validator_cache.get(job_id)


def cache_validator(job_id: str, validator: MonteCarloStreamingValidator):
    """Cache validator for job."""
    _validator_cache[job_id] = validator


def clear_validator_cache(job_id: str):
    """Clear cached validator for job."""
    if job_id in _validator_cache:
        del _validator_cache[job_id]


def calculate_grade(rate: float) -> str:
    """
    Calculate robustness grade from feasible rate.
    
    Args:
        rate: Feasible rate (0.0 - 1.0)
        
    Returns:
        Grade letter
    """
    if rate >= 0.95:
        return "A"
    elif rate >= 0.85:
        return "B"
    elif rate >= 0.70:
        return "C"
    elif rate >= 0.50:
        return "D"
    else:
        return "F"


async def handle_monte_carlo_websocket(
    websocket: WebSocket,
    job_id: str
):
    """
    Handle WebSocket connection for Monte Carlo streaming.
    
    This handler now gets the schedule from the validation_jobs cache
    instead of receiving it directly via WebSocket.
    
    Args:
        websocket: WebSocket connection
        job_id: Unique job identifier (must exist in validation_jobs cache)
    """
    await websocket.accept()
    logger.info(f"[MC WebSocket] Client connected for job {job_id}")
    
    if not MONTE_CARLO_AVAILABLE:
        await websocket.send_json({
            "type": "error",
            "message": "Monte Carlo validation not available"
        })
        await websocket.close()
        return
    
    try:
        # Receive configuration from client
        config = await websocket.receive_json()
        logger.info(f"[MC WebSocket] Received config for job {job_id}: {config}")
        
        # Check if job exists in validation cache
        if job_id not in validation_jobs_ref:
            await websocket.send_json({
                "type": "error",
                "message": "Job no encontrado. Primero debe llamar a /validate-schedule"
            })
            await websocket.close()
            return
        
        # Get the schedule from cache
        job_data = validation_jobs_ref[job_id]
        schedule = job_data.get("schedule", [])
        
        if not schedule:
            await websocket.send_json({
                "type": "error",
                "message": "El job no contiene un horario válido"
            })
            await websocket.close()
            return
        
        # Update job status
        job_data["status"] = "running"
        
        # Extract configuration
        n_simulations = config.get("n_simulations", 1000)
        uncertainty = config.get("uncertainty", 0.2)
        distribution = config.get("distribution", "lognormal")
        batch_size = config.get("batch_size", 50)
        seed = config.get("seed")
        
        # Get base travel times from schedule
        try:
            base_travel_times = extract_travel_times_from_schedule(schedule)
        except Exception as e:
            logger.error(f"[MC WebSocket] Failed to get travel times: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to get travel times: {str(e)}"
            })
            await websocket.close()
            return
        
        # Initialize streaming validator
        validator = MonteCarloStreamingValidator(
            n_simulations=n_simulations,
            time_uncertainty=uncertainty,
            distribution=distribution,
            batch_size=batch_size,
            seed=seed
        )
        
        # Cache validator for potential resume/reconnect
        cache_validator(job_id, validator)
        
        # Send initial status
        await websocket.send_json({
            "type": "started",
            "job_id": job_id,
            "n_simulations": n_simulations,
            "uncertainty": uncertainty,
            "batch_size": batch_size,
            "bus_count": len(schedule),
            "message": "Monte Carlo validation started",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Run streaming validation
        final_results = await validator.validate_streaming(
            schedule, base_travel_times, websocket
        )
        
        # Build completion message with interpretation
        completion_msg = {
            "type": "completed",
            "job_id": job_id,
            "final_grade": final_results["final_grade"],
            "feasible_rate": final_results["feasible_rate"],
            "feasible_rate_pct": final_results["feasible_rate_pct"],
            "total_scenarios": final_results["total_scenarios"],
            "feasible_count": final_results["feasible"],
            "infeasible_count": final_results["infeasible"],
            "interpretation": final_results["interpretation"],
            "stats": {
                "total_simulations": final_results["total_scenarios"],
                "feasible_count": final_results["feasible"],
                "infeasible_count": final_results["infeasible"],
                "avg_violations_per_scenario": final_results["avg_violations_per_scenario"]
            },
            "violation_distribution": final_results["violation_distribution"],
            "all_scenarios": final_results["all_scenarios"],
            "message": "Monte Carlo validation completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send completion message
        await websocket.send_json(completion_msg)
        
        # Update job status to completed
        job_data["status"] = "completed"
        job_data["results"] = final_results
        
        logger.info(f"[MC WebSocket] Validation completed for job {job_id}: "
                   f"grade={final_results['final_grade']}, "
                   f"rate={final_results['feasible_rate_pct']}")
        
    except WebSocketDisconnect:
        logger.info(f"[MC WebSocket] Client disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"[MC WebSocket] Error for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception:
            pass
    finally:
        clear_validator_cache(job_id)
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info(f"[MC WebSocket] Connection closed for job {job_id}")


# FastAPI router factory for easy integration
def create_monte_carlo_websocket_endpoint(app):
    """
    Register Monte Carlo WebSocket endpoint with FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    @app.websocket("/ws/monte-carlo/{job_id}")
    async def websocket_monte_carlo(websocket: WebSocket, job_id: str):
        await handle_monte_carlo_websocket(websocket, job_id)
    
    logger.info("[MC WebSocket] Endpoint registered at /ws/monte-carlo/{job_id}")


__all__ = [
    'MonteCarloStreamingValidator',
    'handle_monte_carlo_websocket',
    'create_monte_carlo_websocket_endpoint',
    'calculate_grade',
    'set_validation_jobs_cache',
]
