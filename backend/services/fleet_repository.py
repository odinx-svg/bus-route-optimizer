"""
Fleet repository with DB-first persistence and JSON fallback.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from db import crud as db_crud
from db.database import SessionLocal, is_database_available
from db import models as db_models
from services.fleet_registry import FleetRegistry


class FleetRepository:
    """Repository facade for fleet data."""

    def __init__(self, registry: Optional[FleetRegistry] = None) -> None:
        self.registry = registry or FleetRegistry()

    @staticmethod
    def _normalize_company_id(value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None

    @classmethod
    def _normalize_company_ids(cls, values: Optional[Iterable[str]]) -> List[str]:
        if values is None:
            return []
        normalized: List[str] = []
        for value in values:
            item = cls._normalize_company_id(value)
            if item and item not in normalized:
                normalized.append(item)
        return normalized

    @staticmethod
    def _derive_seat_fields(payload: Dict[str, Any]) -> Dict[str, int]:
        seats_base_raw = payload.get("seats_base")
        seats_pmr_raw = payload.get("seats_pmr")
        seats_min_raw = payload.get("seats_min")
        seats_max_raw = payload.get("seats_max")

        seats_base = int(seats_base_raw) if seats_base_raw is not None else 0
        seats_pmr = int(seats_pmr_raw) if seats_pmr_raw is not None else 0
        seats_min = int(seats_min_raw) if seats_min_raw is not None else 0
        seats_max = int(seats_max_raw) if seats_max_raw is not None else 0

        if seats_base <= 0:
            seats_base = max(1, seats_min or seats_max or 1)
        if seats_pmr < 0:
            seats_pmr = 0
        if seats_max <= 0:
            seats_max = max(1, seats_base + seats_pmr)
        if seats_min <= 0:
            seats_min = max(1, seats_base)
        if seats_min > seats_max:
            seats_max = seats_min
        return {
            "seats_base": seats_base,
            "seats_pmr": seats_pmr,
            "seats_min": seats_min,
            "seats_max": seats_max,
        }

    @staticmethod
    def _normalize_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for raw in documents or []:
            if not isinstance(raw, dict):
                continue
            doc_type = str(raw.get("doc_type", "") or "").strip()
            reference = str(raw.get("reference", "") or "").strip()
            issue_date = str(raw.get("issue_date", "") or "").strip() or None
            expiry_date = str(raw.get("expiry_date", "") or "").strip() or None
            notes = str(raw.get("notes", "") or "").strip() or None
            if not doc_type and not reference and not issue_date and not expiry_date:
                continue
            normalized.append(
                {
                    "id": str(raw.get("id") or uuid4()),
                    "doc_type": doc_type,
                    "reference": reference,
                    "issue_date": issue_date,
                    "expiry_date": expiry_date,
                    "notes": notes,
                }
            )
        return normalized

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return None
        return None

    @staticmethod
    def _normalize_legacy_vehicle(vehicle: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(vehicle or {})
        company_id = str(normalized.get("company_id", "") or db_crud.DEFAULT_COMPANY_ID).strip() or db_crud.DEFAULT_COMPANY_ID
        normalized["company_id"] = company_id
        seat_fields = FleetRepository._derive_seat_fields(normalized)
        normalized["seats_base"] = int(seat_fields["seats_base"])
        normalized["seats_pmr"] = int(seat_fields["seats_pmr"])
        normalized["seats_min"] = int(seat_fields["seats_min"])
        normalized["seats_max"] = int(seat_fields["seats_max"])
        last_seen = normalized.get("gps_last_seen_at")
        if isinstance(last_seen, datetime):
            normalized["gps_last_seen_at"] = last_seen.isoformat()
        normalized.setdefault("gps_provider", None)
        normalized.setdefault("gps_external_id", None)
        normalized.setdefault("gps_last_seen_at", None)
        normalized.setdefault("gps_last_position", None)
        return normalized

    @staticmethod
    def _vehicle_to_dict(model: db_models.FleetVehicleModel) -> Dict[str, Any]:
        docs = [
            {
                "id": str(doc.id),
                "doc_type": str(doc.doc_type or ""),
                "reference": str(doc.reference or ""),
                "issue_date": str(doc.issue_date or "") or None,
                "expiry_date": str(doc.expiry_date or "") or None,
                "notes": doc.notes,
            }
            for doc in (model.documents or [])
        ]
        return {
            "id": str(model.id),
            "company_id": str(model.company_id),
            "company_name": str(model.company.name or "") if model.company else None,
            "vehicle_code": str(model.vehicle_code or ""),
            "plate": str(model.plate or ""),
            "brand": model.brand,
            "model": model.model,
            "year": model.year,
            "seats_base": int(model.seats_base or model.seats_min or 0),
            "seats_pmr": int(model.seats_pmr or 0),
            "seats_min": int(model.seats_min or 0),
            "seats_max": int(model.seats_max or 0),
            "status": str(model.status or "active"),
            "fuel_type": model.fuel_type,
            "accessibility": bool(model.accessibility),
            "mileage_km": model.mileage_km,
            "notes": model.notes,
            "gps_provider": model.gps_provider,
            "gps_external_id": model.gps_external_id,
            "gps_last_seen_at": model.gps_last_seen_at.isoformat() if model.gps_last_seen_at else None,
            "gps_last_position": model.gps_last_position if isinstance(model.gps_last_position, dict) else None,
            "documents": docs,
            "created_at": model.created_at.isoformat() if model.created_at else "",
            "updated_at": model.updated_at.isoformat() if model.updated_at else "",
        }

    def _resolve_company_id(self, db, company_id: Optional[str]) -> str:
        normalized = self._normalize_company_id(company_id)
        default_company = db_crud.ensure_default_company(db)
        if not normalized:
            return str(default_company.id)
        company = db_crud.get_company(db, normalized)
        if company is None:
            return str(default_company.id)
        return str(company.id)

    def _validate_unique(self, db, *, company_id: str, payload: Dict[str, Any], exclude_id: Optional[str] = None) -> None:
        plate = str(payload.get("plate", "") or "").strip().upper()
        code = str(payload.get("vehicle_code", "") or "").strip().upper()
        query = db.query(db_models.FleetVehicleModel).filter(
            db_models.FleetVehicleModel.company_id == company_id
        )
        if exclude_id:
            query = query.filter(db_models.FleetVehicleModel.id != exclude_id)
        rows = query.all()
        for row in rows:
            row_plate = str(row.plate or "").strip().upper()
            row_code = str(row.vehicle_code or "").strip().upper()
            if plate and row_plate and plate == row_plate:
                raise ValueError(f"La matrícula '{payload.get('plate')}' ya existe")
            if code and row_code and code == row_code:
                raise ValueError(f"El código '{payload.get('vehicle_code')}' ya existe")

    def _db_available(self) -> bool:
        return bool(is_database_available() and SessionLocal is not None)

    def list_vehicles(
        self,
        company_id: Optional[str] = None,
        company_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_company_ids = self._normalize_company_ids(company_ids)
        if company_id:
            company_single = self._normalize_company_id(company_id)
            if company_single and company_single not in normalized_company_ids:
                normalized_company_ids.append(company_single)

        if not self._db_available():
            legacy = [self._normalize_legacy_vehicle(v) for v in self.registry.list_vehicles()]
            if normalized_company_ids:
                legacy = [
                    v for v in legacy
                    if str(v.get("company_id", "") or "") in normalized_company_ids
                ]
            return legacy

        db = SessionLocal()
        try:
            query = db.query(db_models.FleetVehicleModel)
            if normalized_company_ids:
                query = query.filter(db_models.FleetVehicleModel.company_id.in_(normalized_company_ids))
            elif company_id:
                resolved_company = self._resolve_company_id(db, company_id)
                query = query.filter(db_models.FleetVehicleModel.company_id == resolved_company)
            else:
                # No scope explicitly provided: return all companies (multi-company fleet view).
                pass

            rows = query.order_by(
                db_models.FleetVehicleModel.company_id.asc(),
                db_models.FleetVehicleModel.vehicle_code.asc(),
            ).all()
            return [self._vehicle_to_dict(row) for row in rows]
        finally:
            db.close()

    def get_vehicle(self, vehicle_id: str, company_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self._db_available():
            row = self.registry.get_vehicle(vehicle_id)
            if row is None:
                return None
            normalized = self._normalize_legacy_vehicle(row)
            if company_id and str(normalized.get("company_id", "") or "") != str(self._normalize_company_id(company_id) or ""):
                return None
            return normalized

        db = SessionLocal()
        try:
            row = db.query(db_models.FleetVehicleModel).filter(
                db_models.FleetVehicleModel.id == str(vehicle_id)
            ).first()
            if row is None:
                return None
            if company_id and str(row.company_id) != str(self._normalize_company_id(company_id)):
                return None
            return self._vehicle_to_dict(row)
        finally:
            db.close()

    def create_vehicle(self, payload: Dict[str, Any], company_id: Optional[str] = None) -> Dict[str, Any]:
        if not self._db_available():
            normalized = dict(payload or {})
            normalized["company_id"] = str(company_id or normalized.get("company_id") or db_crud.DEFAULT_COMPANY_ID).strip() or db_crud.DEFAULT_COMPANY_ID
            return self._normalize_legacy_vehicle(self.registry.create_vehicle(normalized))

        db = SessionLocal()
        try:
            resolved_company = self._resolve_company_id(db, company_id or payload.get("company_id"))
            self._validate_unique(db, company_id=resolved_company, payload=payload)
            now = datetime.utcnow()
            seat_fields = self._derive_seat_fields(payload)
            row = db_models.FleetVehicleModel(
                id=str(uuid4()),
                company_id=resolved_company,
                vehicle_code=str(payload.get("vehicle_code", "") or "").strip(),
                plate=str(payload.get("plate", "") or "").strip(),
                brand=str(payload.get("brand", "") or "").strip() or None,
                model=str(payload.get("model", "") or "").strip() or None,
                year=payload.get("year"),
                seats_base=int(seat_fields["seats_base"]),
                seats_pmr=int(seat_fields["seats_pmr"]),
                seats_min=int(seat_fields["seats_min"]),
                seats_max=int(seat_fields["seats_max"]),
                status=str(payload.get("status", "active") or "active"),
                fuel_type=str(payload.get("fuel_type", "") or "").strip() or None,
                accessibility=bool(payload.get("accessibility", False)),
                mileage_km=payload.get("mileage_km"),
                notes=str(payload.get("notes", "") or "").strip() or None,
                gps_provider=str(payload.get("gps_provider", "") or "").strip() or None,
                gps_external_id=str(payload.get("gps_external_id", "") or "").strip() or None,
                gps_last_seen_at=self._parse_datetime(payload.get("gps_last_seen_at")),
                gps_last_position=payload.get("gps_last_position") if isinstance(payload.get("gps_last_position"), dict) else None,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.flush()
            for doc in self._normalize_documents(payload.get("documents", [])):
                db.add(
                    db_models.FleetVehicleDocumentModel(
                        id=str(doc["id"]),
                        vehicle_id=str(row.id),
                        doc_type=str(doc["doc_type"]),
                        reference=str(doc["reference"]),
                        issue_date=doc["issue_date"],
                        expiry_date=doc["expiry_date"],
                        notes=doc["notes"],
                        created_at=now,
                        updated_at=now,
                    )
                )
            db.commit()
            db.refresh(row)
            return self._vehicle_to_dict(row)
        finally:
            db.close()

    def update_vehicle(self, vehicle_id: str, payload: Dict[str, Any], company_id: Optional[str] = None) -> Dict[str, Any]:
        if not self._db_available():
            normalized = dict(payload or {})
            if company_id:
                normalized["company_id"] = str(company_id).strip()
            updated = self.registry.update_vehicle(vehicle_id, normalized)
            return self._normalize_legacy_vehicle(updated)

        db = SessionLocal()
        try:
            row = db.query(db_models.FleetVehicleModel).filter(
                db_models.FleetVehicleModel.id == str(vehicle_id)
            ).first()
            if row is None:
                raise KeyError("Vehicle not found")
            resolved_company = self._resolve_company_id(db, company_id or payload.get("company_id") or row.company_id)
            self._validate_unique(db, company_id=resolved_company, payload=payload, exclude_id=str(vehicle_id))

            now = datetime.utcnow()
            seat_fields = self._derive_seat_fields(payload)
            row.company_id = resolved_company
            row.vehicle_code = str(payload.get("vehicle_code", "") or "").strip()
            row.plate = str(payload.get("plate", "") or "").strip()
            row.brand = str(payload.get("brand", "") or "").strip() or None
            row.model = str(payload.get("model", "") or "").strip() or None
            row.year = payload.get("year")
            row.seats_base = int(seat_fields["seats_base"])
            row.seats_pmr = int(seat_fields["seats_pmr"])
            row.seats_min = int(seat_fields["seats_min"])
            row.seats_max = int(seat_fields["seats_max"])
            row.status = str(payload.get("status", "active") or "active")
            row.fuel_type = str(payload.get("fuel_type", "") or "").strip() or None
            row.accessibility = bool(payload.get("accessibility", False))
            row.mileage_km = payload.get("mileage_km")
            row.notes = str(payload.get("notes", "") or "").strip() or None
            row.gps_provider = str(payload.get("gps_provider", "") or "").strip() or None
            row.gps_external_id = str(payload.get("gps_external_id", "") or "").strip() or None
            parsed_last_seen = self._parse_datetime(payload.get("gps_last_seen_at"))
            if parsed_last_seen is not None:
                row.gps_last_seen_at = parsed_last_seen
            if isinstance(payload.get("gps_last_position"), dict):
                row.gps_last_position = payload.get("gps_last_position")
            row.updated_at = now

            db.query(db_models.FleetVehicleDocumentModel).filter(
                db_models.FleetVehicleDocumentModel.vehicle_id == str(row.id)
            ).delete()
            for doc in self._normalize_documents(payload.get("documents", [])):
                db.add(
                    db_models.FleetVehicleDocumentModel(
                        id=str(doc["id"]),
                        vehicle_id=str(row.id),
                        doc_type=str(doc["doc_type"]),
                        reference=str(doc["reference"]),
                        issue_date=doc["issue_date"],
                        expiry_date=doc["expiry_date"],
                        notes=doc["notes"],
                        created_at=now,
                        updated_at=now,
                    )
                )
            db.commit()
            db.refresh(row)
            return self._vehicle_to_dict(row)
        finally:
            db.close()

    def delete_vehicle(self, vehicle_id: str, company_id: Optional[str] = None) -> bool:
        if not self._db_available():
            return self.registry.delete_vehicle(vehicle_id)

        db = SessionLocal()
        try:
            query = db.query(db_models.FleetVehicleModel).filter(
                db_models.FleetVehicleModel.id == str(vehicle_id)
            )
            if company_id:
                query = query.filter(
                    db_models.FleetVehicleModel.company_id == str(self._normalize_company_id(company_id))
                )
            row = query.first()
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True
        finally:
            db.close()

    def list_active_profiles(
        self,
        company_id: Optional[str] = None,
        company_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        rows = self.list_vehicles(company_id=company_id, company_ids=company_ids)
        active = [row for row in rows if str(row.get("status", "active") or "").lower() == "active"]
        active.sort(
            key=lambda row: (
                int(row.get("seats_max") or 0),
                int(row.get("seats_min") or 0),
                str(row.get("vehicle_code", "") or ""),
            )
        )
        return active

    def sync_json_fleet_into_db(self, company_id: Optional[str] = None) -> Dict[str, int]:
        """
        Best-effort import from legacy JSON file into DB (used by init script).
        """
        if not self._db_available():
            return {"imported": 0, "skipped": 0}

        db = SessionLocal()
        resolved_company = db_crud.DEFAULT_COMPANY_ID
        try:
            resolved_company = self._resolve_company_id(db, company_id)
            existing = db.query(db_models.FleetVehicleModel).filter(
                db_models.FleetVehicleModel.company_id == resolved_company
            ).count()
            if int(existing or 0) > 0:
                return {"imported": 0, "skipped": 0}
        finally:
            db.close()

        imported = 0
        skipped = 0
        for vehicle in self.registry.list_vehicles():
            payload = dict(vehicle or {})
            payload["company_id"] = str(payload.get("company_id", "") or resolved_company).strip() or resolved_company
            try:
                self.create_vehicle(payload, company_id=resolved_company)
                imported += 1
            except Exception:
                skipped += 1
        return {"imported": imported, "skipped": skipped}
