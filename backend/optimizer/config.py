"""Shared optimizer configuration and objective presets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .selection import normalize_solver_preference

OBJECTIVE_ALIASES: Dict[str, str] = {
    "min_buses": "min_buses",
    "min_buses_viability": "min_buses",
    "min_buses_viability_hybrid": "min_buses",
    "min_km": "min_km",
    "min_deadhead": "min_deadhead",
    "operational_balance": "operational_balance",
    "publishable": "publishable",
}

OBJECTIVE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "min_buses": {
        "buses": 1000.0,
        "deadhead_km": 10.0,
        "time_shift_minutes": 5.0,
        "unbalanced_load": 10.0,
        "virtual_buses": 500.0,
    },
    "min_km": {
        "buses": 500.0,
        "deadhead_km": 40.0,
        "time_shift_minutes": 4.0,
        "unbalanced_load": 10.0,
        "virtual_buses": 500.0,
    },
    "min_deadhead": {
        "buses": 600.0,
        "deadhead_km": 60.0,
        "time_shift_minutes": 4.0,
        "unbalanced_load": 8.0,
        "virtual_buses": 500.0,
    },
    "operational_balance": {
        "buses": 700.0,
        "deadhead_km": 15.0,
        "time_shift_minutes": 5.0,
        "unbalanced_load": 30.0,
        "virtual_buses": 500.0,
    },
    "publishable": {
        "buses": 800.0,
        "deadhead_km": 20.0,
        "time_shift_minutes": 5.0,
        "unbalanced_load": 20.0,
        "virtual_buses": 1000.0,
    },
}


def normalize_objective_mode(value: Any) -> str:
    raw = str(value or "min_buses").strip().lower()
    return OBJECTIVE_ALIASES.get(raw, "min_buses")


@dataclass
class OptimizerConfig:
    """Runtime configuration shared by all solver adapters."""

    objective_mode: str = "min_buses"
    preferred_solver: str = "auto"
    use_ml_assignment: bool = True
    balance_load: bool = True
    load_balance_hard_spread_limit: int = 2
    load_balance_target_band: int = 1
    route_load_constraints: List[Dict[str, Any]] = field(default_factory=list)
    enable_greedy_warm_start: bool = True
    use_lns: bool = False
    time_limit_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.objective_mode = normalize_objective_mode(self.objective_mode)
        self.preferred_solver = normalize_solver_preference(self.preferred_solver)
        spread = max(1, int(self.load_balance_hard_spread_limit or 2))
        self.load_balance_hard_spread_limit = spread
        self.load_balance_target_band = max(0, min(spread, int(self.load_balance_target_band or 0)))
        self.route_load_constraints = list(self.route_load_constraints or [])
        self.metadata = dict(self.metadata or {})
        if self.time_limit_seconds is not None:
            self.time_limit_seconds = max(1, int(self.time_limit_seconds))

    @property
    def objective_weights(self) -> Dict[str, float]:
        return dict(OBJECTIVE_WEIGHTS.get(self.objective_mode, OBJECTIVE_WEIGHTS["min_buses"]))

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "OptimizerConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            objective_mode=data.get("objective_mode", data.get("objective", "min_buses")),
            preferred_solver=data.get("preferred_solver", data.get("solver", "auto")),
            use_ml_assignment=bool(data.get("use_ml_assignment", True)),
            balance_load=bool(data.get("balance_load", True)),
            load_balance_hard_spread_limit=int(data.get("load_balance_hard_spread_limit", 2)),
            load_balance_target_band=int(data.get("load_balance_target_band", 1)),
            route_load_constraints=list(data.get("route_load_constraints") or []),
            enable_greedy_warm_start=bool(data.get("enable_greedy_warm_start", True)),
            use_lns=bool(data.get("use_lns", False)),
            time_limit_seconds=data.get("time_limit_seconds"),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective_mode": self.objective_mode,
            "preferred_solver": self.preferred_solver,
            "use_ml_assignment": self.use_ml_assignment,
            "balance_load": self.balance_load,
            "load_balance_hard_spread_limit": self.load_balance_hard_spread_limit,
            "load_balance_target_band": self.load_balance_target_band,
            "route_load_constraints": list(self.route_load_constraints),
            "enable_greedy_warm_start": self.enable_greedy_warm_start,
            "use_lns": self.use_lns,
            "time_limit_seconds": self.time_limit_seconds,
            "metadata": dict(self.metadata),
            "objective_weights": self.objective_weights,
        }
