"""
Operational fleet publication services.

Publication creates real/virtual operational reservations and blocks
conflicting real allocations against other published workspaces.
"""

from __future__ import annotations

from datetime import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from db import models as db_models
from models import BusSchedule
from services.fleet_assignment import (
    _bus_required_seats,
    assign_fleet_profiles_to_schedule,
    load_active_fleet_profiles,
)
from services.fleet_repository import FleetRepository


ALL_DAYS = ("L", "M", "Mc", "X", "V")


def _to_minutes(value: Any) -> int:
    if isinstance(value, time):
        return (int(value.hour) * 60) + int(value.minute)
    if isinstance(value, str):
        try:
            hh, mm = [int(part) for part in value.split(":")[:2]]
            return (hh * 60) + mm
        except Exception:
            return 0
    return 0


def _deserialize_day_schedule(raw_schedule: Any) -> List[BusSchedule]:
    parsed: List[BusSchedule] = []
    for bus in raw_schedule or []:
        if not isinstance(bus, dict):
            continue
        try:
            parsed.append(BusSchedule(**bus))
        except Exception:
            continue
    return parsed


def deserialize_schedule_by_day(schedule_by_day: Dict[str, Any]) -> Dict[str, List[BusSchedule]]:
    parsed: Dict[str, List[BusSchedule]] = {day: [] for day in ALL_DAYS}
    if not isinstance(schedule_by_day, dict):
        return parsed
    for day in ALL_DAYS:
        raw = schedule_by_day.get(day)
        if isinstance(raw, list):
            parsed[day] = _deserialize_day_schedule(raw)
        elif isinstance(raw, dict):
            parsed[day] = _deserialize_day_schedule(raw.get("schedule", []))
    return parsed


def _stats_from_schedule(day_schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_routes = 0
    total_entries = 0
    total_exits = 0
    for bus in day_schedule:
        items = bus.get("items", []) if isinstance(bus, dict) else []
        total_routes += len(items)
        for item in items:
            item_type = str((item or {}).get("type", "")).lower()
            if item_type == "entry":
                total_entries += 1
            elif item_type == "exit":
                total_exits += 1
    return {
        "total_buses": len(day_schedule),
        "total_routes": total_routes,
        "total_entries": total_entries,
        "total_exits": total_exits,
        "avg_routes_per_bus": round(total_routes / len(day_schedule), 2) if day_schedule else 0,
    }


def serialize_assigned_schedule_by_day(
    base_schedule_by_day: Dict[str, Any],
    assigned_by_day: Dict[str, List[BusSchedule]],
) -> Dict[str, Any]:
    serialized: Dict[str, Any] = {}
    base_schedule_by_day = base_schedule_by_day if isinstance(base_schedule_by_day, dict) else {}
    for day in ALL_DAYS:
        base_day = base_schedule_by_day.get(day)
        day_schedule = [bus.model_dump(mode="json") for bus in (assigned_by_day.get(day) or [])]
        if isinstance(base_day, dict):
            serialized[day] = {
                "schedule": day_schedule,
                "stats": _stats_from_schedule(day_schedule),
                "metadata": base_day.get("metadata", {}) if isinstance(base_day.get("metadata"), dict) else {},
                "unassigned_routes": base_day.get("unassigned_routes", []) if isinstance(base_day.get("unassigned_routes"), list) else [],
            }
        else:
            serialized[day] = {
                "schedule": day_schedule,
                "stats": _stats_from_schedule(day_schedule),
                "metadata": {},
                "unassigned_routes": [],
            }
    return serialized


def _iter_assignment_intervals(
    fallback_company_id: str,
    schedule_by_day: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for day in ALL_DAYS:
        day_payload = schedule_by_day.get(day, {})
        buses = day_payload.get("schedule", []) if isinstance(day_payload, dict) else []
        for bus in buses:
            if not isinstance(bus, dict):
                continue
            bus_id = str(bus.get("bus_id", "") or "")
            vehicle_id = str(bus.get("assigned_vehicle_id", "") or "")
            assignment_type = str(bus.get("fleet_assignment_type", "virtual") or "virtual").lower()
            bus_company_id = str(bus.get("assigned_company_id", "") or "").strip() or fallback_company_id
            items = bus.get("items", []) if isinstance(bus.get("items"), list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                start_minute = _to_minutes(item.get("start_time"))
                end_minute = _to_minutes(item.get("end_time"))
                if end_minute <= start_minute:
                    end_minute = start_minute + 1
                rows.append(
                    {
                        "company_id": bus_company_id,
                        "day": day,
                        "bus_id": bus_id,
                        "route_id": str(item.get("route_id", "") or ""),
                        "start_minute": start_minute,
                        "end_minute": end_minute,
                        "assigned_vehicle_id": vehicle_id if assignment_type == "real" and vehicle_id else None,
                        "assignment_type": assignment_type if assignment_type in {"real", "virtual"} else "virtual",
                    }
                )
    return rows


def _bus_required_seats_from_payload(bus: Dict[str, Any]) -> int:
    required = int(bus.get("min_required_seats", 0) or 0)
    if required > 0:
        return required
    items = bus.get("items", []) if isinstance(bus.get("items"), list) else []
    max_needed = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        max_needed = max(max_needed, int(item.get("capacity_needed", 0) or 0))
    return max(1, max_needed or 1)


def _bus_time_window_from_payload(bus: Dict[str, Any]) -> Tuple[int, int]:
    items = bus.get("items", []) if isinstance(bus.get("items"), list) else []
    start_minute: Optional[int] = None
    end_minute: Optional[int] = None
    for item in items:
        if not isinstance(item, dict):
            continue
        item_start = _to_minutes(item.get("start_time"))
        item_end = _to_minutes(item.get("end_time"))
        if item_end <= item_start:
            item_end = item_start + 1
        start_minute = item_start if start_minute is None else min(start_minute, item_start)
        end_minute = item_end if end_minute is None else max(end_minute, item_end)
    if start_minute is None or end_minute is None:
        return (0, 1)
    return (int(start_minute), int(max(end_minute, start_minute + 1)))


def _window_overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return (a_start < b_end) and (a_end > b_start)


def _build_virtual_reconciliation_report(
    *,
    company_id: str,
    scope_company_ids: Optional[List[str]],
    assigned_schedule_by_day: Dict[str, Any],
) -> Dict[str, Any]:
    repository = FleetRepository()
    vehicles = repository.list_active_profiles(company_id=company_id, company_ids=scope_company_ids)
    vehicle_pool: List[Dict[str, Any]] = []
    for raw in vehicles:
        seats_max = int(raw.get("seats_max", 0) or 0)
        if seats_max <= 0:
            continue
        vehicle_pool.append(
            {
                "id": str(raw.get("id", "") or ""),
                "vehicle_code": str(raw.get("vehicle_code", "") or "").strip(),
                "plate": str(raw.get("plate", "") or "").strip(),
                "company_id": str(raw.get("company_id", "") or "").strip() or None,
                "company_name": str(raw.get("company_name", "") or "").strip() or None,
                "seats_base": int(raw.get("seats_base", raw.get("seats_min", 0)) or 0),
                "seats_pmr": int(raw.get("seats_pmr", 0) or 0),
                "seats_min": int(raw.get("seats_min", 0) or 0),
                "seats_max": seats_max,
            }
        )

    occupied: Dict[str, Dict[str, List[Tuple[int, int]]]] = {}
    for day in ALL_DAYS:
        occupied.setdefault(day, {})
        day_payload = assigned_schedule_by_day.get(day, {}) if isinstance(assigned_schedule_by_day, dict) else {}
        buses = day_payload.get("schedule", []) if isinstance(day_payload, dict) else []
        for bus in buses:
            if not isinstance(bus, dict):
                continue
            if str(bus.get("fleet_assignment_type", "virtual") or "virtual").lower() != "real":
                continue
            vehicle_id = str(bus.get("assigned_vehicle_id", "") or "").strip()
            if not vehicle_id:
                continue
            start_minute, end_minute = _bus_time_window_from_payload(bus)
            occupied[day].setdefault(vehicle_id, []).append((start_minute, end_minute))

    items: List[Dict[str, Any]] = []
    for day in ALL_DAYS:
        day_payload = assigned_schedule_by_day.get(day, {}) if isinstance(assigned_schedule_by_day, dict) else {}
        buses = day_payload.get("schedule", []) if isinstance(day_payload, dict) else []
        for bus in buses:
            if not isinstance(bus, dict):
                continue
            if str(bus.get("fleet_assignment_type", "virtual") or "virtual").lower() != "virtual":
                continue

            start_minute, end_minute = _bus_time_window_from_payload(bus)
            required = _bus_required_seats_from_payload(bus)
            suggestions: List[Dict[str, Any]] = []
            for vehicle in vehicle_pool:
                if int(vehicle["seats_max"]) < required:
                    continue
                vehicle_windows = occupied.get(day, {}).get(str(vehicle["id"]), [])
                has_overlap = any(
                    _window_overlaps(start_minute, end_minute, win_start, win_end)
                    for (win_start, win_end) in vehicle_windows
                )
                if has_overlap:
                    continue
                suggestions.append(
                    {
                        "vehicle_id": str(vehicle["id"]),
                        "vehicle_code": str(vehicle["vehicle_code"]),
                        "plate": str(vehicle["plate"]),
                        "company_id": vehicle.get("company_id"),
                        "company_name": vehicle.get("company_name"),
                        "seats_base": int(vehicle.get("seats_base", vehicle.get("seats_min", 0)) or 0),
                        "seats_pmr": int(vehicle.get("seats_pmr", 0) or 0),
                        "seats_min": int(vehicle.get("seats_min", 0) or 0),
                        "seats_max": int(vehicle["seats_max"]),
                        "overflow": max(0, int(vehicle["seats_max"]) - required),
                    }
                )
            suggestions.sort(key=lambda row: (int(row.get("overflow", 0)), int(row.get("seats_max", 0)), str(row.get("vehicle_code", ""))))
            top_suggestions = suggestions[:12]

            route_ids: List[str] = []
            for item in (bus.get("items", []) if isinstance(bus.get("items"), list) else []):
                if not isinstance(item, dict):
                    continue
                route_id = str(item.get("route_id", "") or "").strip()
                if route_id:
                    route_ids.append(route_id)

            items.append(
                {
                    "day": day,
                    "bus_id": str(bus.get("bus_id", "") or ""),
                    "required_seats": int(required),
                    "start_minute": int(start_minute),
                    "end_minute": int(end_minute),
                    "route_ids": route_ids,
                    "suggestions": top_suggestions,
                }
            )

    def _build_company_mix(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        recommendation_by_company: Dict[str, Dict[str, Any]] = {}
        coverage_by_company: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            suggestions = row.get("suggestions", []) if isinstance(row.get("suggestions"), list) else []
            seen_companies: set[str] = set()
            for suggestion in suggestions:
                company_key = str(suggestion.get("company_id") or "unassigned")
                company_name = str(suggestion.get("company_name") or "Empresa sin identificar")
                coverage_entry = coverage_by_company.setdefault(
                    company_key,
                    {
                        "company_id": suggestion.get("company_id"),
                        "company_name": company_name,
                        "coverable_assignments": 0,
                        "candidate_vehicle_ids": set(),
                        "candidate_vehicle_codes": set(),
                    },
                )
                vehicle_id = str(suggestion.get("vehicle_id") or "").strip()
                vehicle_code = str(suggestion.get("vehicle_code") or "").strip()
                if company_key not in seen_companies:
                    coverage_entry["coverable_assignments"] += 1
                    seen_companies.add(company_key)
                if vehicle_id:
                    coverage_entry["candidate_vehicle_ids"].add(vehicle_id)
                if vehicle_code:
                    coverage_entry["candidate_vehicle_codes"].add(vehicle_code)

            if suggestions:
                best_suggestion = suggestions[0]
                company_key = str(best_suggestion.get("company_id") or "unassigned")
                company_name = str(best_suggestion.get("company_name") or "Empresa sin identificar")
                recommendation_entry = recommendation_by_company.setdefault(
                    company_key,
                    {
                        "company_id": best_suggestion.get("company_id"),
                        "company_name": company_name,
                        "recommended_count": 0,
                        "vehicle_codes": [],
                    },
                )
                recommendation_entry["recommended_count"] += 1
                best_vehicle_code = str(best_suggestion.get("vehicle_code") or "").strip()
                if best_vehicle_code and best_vehicle_code not in recommendation_entry["vehicle_codes"]:
                    recommendation_entry["vehicle_codes"].append(best_vehicle_code)

        recommendations: List[Dict[str, Any]] = []
        for company_key, recommendation_entry in recommendation_by_company.items():
            coverage_entry = coverage_by_company.get(company_key, {})
            recommendations.append(
                {
                    "company_id": recommendation_entry.get("company_id"),
                    "company_name": recommendation_entry.get("company_name"),
                    "recommended_count": int(recommendation_entry.get("recommended_count", 0) or 0),
                    "coverable_assignments": int(coverage_entry.get("coverable_assignments", 0) or 0),
                    "candidate_vehicle_count": len(coverage_entry.get("candidate_vehicle_ids", set())),
                    "vehicle_codes": recommendation_entry.get("vehicle_codes", [])[:4],
                }
            )

        recommendations.sort(
            key=lambda row: (
                -int(row.get("recommended_count", 0) or 0),
                -int(row.get("coverable_assignments", 0) or 0),
                str(row.get("company_name", "")),
            )
        )

        return {
            "total_pending_buses": len(rows),
            "recommended_companies": recommendations,
            "companies_with_options": len(coverage_by_company),
            "uncovered_buses": sum(
                1
                for row in rows
                if not isinstance(row.get("suggestions"), list) or len(row.get("suggestions", [])) == 0
            ),
        }

    by_day: Dict[str, Any] = {}
    for day in ALL_DAYS:
        day_items = [row for row in items if row.get("day") == day]
        by_day[day] = {
            "pending_virtual": len(day_items),
            "items": day_items,
            "company_mix": _build_company_mix(day_items),
        }

    return {
        "pending_count": len(items),
        "by_day": by_day,
        "items": items,
        "company_mix": _build_company_mix(items),
    }


def detect_publication_conflicts(
    db,
    *,
    company_id: str,
    scope_company_ids: Optional[List[str]] = None,
    candidate_rows: List[Dict[str, Any]],
    exclude_workspace_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    normalized_scope = [str(cid).strip() for cid in (scope_company_ids or []) if str(cid).strip()]
    if not normalized_scope:
        normalized_scope = [str(company_id)]
    for row in candidate_rows:
        if row.get("assignment_type") != "real":
            continue
        vehicle_id = str(row.get("assigned_vehicle_id", "") or "")
        if not vehicle_id:
            continue
        query = db.query(db_models.PublishedFleetAssignmentModel).filter(
            db_models.PublishedFleetAssignmentModel.company_id.in_(normalized_scope),
            db_models.PublishedFleetAssignmentModel.day == str(row.get("day", "")),
            db_models.PublishedFleetAssignmentModel.assignment_type == "real",
            db_models.PublishedFleetAssignmentModel.active.is_(True),
            db_models.PublishedFleetAssignmentModel.assigned_vehicle_id == vehicle_id,
        )
        if exclude_workspace_id:
            query = query.filter(
                db_models.PublishedFleetAssignmentModel.workspace_id != str(exclude_workspace_id)
            )

        start_minute = int(row.get("start_minute", 0))
        end_minute = int(row.get("end_minute", 0))
        overlap_rows = query.filter(
            db_models.PublishedFleetAssignmentModel.start_minute < end_minute,
            db_models.PublishedFleetAssignmentModel.end_minute > start_minute,
        ).all()

        for overlap in overlap_rows:
            conflicts.append(
                {
                    "day": str(row.get("day", "")),
                    "vehicle_id": vehicle_id,
                    "candidate_workspace_id": exclude_workspace_id,
                    "conflicting_workspace_id": str(overlap.workspace_id),
                    "conflicting_version_id": str(overlap.workspace_version_id),
                    "candidate_route_id": str(row.get("route_id", "")),
                    "conflicting_route_id": str(overlap.route_id or ""),
                    "candidate_range": [start_minute, end_minute],
                    "conflicting_range": [int(overlap.start_minute or 0), int(overlap.end_minute or 0)],
                    "message": "Vehículo ya reservado en otra optimización publicada en rango solapado",
                }
            )
    return conflicts


def _assign_schedule_by_day_preserving_existing(
    *,
    schedule_by_day: Dict[str, Any],
    company_id: str,
    scope_company_ids: Optional[List[str]] = None,
    binding_state: str = "committed",
) -> Tuple[Dict[str, List[BusSchedule]], Dict[str, Any]]:
    raw_by_day = deserialize_schedule_by_day(schedule_by_day)
    fleet_profiles = load_active_fleet_profiles(company_id=company_id, company_ids=scope_company_ids)
    fleet_by_id = {
        str(vehicle.get("id") or "").strip(): vehicle
        for vehicle in fleet_profiles
        if str(vehicle.get("id") or "").strip()
    }

    assigned_by_day: Dict[str, List[BusSchedule]] = {}
    summary_by_day: Dict[str, Any] = {}
    total_assigned = 0
    total_virtual_buses = 0

    for day, original_schedule in (raw_by_day or {}).items():
        day_schedule = list(original_schedule or [])
        locked_buses: Dict[str, BusSchedule] = {}
        reserved_vehicle_ids: set[str] = set()

        for bus in day_schedule:
            bus_id = str(getattr(bus, "bus_id", "") or "").strip()
            vehicle_id = str(getattr(bus, "assigned_vehicle_id", "") or "").strip()
            assignment_type = str(getattr(bus, "fleet_assignment_type", "") or "").strip().lower()
            if not bus_id or assignment_type != "real" or not vehicle_id:
                continue
            if vehicle_id in reserved_vehicle_ids:
                continue
            profile = fleet_by_id.get(vehicle_id)
            if not profile:
                continue
            required_seats = int(getattr(bus, "min_required_seats", 0) or 0) or int(_bus_required_seats(bus))
            if int(profile.get("seats_max", 0) or 0) < required_seats:
                continue

            bus.uses_fleet_profile = True
            bus.fleet_assignment_type = "real"
            bus.fleet_binding_state = str(binding_state or "committed")
            bus.assigned_vehicle_id = vehicle_id
            bus.assigned_vehicle_code = str(profile.get("vehicle_code") or "") or None
            bus.assigned_vehicle_plate = str(profile.get("plate") or "") or None
            bus.assigned_company_id = str(profile.get("company_id") or "") or None
            bus.assigned_company_name = str(profile.get("company_name") or "") or None
            bus.assigned_vehicle_seats_base = int(profile.get("seats_base") or profile.get("seats_min") or 0)
            bus.assigned_vehicle_seats_pmr = int(profile.get("seats_pmr") or 0)
            bus.assigned_vehicle_seats_min = int(profile.get("seats_min") or 0)
            bus.assigned_vehicle_seats_max = int(profile.get("seats_max") or 0)
            locked_buses[bus_id] = bus
            reserved_vehicle_ids.add(vehicle_id)

        remaining_buses = [
            bus
            for bus in day_schedule
            if str(getattr(bus, "bus_id", "") or "").strip() not in locked_buses
        ]
        remaining_fleet = [
            vehicle
            for vehicle in fleet_profiles
            if str(vehicle.get("id") or "").strip() not in reserved_vehicle_ids
        ]
        assigned_remaining, remaining_summary = assign_fleet_profiles_to_schedule(
            remaining_buses,
            fleet_profiles=remaining_fleet,
            binding_state=binding_state,
        )
        remaining_by_bus = {
            str(getattr(bus, "bus_id", "") or "").strip(): bus
            for bus in assigned_remaining
        }

        merged_schedule: List[BusSchedule] = []
        for bus in day_schedule:
            bus_id = str(getattr(bus, "bus_id", "") or "").strip()
            merged_schedule.append(locked_buses.get(bus_id) or remaining_by_bus.get(bus_id) or bus)

        assigned_count = len(locked_buses) + int(remaining_summary.get("fleet_assigned", 0) or 0)
        virtual_count = max(0, len(merged_schedule) - assigned_count)
        assigned_by_day[day] = merged_schedule
        summary_by_day[day] = {
            "fleet_available": len(fleet_profiles),
            "fleet_assigned": assigned_count,
            "virtual_buses": virtual_count,
            "unmatched_bus_ids": remaining_summary.get("unmatched_bus_ids", []),
            "locked_bus_ids": list(locked_buses.keys()),
        }
        total_assigned += assigned_count
        total_virtual_buses += virtual_count

    return assigned_by_day, {
        "days": summary_by_day,
        "total_assigned": total_assigned,
        "total_virtual_buses": total_virtual_buses,
    }


def preview_workspace_publication(
    db,
    *,
    company_id: str,
    scope_company_ids: Optional[List[str]] = None,
    schedule_by_day: Dict[str, Any],
    exclude_workspace_id: Optional[str] = None,
) -> Dict[str, Any]:
    assigned_raw_by_day, fleet_assignment_summary = _assign_schedule_by_day_preserving_existing(
        schedule_by_day=schedule_by_day,
        company_id=company_id,
        scope_company_ids=scope_company_ids,
        binding_state="committed",
    )
    assigned_schedule_by_day = serialize_assigned_schedule_by_day(schedule_by_day, assigned_raw_by_day)
    candidate_rows = _iter_assignment_intervals(company_id, assigned_schedule_by_day)
    conflicts = detect_publication_conflicts(
        db,
        company_id=company_id,
        scope_company_ids=scope_company_ids,
        candidate_rows=candidate_rows,
        exclude_workspace_id=exclude_workspace_id,
    )
    real_assigned = int(fleet_assignment_summary.get("total_assigned", 0))
    virtual_created = int(fleet_assignment_summary.get("total_virtual_buses", 0))
    days_summary = fleet_assignment_summary.get("days", {}) if isinstance(fleet_assignment_summary.get("days"), dict) else {}
    reconciliation = _build_virtual_reconciliation_report(
        company_id=company_id,
        scope_company_ids=scope_company_ids,
        assigned_schedule_by_day=assigned_schedule_by_day,
    )

    return {
        "company_id": company_id,
        "blocked": len(conflicts) > 0,
        "conflicts": conflicts,
        "real_assigned": real_assigned,
        "virtual_created": virtual_created,
        "days": days_summary,
        "scope_company_ids": [str(cid) for cid in (scope_company_ids or [company_id])],
        "schedule_by_day": assigned_schedule_by_day,
        "candidate_rows": candidate_rows,
        "reconciliation": reconciliation,
    }


def persist_publication_assignments(
    db,
    *,
    workspace_id: str,
    workspace_version_id: str,
    company_id: str,
    candidate_rows: List[Dict[str, Any]],
) -> None:
    db.query(db_models.PublishedFleetAssignmentModel).filter(
        db_models.PublishedFleetAssignmentModel.workspace_id == str(workspace_id),
        db_models.PublishedFleetAssignmentModel.active.is_(True),
    ).update({"active": False})

    for row in candidate_rows:
        db.add(
            db_models.PublishedFleetAssignmentModel(
                id=str(uuid4()),
                company_id=str(row.get("company_id", "") or company_id),
                workspace_id=str(workspace_id),
                workspace_version_id=str(workspace_version_id),
                day=str(row.get("day", "")),
                bus_id=str(row.get("bus_id", "")),
                route_id=str(row.get("route_id", "")),
                start_minute=int(row.get("start_minute", 0)),
                end_minute=int(row.get("end_minute", 0)),
                assigned_vehicle_id=row.get("assigned_vehicle_id"),
                assignment_type=str(row.get("assignment_type", "virtual")),
                active=True,
                details={
                    "company_id": str(row.get("company_id", "") or company_id),
                    "bus_id": str(row.get("bus_id", "")),
                },
            )
        )
