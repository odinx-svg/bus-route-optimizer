"""
Modelos de datos adicionales para Tutti.
"""

# Re-exportar modelos del módulo models.py (el archivo, no el paquete)
# Usamos importlib para evitar conflictos con este paquete
import sys
import os
import importlib.util

def _load_base_models_module():
    """
    Load models.py robustly across:
    - source mode
    - frozen onefile mode (PyInstaller)
    """
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models.py")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "models.py")),
        os.path.abspath(os.path.join(os.getcwd(), "models.py")),
        os.path.abspath(os.path.join(os.getcwd(), "backend", "models.py")),
    ]

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.extend(
            [
                os.path.join(meipass, "models.py"),
                os.path.join(meipass, "backend", "models.py"),
            ]
        )

    for candidate in candidates:
        if not os.path.exists(candidate):
            continue
        spec = importlib.util.spec_from_file_location("_base_models", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules["_base_models"] = module
        spec.loader.exec_module(module)
        return module
    return None


_base_models = _load_base_models_module()
if _base_models is not None:
    Stop = _base_models.Stop
    Route = _base_models.Route
    BusSchedule = _base_models.BusSchedule
    ScheduleItem = _base_models.ScheduleItem
    Bus = _base_models.Bus

# Modelos de validación
try:
    from backend.models.validation_result import (
        IssueType,
        RouteIssue,
        ValidationResult,
        ConnectionValidationResult,
        AssignedRoute,
        ValidationCacheEntry,
        ProgressiveValidationState,
        SuggestionResult,
    )
except ImportError:
    from models.validation_result import (
        IssueType,
        RouteIssue,
        ValidationResult,
        ConnectionValidationResult,
        AssignedRoute,
        ValidationCacheEntry,
        ProgressiveValidationState,
        SuggestionResult,
    )

__all__ = [
    # Modelos base (del módulo models.py)
    'Stop', 'Route', 'BusSchedule', 'ScheduleItem', 'Bus',
    # Modelos de validación
    'IssueType',
    'RouteIssue',
    'ValidationResult',
    'ConnectionValidationResult',
    'AssignedRoute',
    'ValidationCacheEntry',
    'ProgressiveValidationState',
    'SuggestionResult',
]
