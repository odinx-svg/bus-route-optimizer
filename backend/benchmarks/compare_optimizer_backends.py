#!/usr/bin/env python3
"""Compare pluggable optimizer backends on real or synthetic route sets."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.run_real_excels import _load_routes_from_folder  # noqa: E402
from models import Route  # noqa: E402
from optimizer import OptimizerConfig, OptimizerEngine  # noqa: E402


ALL_DAYS = ["L", "M", "Mc", "X", "V"]


def _run_backend(routes: List[Route], preferred_solver: str, time_limit_seconds: int) -> Dict[str, Any]:
    engine = OptimizerEngine()
    started = time.time()
    per_day: Dict[str, Any] = {}
    total_buses = 0
    total_routes = 0
    total_split_count = 0

    for day in ALL_DAYS:
        day_routes = [route for route in routes if day in route.days]
        result = engine.optimize(
            day_routes,
            config=OptimizerConfig(
                objective_mode="min_buses",
                preferred_solver=preferred_solver,
                time_limit_seconds=time_limit_seconds,
                enable_greedy_warm_start=True,
            ),
        )
        diagnostics = engine.get_last_diagnostics()
        route_count = sum(len(bus.items) for bus in result.schedule)
        per_day[day] = {
            "routes": route_count,
            "buses": len(result.schedule),
            "solver_status": diagnostics.get("solver_status"),
            "selected_solver": diagnostics.get("selected_solver", diagnostics.get("solver_name")),
            "split_count": int(diagnostics.get("split_count", 0) or 0),
            "avg_positioning_minutes": diagnostics.get("avg_positioning_minutes", 0.0),
        }
        total_buses += len(result.schedule)
        total_routes += route_count
        total_split_count += int(diagnostics.get("split_count", 0) or 0)

    return {
        "preferred_solver": preferred_solver,
        "runtime_sec": round(time.time() - started, 2),
        "total_buses": total_buses,
        "total_routes": total_routes,
        "split_count": total_split_count,
        "per_day": per_day,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare optimizer backends using the pluggable engine")
    parser.add_argument(
        "--input-dir",
        default=str(ROOT.parent / "ejemplo excel rutas a optimizar"),
        help="Folder containing Excel files",
    )
    parser.add_argument("--sample-routes", type=int, default=0, help="Use first N routes only")
    parser.add_argument("--time-limit-seconds", type=int, default=30, help="Solver time limit")
    parser.add_argument(
        "--output",
        default=str(ROOT / "benchmarks" / "results" / f"backend_compare_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"),
        help="Output JSON report",
    )
    args = parser.parse_args()

    routes, parse_report = _load_routes_from_folder(Path(args.input_dir).resolve())
    if args.sample_routes and args.sample_routes > 0:
        routes = routes[: args.sample_routes]

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "input_dir": str(Path(args.input_dir).resolve()),
        "routes_count": len(routes),
        "parse_report": parse_report,
        "backends": {
            "pulp_v6": _run_backend(routes, "pulp_v6", int(args.time_limit_seconds)),
            "cp_sat": _run_backend(routes, "cp_sat", int(args.time_limit_seconds)),
        },
    }

    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
