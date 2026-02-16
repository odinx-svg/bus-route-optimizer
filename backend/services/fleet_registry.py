"""
Fleet registry persistence service.

Stores vehicle profiles in a JSON file so fleet management works even when
database persistence is disabled.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class FleetRegistry:
    """Simple thread-safe JSON-backed registry for fleet vehicles."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.storage_path = storage_path or (base_dir / "data" / "fleet_profiles.json")
        self._lock = threading.Lock()
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write_data({"version": 1, "vehicles": []})

    def _read_data(self) -> Dict[str, Any]:
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"version": 1, "vehicles": []}
        except json.JSONDecodeError:
            data = {"version": 1, "vehicles": []}
        if not isinstance(data, dict):
            return {"version": 1, "vehicles": []}
        vehicles = data.get("vehicles", [])
        if not isinstance(vehicles, list):
            vehicles = []
        return {"version": int(data.get("version", 1) or 1), "vehicles": vehicles}

    def _write_data(self, data: Dict[str, Any]) -> None:
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for doc in documents or []:
            if not isinstance(doc, dict):
                continue
            doc_type = str(doc.get("doc_type", "") or "").strip()
            reference = str(doc.get("reference", "") or "").strip()
            issue_date = str(doc.get("issue_date", "") or "").strip() or None
            expiry_date = str(doc.get("expiry_date", "") or "").strip() or None
            notes = str(doc.get("notes", "") or "").strip() or None
            if not doc_type and not reference and not expiry_date and not issue_date:
                continue
            normalized.append(
                {
                    "id": str(doc.get("id", "") or uuid4()),
                    "doc_type": doc_type,
                    "reference": reference,
                    "issue_date": issue_date,
                    "expiry_date": expiry_date,
                    "notes": notes,
                }
            )
        return normalized

    @staticmethod
    def _sort_key(vehicle: Dict[str, Any]) -> tuple:
        code = str(vehicle.get("vehicle_code", "") or "")
        numeric = "".join(ch for ch in code if ch.isdigit())
        if numeric:
            return (0, int(numeric), code)
        return (1, 0, code)

    def _validate_unique_constraints(
        self,
        vehicles: List[Dict[str, Any]],
        candidate: Dict[str, Any],
        exclude_id: Optional[str] = None,
    ) -> None:
        candidate_plate = str(candidate.get("plate", "") or "").strip().upper()
        candidate_code = str(candidate.get("vehicle_code", "") or "").strip().upper()
        for v in vehicles:
            v_id = str(v.get("id", "") or "")
            if exclude_id and v_id == exclude_id:
                continue
            plate = str(v.get("plate", "") or "").strip().upper()
            code = str(v.get("vehicle_code", "") or "").strip().upper()
            if candidate_plate and plate and candidate_plate == plate:
                raise ValueError(f"La matrícula '{candidate.get('plate')}' ya existe")
            if candidate_code and code and candidate_code == code:
                raise ValueError(f"El código '{candidate.get('vehicle_code')}' ya existe")

    def list_vehicles(self) -> List[Dict[str, Any]]:
        with self._lock:
            data = self._read_data()
            vehicles = [v for v in data.get("vehicles", []) if isinstance(v, dict)]
            vehicles.sort(key=self._sort_key)
            return vehicles

    def get_vehicle(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            vehicles = self._read_data().get("vehicles", [])
            for vehicle in vehicles:
                if str(vehicle.get("id", "")) == str(vehicle_id):
                    return vehicle
            return None

    def create_vehicle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read_data()
            vehicles = data.get("vehicles", [])
            self._validate_unique_constraints(vehicles, payload)
            now = datetime.utcnow().isoformat()
            vehicle = {
                "id": str(uuid4()),
                "vehicle_code": str(payload.get("vehicle_code", "") or "").strip(),
                "plate": str(payload.get("plate", "") or "").strip(),
                "brand": str(payload.get("brand", "") or "").strip() or None,
                "model": str(payload.get("model", "") or "").strip() or None,
                "year": payload.get("year"),
                "seats_min": int(payload.get("seats_min") or 0),
                "seats_max": int(payload.get("seats_max") or 0),
                "status": str(payload.get("status", "active") or "active"),
                "fuel_type": str(payload.get("fuel_type", "") or "").strip() or None,
                "accessibility": bool(payload.get("accessibility", False)),
                "mileage_km": payload.get("mileage_km"),
                "notes": str(payload.get("notes", "") or "").strip() or None,
                "documents": self._normalize_documents(payload.get("documents", [])),
                "created_at": now,
                "updated_at": now,
            }
            vehicles.append(vehicle)
            data["vehicles"] = vehicles
            self._write_data(data)
            return vehicle

    def update_vehicle(self, vehicle_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = self._read_data()
            vehicles = data.get("vehicles", [])
            idx = next(
                (i for i, v in enumerate(vehicles) if str(v.get("id", "")) == str(vehicle_id)),
                -1,
            )
            if idx < 0:
                raise KeyError("Vehicle not found")

            existing = vehicles[idx]
            self._validate_unique_constraints(vehicles, payload, exclude_id=str(vehicle_id))
            now = datetime.utcnow().isoformat()
            updated = {
                "id": str(existing.get("id", vehicle_id)),
                "vehicle_code": str(payload.get("vehicle_code", "") or "").strip(),
                "plate": str(payload.get("plate", "") or "").strip(),
                "brand": str(payload.get("brand", "") or "").strip() or None,
                "model": str(payload.get("model", "") or "").strip() or None,
                "year": payload.get("year"),
                "seats_min": int(payload.get("seats_min") or 0),
                "seats_max": int(payload.get("seats_max") or 0),
                "status": str(payload.get("status", "active") or "active"),
                "fuel_type": str(payload.get("fuel_type", "") or "").strip() or None,
                "accessibility": bool(payload.get("accessibility", False)),
                "mileage_km": payload.get("mileage_km"),
                "notes": str(payload.get("notes", "") or "").strip() or None,
                "documents": self._normalize_documents(payload.get("documents", [])),
                "created_at": existing.get("created_at", now),
                "updated_at": now,
            }
            vehicles[idx] = updated
            data["vehicles"] = vehicles
            self._write_data(data)
            return updated

    def delete_vehicle(self, vehicle_id: str) -> bool:
        with self._lock:
            data = self._read_data()
            vehicles = data.get("vehicles", [])
            original_len = len(vehicles)
            vehicles = [v for v in vehicles if str(v.get("id", "")) != str(vehicle_id)]
            if len(vehicles) == original_len:
                return False
            data["vehicles"] = vehicles
            self._write_data(data)
            return True

