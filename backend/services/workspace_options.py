"""
Workspace optimization options persistence helpers.

Stores per-workspace optimization configuration in app_meta without DB schema migrations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from db import crud as db_crud

DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS: Dict[str, Any] = {
    "objective": "min_buses_viability",
    "preferred_solver": "auto",
    "balance_load": True,
    "load_balance_hard_spread_limit": 2,
    "load_balance_target_band": 1,
    "route_load_constraints": [],
    "enable_greedy_warm_start": True,
    "time_limit_seconds": None,
    "fleet_scope_mode": "company",  # company|ute
    "fleet_scope_ute_id": None,
    "virtual_bus_publish_policy": "allow",  # allow|block
}


def workspace_optimization_options_key(workspace_id: str) -> str:
    return f"workspace_optimization_options::{str(workspace_id or '').strip()}"


def _parse_hhmm_minutes(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except Exception:
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return (hh * 60) + mm


def _normalize_route_load_constraints(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        start = str(row.get("start_time", row.get("start", "")) or "").strip()
        end = str(row.get("end_time", row.get("end", "")) or "").strip()
        if _parse_hhmm_minutes(start) is None or _parse_hhmm_minutes(end) is None:
            continue
        label = str(row.get("label", "") or "").strip() or f"{start}-{end}"
        enabled = bool(row.get("enabled", True))
        try:
            max_routes = int(row.get("max_routes", 0) or 0)
        except Exception:
            max_routes = 0
        if not start or not end or max_routes <= 0:
            continue
        key = f"{start}|{end}"
        current = dedup.get(key)
        next_item = {
            "start_time": start,
            "end_time": end,
            "max_routes": max(1, max_routes),
            "enabled": enabled,
            "label": label,
        }
        if current is None:
            dedup[key] = next_item
            continue
        dedup[key] = {
            **current,
            "max_routes": min(int(current.get("max_routes", 1) or 1), next_item["max_routes"]),
            "enabled": bool(current.get("enabled", True)) or enabled,
            "label": str(current.get("label", "") or "").strip() or label,
        }
    return sorted(dedup.values(), key=lambda item: (item["start_time"], item["end_time"], item["max_routes"]))


def sanitize_workspace_optimization_options(raw: Any) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    try:
        spread = int(data.get("load_balance_hard_spread_limit", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["load_balance_hard_spread_limit"]))
    except Exception:
        spread = int(DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["load_balance_hard_spread_limit"])
    try:
        band = int(data.get("load_balance_target_band", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["load_balance_target_band"]))
    except Exception:
        band = int(DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["load_balance_target_band"])

    fleet_scope_mode = str(data.get("fleet_scope_mode", "company") or "company").strip().lower()
    if fleet_scope_mode not in {"company", "ute"}:
        fleet_scope_mode = "company"
    fleet_scope_ute_id = str(data.get("fleet_scope_ute_id", "") or "").strip() or None
    virtual_bus_publish_policy = str(
        data.get("virtual_bus_publish_policy", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["virtual_bus_publish_policy"])
        or DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["virtual_bus_publish_policy"]
    ).strip().lower()
    if virtual_bus_publish_policy not in {"allow", "block"}:
        virtual_bus_publish_policy = "allow"
    objective = str(
        data.get("objective", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["objective"])
        or DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["objective"]
    ).strip().lower()
    if objective not in {
        "min_buses_viability",
        "min_buses_viability_hybrid",
        "min_km",
        "min_deadhead",
        "operational_balance",
        "publishable",
    }:
        objective = "min_buses_viability"
    preferred_solver = str(
        data.get("preferred_solver", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["preferred_solver"])
        or DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["preferred_solver"]
    ).strip().lower()
    if preferred_solver not in {"auto", "pulp_v6", "cp_sat"}:
        preferred_solver = "auto"
    time_limit_seconds_raw = data.get("time_limit_seconds", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["time_limit_seconds"])
    try:
        time_limit_seconds = max(1, min(600, int(time_limit_seconds_raw))) if time_limit_seconds_raw is not None else None
    except Exception:
        time_limit_seconds = None

    spread = max(1, min(12, spread))
    band = max(0, min(6, band, spread))

    return {
        "objective": objective,
        "preferred_solver": preferred_solver,
        "balance_load": bool(data.get("balance_load", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["balance_load"])),
        "load_balance_hard_spread_limit": spread,
        "load_balance_target_band": band,
        "route_load_constraints": _normalize_route_load_constraints(data.get("route_load_constraints", [])),
        "enable_greedy_warm_start": bool(
            data.get("enable_greedy_warm_start", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["enable_greedy_warm_start"])
        ),
        "time_limit_seconds": time_limit_seconds,
        "fleet_scope_mode": fleet_scope_mode,
        "fleet_scope_ute_id": fleet_scope_ute_id,
        "virtual_bus_publish_policy": virtual_bus_publish_policy,
    }


def get_workspace_optimization_options(db, workspace_id: str) -> Dict[str, Any]:
    key = workspace_optimization_options_key(workspace_id)
    meta = db_crud.get_app_meta(db, key)
    if not meta:
        return dict(DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS)
    return sanitize_workspace_optimization_options(meta.value)


def set_workspace_optimization_options(db, workspace_id: str, options: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = sanitize_workspace_optimization_options(options)
    key = workspace_optimization_options_key(workspace_id)
    db_crud.set_app_meta(db, key, sanitized)
    return sanitized
