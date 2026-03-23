"""Shared solver selection heuristics and human-readable diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .config import OptimizerConfig

AUTO_ALIASES = {"", "auto", "default"}
PULP_ALIASES = {"pulp", "pulp_v6", "cbc"}
CP_SAT_ALIASES = {"cp_sat", "cpsat", "ortools", "or_tools", "cp-sat"}

_REASON_TEXT: Dict[str, Dict[str, str]] = {
    "auto:fallback_cp_sat_unavailable": {
        "label": "CP-SAT no disponible",
        "detail": "El motor auto usa PuLP V6 porque OR-Tools/CP-SAT no esta disponible en este entorno.",
    },
    "auto:fallback_cp_sat_experimental": {
        "label": "CP-SAT aun experimental",
        "detail": "El motor auto mantiene PuLP V6 porque CP-SAT todavia no esta validado para produccion en datasets reales.",
    },
    "auto:fallback_route_load_constraints": {
        "label": "Reglas horarias avanzadas activas",
        "detail": "Hay ventanas o limites de reparto activos y el modo auto prioriza PuLP V6 para conservar esas reglas.",
    },
    "auto:fallback_balance_load_priority": {
        "label": "Balanceo operativo prioritario",
        "detail": "El modo auto mantiene PuLP V6 cuando el reparto equilibrado pesa mas que la eficiencia pura.",
    },
    "auto:fallback_operational_objective": {
        "label": "Objetivo operativo conservador",
        "detail": "El objetivo elegido prioriza publicabilidad o equilibrio operativo, asi que auto mantiene el backend estable.",
    },
    "auto:fallback_large_min_buses_instance": {
        "label": "Instancia grande de minimo buses",
        "detail": "Para un volumen alto con objetivo de reducir buses, auto usa PuLP V6 como backend principal.",
    },
    "auto:fallback_instance_too_large": {
        "label": "Instancia grande",
        "detail": "El caso es lo bastante grande como para que auto prefiera PuLP V6 en esta fase del motor.",
    },
    "auto:cp_sat_candidate": {
        "label": "Caso apto para CP-SAT",
        "detail": "El problema es lo bastante simple o eficiente como para intentar resolverlo con CP-SAT.",
    },
    "explicit:cp_sat": {
        "label": "CP-SAT solicitado",
        "detail": "La configuracion pide CP-SAT de forma explicita.",
    },
    "explicit:fallback_cp_sat_unavailable": {
        "label": "CP-SAT pedido pero no disponible",
        "detail": "Se pidio CP-SAT, pero el entorno no lo tiene disponible; se usa PuLP V6 como respaldo.",
    },
    "explicit:pulp_v6": {
        "label": "PuLP V6 solicitado",
        "detail": "La configuracion pide usar el backend estable PuLP V6.",
    },
    "fallback:unknown_solver": {
        "label": "Solver no reconocido",
        "detail": "La preferencia de solver no se reconoce y el motor vuelve a PuLP V6 para mantener compatibilidad.",
    },
    "empty:no_routes": {
        "label": "Sin rutas en el dia",
        "detail": "No hay rutas para optimizar en este dia, asi que no se ejecuta seleccion real de solver.",
    },
}


def normalize_solver_preference(value: Any) -> str:
    """Normalize known solver aliases to stable backend ids."""
    raw = str(value or "").strip().lower()
    if raw in AUTO_ALIASES:
        return "auto"
    if raw in PULP_ALIASES:
        return "pulp_v6"
    if raw in CP_SAT_ALIASES:
        return "cp_sat"
    return raw or "auto"


def describe_selection_reason(reason_code: str) -> Dict[str, str]:
    """Return a human-readable label/detail for a selection reason."""
    return dict(_REASON_TEXT.get(reason_code, _REASON_TEXT["fallback:unknown_solver"]))


def analyze_solver_selection(
    config: "OptimizerConfig",
    *,
    route_count: int,
    cp_sat_available: bool,
) -> Dict[str, Any]:
    """Explain which backend should be used for the current optimizer request."""
    requested_solver = normalize_solver_preference(config.preferred_solver)
    selected_solver = "pulp_v6"
    reason_code = "fallback:unknown_solver"
    decision_mode = "fallback"

    if route_count <= 0:
        selected_solver = requested_solver if requested_solver in {"pulp_v6", "cp_sat"} else "auto"
        reason_code = "empty:no_routes"
        decision_mode = "empty"
    elif requested_solver == "auto":
        decision_mode = "auto"
        if not cp_sat_available:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_cp_sat_unavailable"
        else:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_cp_sat_experimental"
        if selected_solver != "pulp_v6" and config.route_load_constraints:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_route_load_constraints"
        elif selected_solver != "pulp_v6" and config.balance_load and config.objective_mode not in {"min_km", "min_deadhead"}:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_balance_load_priority"
        elif selected_solver != "pulp_v6" and config.objective_mode in {"publishable", "operational_balance"}:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_operational_objective"
        elif selected_solver != "pulp_v6" and config.objective_mode == "min_buses" and route_count > 60:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_large_min_buses_instance"
        elif selected_solver != "pulp_v6" and route_count > 120:
            selected_solver = "pulp_v6"
            reason_code = "auto:fallback_instance_too_large"
        elif selected_solver != "pulp_v6":
            selected_solver = "cp_sat"
            reason_code = "auto:cp_sat_candidate"
    elif requested_solver == "cp_sat":
        decision_mode = "explicit"
        if cp_sat_available:
            selected_solver = "cp_sat"
            reason_code = "explicit:cp_sat"
        else:
            selected_solver = "pulp_v6"
            reason_code = "explicit:fallback_cp_sat_unavailable"
    elif requested_solver == "pulp_v6":
        decision_mode = "explicit"
        selected_solver = "pulp_v6"
        reason_code = "explicit:pulp_v6"

    reason_text = describe_selection_reason(reason_code)
    fallback_used = (
        (requested_solver == "cp_sat" and selected_solver != "cp_sat")
        or (requested_solver not in {"auto", "pulp_v6", "cp_sat"})
    )
    return {
        "requested_solver": requested_solver,
        "selected_solver": selected_solver,
        "decision_mode": decision_mode,
        "reason_code": reason_code,
        "reason_label": reason_text["label"],
        "reason_detail": reason_text["detail"],
        "route_count": int(route_count),
        "cp_sat_available": bool(cp_sat_available),
        "fallback_used": bool(fallback_used),
        "supports_route_load_constraints": selected_solver == "pulp_v6",
        "supports_balance_load_priority": selected_solver == "pulp_v6",
    }
