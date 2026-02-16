"""
Configuration module for Tutti backend.

Centralizes all configuration settings including feature flags,
database URLs, and external service configurations.
"""

import os
from typing import Optional, Dict, Any


class ObjectivePresets:
    """Presets predefinidos para diferentes escenarios de optimización multi-objetivo."""
    
    @staticmethod
    def minimize_buses() -> Dict[str, float]:
        """Preset para minimizar principalmente el número de buses."""
        return {
            "buses": 1000,
            "deadhead_km": 10,
            "driver_overtime": 50,
            "time_shift_minutes": 5,
            "unbalanced_load": 10,
            "fuel_cost": 0.1,
            "co2_emissions": 0.005
        }
    
    @staticmethod
    def minimize_cost() -> Dict[str, float]:
        """Preset para minimizar costos operacionales."""
        return {
            "buses": 500,
            "deadhead_km": 20,
            "driver_overtime": 100,
            "time_shift_minutes": 2,
            "fuel_cost": 0.25,
            "unbalanced_load": 15,
            "co2_emissions": 0.005
        }
    
    @staticmethod
    def minimize_emissions() -> Dict[str, float]:
        """Preset para minimizar emisiones de CO2."""
        return {
            "buses": 800,
            "deadhead_km": 30,
            "driver_overtime": 50,
            "time_shift_minutes": 5,
            "unbalanced_load": 10,
            "fuel_cost": 0.1,
            "co2_emissions": 0.05
        }
    
    @staticmethod
    def balanced() -> Dict[str, float]:
        """Preset balanceado (default)."""
        return {
            "buses": 1000.0,
            "deadhead_km": 10.0,
            "driver_overtime": 50.0,
            "time_shift_minutes": 5.0,
            "unbalanced_load": 20.0,
            "fuel_cost": 0.15,
            "co2_emissions": 0.01
        }
    
    @staticmethod
    def get_preset(name: str) -> Dict[str, float]:
        """Obtener preset por nombre."""
        presets = {
            "minimize_buses": ObjectivePresets.minimize_buses(),
            "minimize_cost": ObjectivePresets.minimize_cost(),
            "minimize_emissions": ObjectivePresets.minimize_emissions(),
            "balanced": ObjectivePresets.balanced(),
        }
        return presets.get(name, ObjectivePresets.balanced())


class Config:
    """Application configuration loaded from environment variables."""
    
    # Feature Flags
    CELERY_ENABLED: bool = os.getenv("CELERY_ENABLED", "true").lower() == "true"
    WEBSOCKET_ENABLED: bool = os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true"
    USE_DATABASE: bool = os.getenv("USE_DATABASE", "true").lower() == "true"
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://tutti:tutti@localhost:5432/tutti"
    )
    SQLALCHEMY_ECHO: bool = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
    
    # OSRM Configuration
    OSRM_URL: str = os.getenv(
        "OSRM_URL", 
        "http://187.77.33.218:5000/route/v1/driving"
    )
    OSRM_TABLE_URL: str = os.getenv(
        "OSRM_TABLE_URL", 
        "http://187.77.33.218:5000/table/v1/driving"
    )
    
    # WebSocket Configuration
    WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    WS_PING_TIMEOUT: int = int(os.getenv("WS_PING_TIMEOUT", "10"))
    
    # Celery Configuration
    CELERY_TASK_TIME_LIMIT: int = int(os.getenv("CELERY_TASK_TIME_LIMIT", "3600"))
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = int(
        os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1")
    )
    
    # Optimization Configuration
    OPTIMIZER_PROGRESS_INTERVAL: float = float(
        os.getenv("OPTIMIZER_PROGRESS_INTERVAL", "1.0")
    )
    APP_RUNTIME_MODE: str = os.getenv("APP_RUNTIME_MODE", "stable").strip().lower() or "stable"
    
    @classmethod
    def is_celery_available(cls) -> bool:
        """Check if Celery is enabled and properly configured."""
        if not cls.CELERY_ENABLED:
            return False
        try:
            from celery import Celery
            return True
        except ImportError:
            return False
    
    @classmethod
    def is_redis_available(cls) -> bool:
        """Check if Redis is accessible."""
        try:
            import redis
            client = redis.Redis.from_url(cls.REDIS_URL, socket_connect_timeout=2)
            client.ping()
            return True
        except Exception:
            return False
    
    @classmethod
    def get_config_dict(cls) -> dict:
        """Return configuration as dictionary (for debugging)."""
        return {
            "CELERY_ENABLED": cls.CELERY_ENABLED,
            "WEBSOCKET_ENABLED": cls.WEBSOCKET_ENABLED,
            "USE_DATABASE": cls.USE_DATABASE,
            "REDIS_URL": cls.REDIS_URL.replace("//", "//***@") if "@" in cls.REDIS_URL else cls.REDIS_URL,
            "DATABASE_URL": cls.DATABASE_URL.replace("//", "//***@") if "@" in cls.DATABASE_URL else cls.DATABASE_URL,
            "OSRM_URL": cls.OSRM_URL,
            "APP_RUNTIME_MODE": cls.APP_RUNTIME_MODE,
        }


# Global configuration instance
config = Config()
