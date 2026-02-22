"""
Workspace optimization options persistence helpers.

Stores per-workspace optimization configuration in app_meta without DB schema migrations.
"""

from __future__ import annotations

from typing import Any, Dict, List

from db import crud as db_crud

DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS: Dict[str, Any] = {
    "balance_load": True,
    "load_balance_hard_spread_limit": 2,
    "load_balance_target_band": 1,
    "route_load_constraints": [],
}


def workspace_optimization_options_key(workspace_id: str) -> str:
    return f"workspace_optimization_options::{str(workspace_id or '').strip()}"


def _normalize_route_load_constraints(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: List[Dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        start = str(row.get("start_time", row.get("start", "")) or "").strip()
        end = str(row.get("end_time", row.get("end", "")) or "").strip()
        label = str(row.get("label", "") or "").strip()
        enabled = bool(row.get("enabled", True))
        try:
            max_routes = int(row.get("max_routes", 0) or 0)
        except Exception:
            max_routes = 0
        if not start or not end or max_routes <= 0:
            continue
        items.append(
            {
                "start_time": start,
                "end_time": end,
                "max_routes": max(1, max_routes),
                "enabled": enabled,
                "label": label,
            }
        )
    return items


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

    return {
        "balance_load": bool(data.get("balance_load", DEFAULT_WORKSPACE_OPTIMIZATION_OPTIONS["balance_load"])),
        "load_balance_hard_spread_limit": max(1, min(12, spread)),
        "load_balance_target_band": max(0, min(6, band)),
        "route_load_constraints": _normalize_route_load_constraints(data.get("route_load_constraints", [])),
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

