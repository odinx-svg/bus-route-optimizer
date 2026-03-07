"""
Contract-first telematics providers (GPS integration foundation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional


class TelematicsProvider(ABC):
    """Abstract provider for external GPS platforms."""

    provider_name: str = "abstract"

    @abstractmethod
    def test_link(self, external_vehicle_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate provider credentials + vehicle mapping."""


class DummyTelematicsProvider(TelematicsProvider):
    provider_name = "dummy"

    def test_link(self, external_vehicle_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_id = str(external_vehicle_id or "").strip()
        if not normalized_id:
            return {
                "ok": False,
                "provider": self.provider_name,
                "message": "external_vehicle_id requerido",
            }
        return {
            "ok": True,
            "provider": self.provider_name,
            "external_vehicle_id": normalized_id,
            "message": "Vinculo validado (dummy)",
            "checked_at": datetime.utcnow().isoformat(),
        }


def get_telematics_provider(provider_name: str) -> Optional[TelematicsProvider]:
    normalized = str(provider_name or "").strip().lower()
    if normalized in {"dummy", "test"}:
        return DummyTelematicsProvider()
    return None


def test_telematics_link(
    provider_name: str,
    external_vehicle_id: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    provider = get_telematics_provider(provider_name)
    if provider is None:
        return {
            "ok": False,
            "provider": provider_name,
            "message": "Proveedor no soportado en esta fase",
        }
    return provider.test_link(external_vehicle_id=external_vehicle_id, config=config)

