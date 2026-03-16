"""
Operational fleet reconciliation services.

This service builds a day-level snapshot for fleet reconciliation based on the
operational need of the schedule, not only on currently virtual buses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from db import models as db_models
from services.fleet_assignment import _fleet_score_for_requirement, _normalize_vehicle
from services.fleet_publication import _bus_required_seats_from_payload, _bus_time_window_from_payload
from services.fleet_repository import FleetRepository


ALL_DAYS = ("L", "M", "Mc", "X", "V")


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _day_bus_key(day: Any, bus_id: Any) -> str:
    return f"{str(day or '').strip()}::{str(bus_id or '').strip()}"


def _window_overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return (a_start < b_end) and (a_end > b_start)


def _normalize_vehicle_pool(
    *,
    primary_company_id: str,
    scope_company_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    repository = FleetRepository()
    vehicles: List[Dict[str, Any]] = []
    for raw in repository.list_active_profiles(company_id=primary_company_id, company_ids=scope_company_ids):
        normalized = _normalize_vehicle(raw)
        if normalized:
            vehicles.append(normalized)
    vehicles.sort(
        key=lambda row: (
            str(row.get("company_name") or ""),
            int(row.get("seats_max", 0) or 0),
            str(row.get("vehicle_code") or ""),
        )
    )
    return vehicles


def _normalize_reconciliation_snapshot(fleet_snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = _safe_dict(fleet_snapshot)
    snapshot = _safe_dict(source.get("reconciliation_snapshot"))
    days = _safe_dict(snapshot.get("days"))
    return {
        **snapshot,
        "days": days,
    }


def _build_published_occupancy(
    db,
    *,
    day: str,
    scope_company_ids: List[str],
    exclude_workspace_id: Optional[str] = None,
) -> Dict[str, List[Tuple[int, int]]]:
    occupancy: Dict[str, List[Tuple[int, int]]] = {}
    if not scope_company_ids:
        return occupancy
    query = db.query(db_models.PublishedFleetAssignmentModel).filter(
        db_models.PublishedFleetAssignmentModel.company_id.in_(scope_company_ids),
        db_models.PublishedFleetAssignmentModel.day == str(day),
        db_models.PublishedFleetAssignmentModel.assignment_type == "real",
        db_models.PublishedFleetAssignmentModel.active.is_(True),
        db_models.PublishedFleetAssignmentModel.assigned_vehicle_id.isnot(None),
    )
    if exclude_workspace_id:
        query = query.filter(db_models.PublishedFleetAssignmentModel.workspace_id != str(exclude_workspace_id))
    rows = query.all()
    for row in rows:
        vehicle_id = str(row.assigned_vehicle_id or "").strip()
        if not vehicle_id:
            continue
        occupancy.setdefault(vehicle_id, []).append(
            (
                int(row.start_minute or 0),
                max(int(row.end_minute or 0), int(row.start_minute or 0) + 1),
            )
        )
    return occupancy


def _company_capacity_summary(
    vehicles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for vehicle in vehicles:
        company_id = str(vehicle.get("company_id") or "unassigned")
        entry = summary.setdefault(
            company_id,
            {
                "company_id": vehicle.get("company_id"),
                "company_name": vehicle.get("company_name") or "Empresa sin identificar",
                "available_vehicle_count": 0,
                "vehicle_codes": [],
            },
        )
        entry["available_vehicle_count"] += 1
        code = str(vehicle.get("vehicle_code") or "").strip()
        if code and code not in entry["vehicle_codes"] and len(entry["vehicle_codes"]) < 6:
            entry["vehicle_codes"].append(code)
    return sorted(
        summary.values(),
        key=lambda row: (-int(row.get("available_vehicle_count", 0) or 0), str(row.get("company_name") or "")),
    )


def _build_company_mix(
    rows: List[Dict[str, Any]],
    company_capacity_summary: List[Dict[str, Any]],
) -> Dict[str, Any]:
    recommendation_by_company: Dict[str, Dict[str, Any]] = {}
    coverage_by_company: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        suggestions = row.get("suggestions", []) if isinstance(row.get("suggestions"), list) else []
        seen_companies: set[str] = set()
        for suggestion in suggestions:
            company_key = str(suggestion.get("company_id") or "unassigned")
            coverage = coverage_by_company.setdefault(
                company_key,
                {
                    "company_id": suggestion.get("company_id"),
                    "company_name": suggestion.get("company_name") or "Empresa sin identificar",
                    "coverable_assignments": 0,
                    "candidate_vehicle_ids": set(),
                    "candidate_vehicle_codes": set(),
                },
            )
            if company_key not in seen_companies:
                coverage["coverable_assignments"] += 1
                seen_companies.add(company_key)
            vehicle_id = str(suggestion.get("vehicle_id") or "").strip()
            vehicle_code = str(suggestion.get("vehicle_code") or "").strip()
            if vehicle_id:
                coverage["candidate_vehicle_ids"].add(vehicle_id)
            if vehicle_code:
                coverage["candidate_vehicle_codes"].add(vehicle_code)

        if suggestions:
            best = suggestions[0]
            company_key = str(best.get("company_id") or "unassigned")
            recommendation = recommendation_by_company.setdefault(
                company_key,
                {
                    "company_id": best.get("company_id"),
                    "company_name": best.get("company_name") or "Empresa sin identificar",
                    "recommended_count": 0,
                    "vehicle_codes": [],
                },
            )
            recommendation["recommended_count"] += 1
            best_code = str(best.get("vehicle_code") or "").strip()
            if best_code and best_code not in recommendation["vehicle_codes"] and len(recommendation["vehicle_codes"]) < 4:
                recommendation["vehicle_codes"].append(best_code)

    capacity_by_company = {
        str(row.get("company_id") or "unassigned"): row
        for row in company_capacity_summary
    }
    recommendations: List[Dict[str, Any]] = []
    all_company_keys = {
        *capacity_by_company.keys(),
        *coverage_by_company.keys(),
        *recommendation_by_company.keys(),
    }
    for company_key in all_company_keys:
        recommendation = recommendation_by_company.get(company_key, {})
        capacity = capacity_by_company.get(company_key, {})
        coverage = coverage_by_company.get(company_key, {})
        sample_vehicle_codes = recommendation.get("vehicle_codes", []) or capacity.get("vehicle_codes", []) or []
        recommendations.append(
            {
                "company_id": recommendation.get("company_id") or coverage.get("company_id") or capacity.get("company_id"),
                "company_name": recommendation.get("company_name") or coverage.get("company_name") or capacity.get("company_name"),
                "recommended_count": int(recommendation.get("recommended_count", 0) or 0),
                "available_vehicle_count": int(capacity.get("available_vehicle_count", 0) or 0),
                "coverable_assignments": int(coverage.get("coverable_assignments", 0) or 0),
                "candidate_vehicle_count": len(coverage.get("candidate_vehicle_ids", set())),
                "vehicle_codes": sample_vehicle_codes[:4],
            }
        )
    recommendations.sort(
        key=lambda row: (
            -int(row.get("recommended_count", 0) or 0),
            -int(row.get("coverable_assignments", 0) or 0),
            -int(row.get("available_vehicle_count", 0) or 0),
            str(row.get("company_name") or ""),
        )
    )
    return {
        "total_pending_buses": len(rows),
        "recommended_companies": recommendations,
        "companies_with_options": len(company_capacity_summary),
        "uncovered_buses": sum(1 for row in rows if not _safe_list(row.get("suggestions"))),
    }


def _build_day_bus_rows(day_schedule: Dict[str, Any], day: str) -> List[Dict[str, Any]]:
    buses = _safe_list(_safe_dict(day_schedule).get("schedule"))
    rows: List[Dict[str, Any]] = []
    for bus in buses:
        if not isinstance(bus, dict):
            continue
        bus_id = str(bus.get("bus_id") or "").strip()
        if not bus_id:
            continue
        start_minute, end_minute = _bus_time_window_from_payload(bus)
        rows.append(
            {
                "day": day,
                "bus_id": bus_id,
                "required_seats": int(_bus_required_seats_from_payload(bus) or 1),
                "start_minute": start_minute,
                "end_minute": end_minute,
                "route_ids": [
                    str(item.get("route_id") or "").strip()
                    for item in _safe_list(bus.get("items"))
                    if isinstance(item, dict) and str(item.get("route_id") or "").strip()
                ],
            }
        )
    return rows


def _materialize_selected_assignments(selected_assignments: Dict[str, Any]) -> List[Dict[str, Any]]:
    materialized: List[Dict[str, Any]] = []
    for key, assignment in (selected_assignments or {}).items():
        if not isinstance(assignment, dict):
            continue
        day, _, bus_id = str(key).partition("::")
        materialized.append(
            {
                "day": day,
                "bus_id": bus_id,
                **assignment,
            }
        )
    return materialized


def build_operational_reconciliation_snapshot(
    db,
    *,
    workspace_id: str,
    primary_company_id: str,
    schedule_by_day: Dict[str, Any],
    scope_mode: str,
    scope_label: str,
    scope_company_ids: List[str],
    scope_company_names: Optional[Dict[str, str]] = None,
    scope_vehicle_count: Optional[int] = None,
    exclude_workspace_id: Optional[str] = None,
    fleet_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_schedule = schedule_by_day if isinstance(schedule_by_day, dict) else {}
    normalized_scope_company_ids = [str(cid).strip() for cid in (scope_company_ids or []) if str(cid).strip()]
    vehicles = _normalize_vehicle_pool(
        primary_company_id=primary_company_id,
        scope_company_ids=normalized_scope_company_ids,
    )
    company_capacity_summary = _company_capacity_summary(vehicles)
    scope_company_names = scope_company_names if isinstance(scope_company_names, dict) else {}
    existing_snapshot = _normalize_reconciliation_snapshot(fleet_snapshot)
    existing_days = _safe_dict(existing_snapshot.get("days"))

    days_payload: Dict[str, Any] = {}
    top_required = 0
    top_real = 0
    top_virtual = 0
    top_pending = 0

    for day in ALL_DAYS:
        day_schedule = _safe_dict(normalized_schedule.get(day))
        bus_rows = _build_day_bus_rows(day_schedule, day)
        required_bus_count = len(bus_rows)
        day_snapshot = _safe_dict(existing_days.get(day))
        selected_assignments_raw = _safe_list(day_snapshot.get("selected_assignments"))
        selected_assignments_by_key: Dict[str, Dict[str, Any]] = {}
        for assignment in selected_assignments_raw:
            if not isinstance(assignment, dict):
                continue
            key = _day_bus_key(assignment.get("day") or day, assignment.get("bus_id"))
            selected_assignments_by_key[key] = assignment

        bus_selections_raw = _safe_list(day_snapshot.get("bus_selections"))
        bus_selections_by_key: Dict[str, Dict[str, Any]] = {}
        for selection in bus_selections_raw:
            if not isinstance(selection, dict):
                continue
            key = _day_bus_key(selection.get("day") or day, selection.get("bus_id"))
            bus_selections_by_key[key] = selection

        published_occupancy = _build_published_occupancy(
            db,
            day=day,
            scope_company_ids=normalized_scope_company_ids,
            exclude_workspace_id=exclude_workspace_id,
        )
        selected_occupancy: Dict[str, List[Tuple[int, int]]] = {}
        stale_assignments: List[Dict[str, Any]] = []
        valid_selected_assignments: Dict[str, Dict[str, Any]] = {}
        bus_rows_by_key = {_day_bus_key(day, row.get("bus_id")): row for row in bus_rows}
        vehicle_by_id = {
            str(vehicle.get("id") or "").strip(): vehicle
            for vehicle in vehicles
            if str(vehicle.get("id") or "").strip()
        }

        for row_key, assignment in selected_assignments_by_key.items():
            bus_row = bus_rows_by_key.get(row_key)
            if not isinstance(bus_row, dict):
                continue
            vehicle_id = str(assignment.get("vehicle_id") or "").strip()
            vehicle = vehicle_by_id.get(vehicle_id)
            if vehicle is None:
                stale_assignments.append(
                    {
                        "day": day,
                        "bus_id": bus_row.get("bus_id"),
                        "vehicle_id": vehicle_id,
                        "reason": "vehicle_not_found",
                    }
                )
                continue
            if int(vehicle.get("seats_max", 0) or 0) < int(bus_row.get("required_seats", 0) or 0):
                stale_assignments.append(
                    {
                        "day": day,
                        "bus_id": bus_row.get("bus_id"),
                        "vehicle_id": vehicle_id,
                        "reason": "vehicle_capacity_insufficient",
                    }
                )
                continue
            start_minute = int(bus_row.get("start_minute", 0) or 0)
            end_minute = int(bus_row.get("end_minute", 0) or 0)
            published_windows = published_occupancy.get(vehicle_id, [])
            if any(_window_overlaps(start_minute, end_minute, win_start, win_end) for win_start, win_end in published_windows):
                stale_assignments.append(
                    {
                        "day": day,
                        "bus_id": bus_row.get("bus_id"),
                        "vehicle_id": vehicle_id,
                        "reason": "vehicle_reserved_elsewhere",
                    }
                )
                continue
            selected_windows = selected_occupancy.get(vehicle_id, [])
            if any(_window_overlaps(start_minute, end_minute, win_start, win_end) for win_start, win_end in selected_windows):
                stale_assignments.append(
                    {
                        "day": day,
                        "bus_id": bus_row.get("bus_id"),
                        "vehicle_id": vehicle_id,
                        "reason": "vehicle_reused_in_snapshot",
                    }
                )
                continue
            selected_occupancy.setdefault(vehicle_id, []).append((start_minute, end_minute))
            valid_selected_assignments[row_key] = {
                "day": day,
                "bus_id": bus_row.get("bus_id"),
                "vehicle_id": vehicle_id,
                "vehicle_code": str(vehicle.get("vehicle_code") or "") or None,
                "plate": str(vehicle.get("plate") or "") or None,
                "company_id": str(vehicle.get("company_id") or "") or None,
                "company_name": str(vehicle.get("company_name") or "") or None,
                "seats_base": int(vehicle.get("seats_base") or vehicle.get("seats_min") or 0),
                "seats_pmr": int(vehicle.get("seats_pmr") or 0),
                "seats_min": int(vehicle.get("seats_min") or 0),
                "seats_max": int(vehicle.get("seats_max") or 0),
            }

        pending_items: List[Dict[str, Any]] = []
        for bus_row in bus_rows:
            row_key = _day_bus_key(day, bus_row.get("bus_id"))
            if row_key in valid_selected_assignments:
                continue

            preference = _safe_dict(bus_selections_by_key.get(row_key))
            preferred_company_id = str(preference.get("company_id") or "").strip() or None
            selected_vehicle_id = str(preference.get("vehicle_id") or "").strip() or None
            excluded_vehicle_ids = {
                str(vehicle_id).strip()
                for vehicle_id in _safe_list(preference.get("excluded_vehicle_ids"))
                if str(vehicle_id).strip()
            }

            suggestions: List[Dict[str, Any]] = []
            for vehicle in vehicles:
                vehicle_id = str(vehicle.get("id") or "").strip()
                if not vehicle_id or vehicle_id in excluded_vehicle_ids:
                    continue
                if int(vehicle.get("seats_max", 0) or 0) < int(bus_row.get("required_seats", 0) or 0):
                    continue
                windows = []
                windows.extend(published_occupancy.get(vehicle_id, []))
                windows.extend(selected_occupancy.get(vehicle_id, []))
                if any(
                    _window_overlaps(
                        int(bus_row.get("start_minute", 0) or 0),
                        int(bus_row.get("end_minute", 0) or 0),
                        win_start,
                        win_end,
                    )
                    for win_start, win_end in windows
                ):
                    continue
                suggestions.append(
                    {
                        "vehicle_id": vehicle_id,
                        "vehicle_code": str(vehicle.get("vehicle_code") or ""),
                        "plate": str(vehicle.get("plate") or "") or None,
                        "company_id": str(vehicle.get("company_id") or "") or None,
                        "company_name": str(vehicle.get("company_name") or "") or None,
                        "seats_base": int(vehicle.get("seats_base") or vehicle.get("seats_min") or 0),
                        "seats_pmr": int(vehicle.get("seats_pmr") or 0),
                        "seats_min": int(vehicle.get("seats_min") or 0),
                        "seats_max": int(vehicle.get("seats_max") or 0),
                        "overflow": max(0, int(vehicle.get("seats_max", 0) or 0) - int(bus_row.get("required_seats", 0) or 0)),
                    }
                )
            suggestions.sort(
                key=lambda vehicle: (
                    _fleet_score_for_requirement(vehicle, int(bus_row.get("required_seats", 0) or 0)),
                    str(vehicle.get("company_name") or ""),
                    str(vehicle.get("vehicle_code") or ""),
                )
            )
            pending_items.append(
                {
                    **bus_row,
                    "required_capacity": int(bus_row.get("required_seats", 0) or 0),
                    "time_window": {
                        "start_minute": int(bus_row.get("start_minute", 0) or 0),
                        "end_minute": int(bus_row.get("end_minute", 0) or 0),
                    },
                    "already_real_bound": False,
                    "preferred_company_id": preferred_company_id,
                    "selected_vehicle_id": selected_vehicle_id,
                    "suggestions": suggestions[:12],
                    "suggested_real_vehicles": suggestions[:12],
                }
            )

        real_bound_count = len(valid_selected_assignments)
        pending_real_reconciliation_count = max(0, required_bus_count - real_bound_count)
        virtual_bound_count = pending_real_reconciliation_count
        company_mix = _build_company_mix(pending_items, company_capacity_summary)
        day_result = {
            "day": day,
            "required_bus_count": required_bus_count,
            "real_bound_count": real_bound_count,
            "virtual_bound_count": virtual_bound_count,
            "pending_real_reconciliation_count": pending_real_reconciliation_count,
            "available_real_vehicle_count": len(vehicles),
            "companies_available": len(company_capacity_summary),
            "estimated_virtual_remaining": int(company_mix.get("uncovered_buses", 0) or 0),
            "scope_vehicle_count": int(scope_vehicle_count or len(vehicles)),
            "company_capacity_summary": company_capacity_summary,
            "company_mix": company_mix,
            "items": pending_items,
            "pending_assignments": pending_items,
            "selected_assignments": _materialize_selected_assignments(valid_selected_assignments),
            "bus_selections": list(bus_selections_by_key.values()),
            "company_allocations": _safe_list(day_snapshot.get("company_allocations")),
            "stale_assignments": stale_assignments,
            "unresolved": _safe_list(day_snapshot.get("unresolved")),
            "scope_mode": scope_mode,
            "scope_label": scope_label,
            "scope_company_ids": normalized_scope_company_ids,
            "scope_company_names": scope_company_names,
        }
        days_payload[day] = day_result
        top_required += required_bus_count
        top_real += real_bound_count
        top_virtual += virtual_bound_count
        top_pending += pending_real_reconciliation_count

    return {
        "workspace_id": workspace_id,
        "scope_mode": scope_mode,
        "scope_label": scope_label,
        "scope_company_ids": normalized_scope_company_ids,
        "scope_company_names": scope_company_names,
        "scope_vehicle_count": int(scope_vehicle_count or len(vehicles)),
        "available_real_vehicle_count": len(vehicles),
        "company_capacity_summary": company_capacity_summary,
        "required_bus_count": top_required,
        "real_bound_count": top_real,
        "virtual_bound_count": top_virtual,
        "pending_real_reconciliation_count": top_pending,
        "days": days_payload,
        "reconciliation_snapshot": existing_snapshot,
        "updated_at": datetime.utcnow().isoformat(),
    }


def merge_reconciliation_snapshot(
    *,
    previous_snapshot: Optional[Dict[str, Any]],
    day: str,
    day_payload: Dict[str, Any],
    scope_mode: str,
    scope_company_ids: List[str],
    scope_label: str,
) -> Dict[str, Any]:
    snapshot = _normalize_reconciliation_snapshot(previous_snapshot)
    days = _safe_dict(snapshot.get("days"))
    days[str(day)] = day_payload
    return {
        **snapshot,
        "scope_mode": scope_mode,
        "scope_company_ids": list(scope_company_ids),
        "scope_label": scope_label,
        "updated_at": datetime.utcnow().isoformat(),
        "days": days,
    }


def materialize_schedule_from_reconciliation_snapshot(
    schedule_by_day: Dict[str, Any],
    reconciliation_snapshot: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_schedule = schedule_by_day if isinstance(schedule_by_day, dict) else {}
    snapshot = _normalize_reconciliation_snapshot(reconciliation_snapshot)
    snapshot_days = _safe_dict(snapshot.get("days"))
    if not snapshot_days:
        return normalized_schedule

    selected_assignments: Dict[str, Dict[str, Any]] = {}
    reconciliation_days: set[str] = set()
    for day_key, day_payload in snapshot_days.items():
        reconciliation_days.add(str(day_key))
        for assignment in _safe_list(_safe_dict(day_payload).get("selected_assignments")):
            if not isinstance(assignment, dict):
                continue
            key = _day_bus_key(assignment.get("day") or day_key, assignment.get("bus_id"))
            selected_assignments[key] = assignment

    materialized = {}
    for day_key, day_payload in normalized_schedule.items():
        cloned_day_payload = _safe_dict(day_payload).copy()
        schedule = [dict(bus) for bus in _safe_list(_safe_dict(day_payload).get("schedule"))]
        if str(day_key) in reconciliation_days:
            next_schedule: List[Dict[str, Any]] = []
            for bus in schedule:
                bus_copy = dict(bus)
                key = _day_bus_key(day_key, bus_copy.get("bus_id"))
                assignment = _safe_dict(selected_assignments.get(key))
                if assignment:
                    bus_copy["uses_fleet_profile"] = True
                    bus_copy["fleet_assignment_type"] = "real"
                    bus_copy["fleet_binding_state"] = "preview"
                    bus_copy["assigned_vehicle_id"] = str(assignment.get("vehicle_id") or "") or None
                    bus_copy["assigned_vehicle_code"] = str(assignment.get("vehicle_code") or "") or None
                    bus_copy["assigned_vehicle_plate"] = str(assignment.get("plate") or "") or None
                    bus_copy["assigned_company_id"] = str(assignment.get("company_id") or "") or None
                    bus_copy["assigned_company_name"] = str(assignment.get("company_name") or "") or None
                    bus_copy["assigned_vehicle_seats_base"] = int(assignment.get("seats_base", assignment.get("seats_min", 0)) or 0) or None
                    bus_copy["assigned_vehicle_seats_pmr"] = int(assignment.get("seats_pmr", 0) or 0)
                    bus_copy["assigned_vehicle_seats_min"] = int(assignment.get("seats_min", 0) or 0) or None
                    bus_copy["assigned_vehicle_seats_max"] = int(assignment.get("seats_max", 0) or 0) or None
                else:
                    bus_copy["uses_fleet_profile"] = False
                    bus_copy["fleet_assignment_type"] = "virtual"
                    bus_copy["fleet_binding_state"] = "preview"
                    bus_copy["assigned_vehicle_id"] = None
                    bus_copy["assigned_vehicle_code"] = None
                    bus_copy["assigned_vehicle_plate"] = None
                    bus_copy["assigned_company_id"] = None
                    bus_copy["assigned_company_name"] = None
                    bus_copy["assigned_vehicle_seats_base"] = None
                    bus_copy["assigned_vehicle_seats_pmr"] = None
                    bus_copy["assigned_vehicle_seats_min"] = None
                    bus_copy["assigned_vehicle_seats_max"] = None
                next_schedule.append(bus_copy)
            cloned_day_payload["schedule"] = next_schedule
        materialized[day_key] = cloned_day_payload
    return materialized


def validate_reconciliation_snapshot(
    db,
    *,
    scope_company_ids: List[str],
    schedule_by_day: Dict[str, Any],
    reconciliation_snapshot: Optional[Dict[str, Any]],
    exclude_workspace_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    snapshot = _normalize_reconciliation_snapshot(reconciliation_snapshot)
    snapshot_days = _safe_dict(snapshot.get("days"))
    if not snapshot_days:
        return []

    normalized_schedule = schedule_by_day if isinstance(schedule_by_day, dict) else {}
    vehicles = _normalize_vehicle_pool(
        primary_company_id=scope_company_ids[0] if scope_company_ids else "",
        scope_company_ids=scope_company_ids,
    )
    vehicle_by_id = {str(vehicle.get("id") or "").strip(): vehicle for vehicle in vehicles if str(vehicle.get("id") or "").strip()}
    issues: List[Dict[str, Any]] = []
    selected_windows: Dict[str, Dict[str, List[Tuple[int, int]]]] = {}

    for day_key, day_payload in snapshot_days.items():
        day = str(day_key)
        bus_rows = {
            _day_bus_key(day, row.get("bus_id")): row
            for row in _build_day_bus_rows(_safe_dict(normalized_schedule.get(day)), day)
        }
        published_occupancy = _build_published_occupancy(
            db,
            day=day,
            scope_company_ids=scope_company_ids,
            exclude_workspace_id=exclude_workspace_id,
        )
        for assignment in _safe_list(_safe_dict(day_payload).get("selected_assignments")):
            if not isinstance(assignment, dict):
                continue
            key = _day_bus_key(assignment.get("day") or day, assignment.get("bus_id"))
            bus_row = bus_rows.get(key)
            vehicle_id = str(assignment.get("vehicle_id") or "").strip()
            if bus_row is None:
                issues.append({"day": day, "bus_id": assignment.get("bus_id"), "reason": "bus_not_found"})
                continue
            vehicle = vehicle_by_id.get(vehicle_id)
            if vehicle is None:
                issues.append({"day": day, "bus_id": assignment.get("bus_id"), "vehicle_id": vehicle_id, "reason": "vehicle_not_found"})
                continue
            start_minute = int(bus_row.get("start_minute", 0) or 0)
            end_minute = int(bus_row.get("end_minute", 0) or 0)
            if any(_window_overlaps(start_minute, end_minute, win_start, win_end) for win_start, win_end in published_occupancy.get(vehicle_id, [])):
                issues.append({"day": day, "bus_id": assignment.get("bus_id"), "vehicle_id": vehicle_id, "reason": "vehicle_reserved_elsewhere"})
                continue
            existing = selected_windows.setdefault(vehicle_id, {}).setdefault(day, [])
            if any(_window_overlaps(start_minute, end_minute, win_start, win_end) for win_start, win_end in existing):
                issues.append({"day": day, "bus_id": assignment.get("bus_id"), "vehicle_id": vehicle_id, "reason": "vehicle_reused_in_snapshot"})
                continue
            existing.append((start_minute, end_minute))
    return issues
