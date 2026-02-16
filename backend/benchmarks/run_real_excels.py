#!/usr/bin/env python3
"""
Benchmark E2E sobre excels reales para evaluar recuperación de eficiencia.

Uso:
    python -m benchmarks.run_real_excels
    python -m benchmarks.run_real_excels --input-dir "ejemplo excel rutas a optimizar"
    python -m benchmarks.run_real_excels --output backend/benchmarks/results/real_excels_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parser import parse_routes_with_report, aggregate_parse_reports  # noqa: E402
from models import Route, BusSchedule  # noqa: E402
from optimizer_v6 import optimize_v6, get_last_optimization_diagnostics  # noqa: E402
from services.optimization_pipeline_service import (  # noqa: E402
    PipelineConfig,
    run_optimization_pipeline_by_day,
)


ALL_DAYS = ["L", "M", "Mc", "X", "V"]


def _load_routes_from_folder(folder: Path) -> Tuple[List[Route], Dict[str, Any]]:
    files = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".xlsx", ".xls"}]
    )
    if not files:
        raise FileNotFoundError(f"No Excel files found in: {folder}")

    all_routes: List[Route] = []
    reports: List[Dict[str, Any]] = []
    for file_path in files:
        routes, report = parse_routes_with_report(str(file_path))
        report["file_name"] = file_path.name
        all_routes.extend(routes)
        reports.append(report)

    return all_routes, aggregate_parse_reports(reports)


def _schedule_kpis(schedule_by_day: Dict[str, List[BusSchedule]], diagnostics_by_day: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    per_day: Dict[str, Dict[str, Any]] = {}
    total_buses = 0
    total_routes = 0
    total_split_count = 0

    for day in ALL_DAYS:
        schedules = schedule_by_day.get(day, [])
        bus_count = len(schedules)
        route_count = sum(len(bus.items) for bus in schedules)
        day_diag = diagnostics_by_day.get(day, {})
        split_count = int(day_diag.get("split_count", 0) or 0)

        per_day[day] = {
            "buses": bus_count,
            "routes": route_count,
            "split_count": split_count,
            "solver_status": day_diag.get("solver_status", "unknown"),
            "lower_bound_buses": int(day_diag.get("lower_bound_buses", bus_count) or bus_count),
            "optimality_gap": float(day_diag.get("optimality_gap", 0.0) or 0.0),
        }

        total_buses += bus_count
        total_routes += route_count
        total_split_count += split_count

    return {
        "per_day": per_day,
        "total_buses": total_buses,
        "total_routes": total_routes,
        "split_count": total_split_count,
    }


def _run_baseline(routes: List[Route]) -> Dict[str, Any]:
    started = time.time()
    by_day: Dict[str, List[BusSchedule]] = {}
    diagnostics_by_day: Dict[str, Dict[str, Any]] = {}

    for day in ALL_DAYS:
        day_routes = [route for route in routes if day in route.days]
        if not day_routes:
            by_day[day] = []
            diagnostics_by_day[day] = {
                "split_count": 0,
                "lower_bound_buses": 0,
                "optimality_gap": 0.0,
                "solver_status": "optimal",
            }
            continue

        day_schedule = optimize_v6(day_routes, use_ml_assignment=True)
        by_day[day] = day_schedule
        diagnostics_by_day[day] = get_last_optimization_diagnostics()

    kpis = _schedule_kpis(by_day, diagnostics_by_day)
    kpis["runtime_sec"] = round(time.time() - started, 2)
    return kpis


async def _run_pipeline(
    routes: List[Route],
    invalid_rows_dropped: int,
    max_duration_sec: int,
    max_iterations: int,
) -> Dict[str, Any]:
    started = time.time()
    config = PipelineConfig(
        auto_start=True,
        objective="min_buses_viability",
        max_duration_sec=max_duration_sec,
        max_iterations=max_iterations,
        use_ml_assignment=True,
        invalid_rows_dropped=invalid_rows_dropped,
    )
    result = await run_optimization_pipeline_by_day(routes=routes, config=config, progress_callback=None)
    summary_metrics = result.get("summary_metrics", {})
    validation_report = result.get("validation_report", {})
    incidents = validation_report.get("incidents", []) if isinstance(validation_report, dict) else []
    infeasible_transitions = sum(1 for issue in incidents if str(issue.get("severity", "")).lower() == "error")

    output = {
        "runtime_sec": round(time.time() - started, 2),
        "summary_metrics": summary_metrics,
        "selected_candidate": result.get("selected_candidate"),
        "elapsed_sec": result.get("elapsed_sec"),
        "infeasible_transitions": infeasible_transitions,
        "pipeline_history_size": len(result.get("pipeline_history", []) or []),
    }
    return output


def _build_pass_fail(baseline: Dict[str, Any], pipeline: Dict[str, Any], parse_report: Dict[str, Any]) -> Dict[str, Any]:
    baseline_buses = int(baseline.get("total_buses", 0) or 0)
    pipeline_metrics = pipeline.get("summary_metrics", {}) or {}
    best_buses = int(pipeline_metrics.get("best_buses", pipeline_metrics.get("total_buses", 0)) or 0)
    split_count = int(pipeline_metrics.get("split_count", 0) or 0)
    gap = float(pipeline_metrics.get("optimality_gap", 0.0) or 0.0)
    dropped = int(parse_report.get("rows_dropped_invalid", 0) or 0)

    checks = {
        "buses_not_worse_than_baseline": best_buses <= baseline_buses if baseline_buses > 0 else True,
        "split_count_zero": split_count == 0,
        "rows_invalid_reported": dropped >= 0,
        "optimality_gap_reported": gap >= 0.0,
    }

    return {
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark on real Excel folder")
    parser.add_argument(
        "--input-dir",
        default=str(ROOT.parent / "ejemplo excel rutas a optimizar"),
        help="Folder containing real Excel files",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "benchmarks" / "results" / f"real_excels_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"),
        help="Output JSON file",
    )
    parser.add_argument("--max-duration-sec", type=int, default=300, help="Pipeline max duration")
    parser.add_argument("--max-iterations", type=int, default=2, help="Pipeline max iterations")
    parser.add_argument(
        "--sample-routes",
        type=int,
        default=0,
        help="If >0, runs benchmark with first N routes (smoke mode)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_file = Path(args.output).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    routes, parse_report = _load_routes_from_folder(input_dir)
    if args.sample_routes and args.sample_routes > 0:
        routes = routes[: args.sample_routes]

    baseline = _run_baseline(routes)
    pipeline = asyncio.run(
        _run_pipeline(
            routes,
            int(parse_report.get("rows_dropped_invalid", 0) or 0),
            int(args.max_duration_sec),
            int(args.max_iterations),
        )
    )
    semaforo = _build_pass_fail(baseline, pipeline, parse_report)

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "input_dir": str(input_dir),
        "routes_count": len(routes),
        "parse_report": parse_report,
        "baseline": baseline,
        "pipeline": pipeline,
        "status": semaforo,
    }

    with output_file.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(json.dumps({
        "output": str(output_file),
        "routes_count": len(routes),
        "baseline_buses": baseline.get("total_buses"),
        "pipeline_best_buses": (pipeline.get("summary_metrics") or {}).get("best_buses"),
        "split_count": (pipeline.get("summary_metrics") or {}).get("split_count"),
        "passed": semaforo.get("passed"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
