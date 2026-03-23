"""Common solver interface for current and future optimizer backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from models import BusSchedule, Route

from .config import OptimizerConfig

ProgressCallback = Optional[Callable[[str, int, str], None]]


@dataclass
class SolverResult:
    """Normalized result returned by any optimizer backend."""

    schedule: List[BusSchedule]
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    solver_name: str = ""
    initial_schedule: Optional[List[BusSchedule]] = None


class SolverInterface(ABC):
    """Abstract adapter interface for optimizer backends."""

    name: str = "base"
    supports_warm_start: bool = False

    @abstractmethod
    def optimize(
        self,
        routes: List[Route],
        config: OptimizerConfig,
        progress_callback: ProgressCallback = None,
        initial_schedule: Optional[List[BusSchedule]] = None,
    ) -> SolverResult:
        """Optimize a single-day list of routes."""
