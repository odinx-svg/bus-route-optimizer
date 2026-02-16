"""
Modelos de datos adicionales para Tutti.
"""

# Re-exportar modelos del módulo models.py (el archivo, no el paquete)
# Usamos importlib para evitar conflictos con este paquete
import sys
import os
import importlib.util

# Cargar models.py directamente para evitar conflicto de nombres
_models_path = os.path.join(os.path.dirname(__file__), '..', 'models.py')
if os.path.exists(_models_path):
    _spec = importlib.util.spec_from_file_location("_base_models", _models_path)
    _base_models = importlib.util.module_from_spec(_spec)
    sys.modules["_base_models"] = _base_models
    _spec.loader.exec_module(_base_models)
    
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
