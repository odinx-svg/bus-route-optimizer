"""
Configuracion especifica para OSRM (Open Source Routing Machine).
"""

import os
from typing import Optional


class OSRMConfig:
    """Configuration class for OSRM integration."""
    
    BASE_URL: str = os.getenv("OSRM_BASE_URL", "http://187.77.33.218:5000")
    ROUTE_URL: str = os.getenv("OSRM_ROUTE_URL", f"{BASE_URL}/route/v1/driving")
    TABLE_URL: str = os.getenv("OSRM_TABLE_URL", f"{BASE_URL}/table/v1/driving")
    
    CACHE_ENABLED: bool = os.getenv("OSRM_CACHE_ENABLED", "true").lower() == "true"
    CACHE_FILE: str = os.getenv("OSRM_CACHE_FILE", "osrm_cache_validation.json")
    CACHE_TTL_SECONDS: int = int(os.getenv("OSRM_CACHE_TTL", "86400"))
    CACHE_MAX_SIZE: int = int(os.getenv("OSRM_CACHE_MAX_SIZE", "10000"))
    
    TIMEOUT_SECONDS: float = float(os.getenv("OSRM_TIMEOUT", "5.0"))
    MAX_RETRIES: int = int(os.getenv("OSRM_MAX_RETRIES", "3"))
    RETRY_DELAY_SECONDS: float = float(os.getenv("OSRM_RETRY_DELAY", "0.5"))
    
    RATE_LIMIT_ENABLED: bool = os.getenv("OSRM_RATE_LIMIT", "false").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_SECOND: float = float(os.getenv("OSRM_RATE_LIMIT_RPS", "10.0"))
    
    FALLBACK_ENABLED: bool = os.getenv("OSRM_FALLBACK_ENABLED", "true").lower() == "true"
    FALLBACK_SPEED_KMH: float = float(os.getenv("OSRM_FALLBACK_SPEED", "30.0"))
    
    MIN_MARGIN_MINUTES: float = float(os.getenv("OSRM_MIN_MARGIN", "5.0"))
    MAX_TRAVEL_TIME_MINUTES: float = float(os.getenv("OSRM_MAX_TRAVEL_TIME", "120.0"))

    @classmethod
    def get_route_url(cls) -> str:
        return cls.ROUTE_URL
    
    @classmethod
    def get_table_url(cls) -> str:
        return cls.TABLE_URL
    
    @classmethod
    def is_self_hosted(cls) -> bool:
        return "router.project-osrm.org" not in cls.BASE_URL
    
    @classmethod
    def get_config_dict(cls) -> dict:
        return {
            "BASE_URL": cls.BASE_URL,
            "ROUTE_URL": cls.ROUTE_URL,
            "TABLE_URL": cls.TABLE_URL,
            "CACHE_ENABLED": cls.CACHE_ENABLED,
            "CACHE_FILE": cls.CACHE_FILE,
            "CACHE_TTL_SECONDS": cls.CACHE_TTL_SECONDS,
            "TIMEOUT_SECONDS": cls.TIMEOUT_SECONDS,
            "MAX_RETRIES": cls.MAX_RETRIES,
            "FALLBACK_ENABLED": cls.FALLBACK_ENABLED,
            "FALLBACK_SPEED_KMH": cls.FALLBACK_SPEED_KMH,
            "MIN_MARGIN_MINUTES": cls.MIN_MARGIN_MINUTES,
            "IS_SELF_HOSTED": cls.is_self_hosted(),
        }


osrm_config = OSRMConfig()
