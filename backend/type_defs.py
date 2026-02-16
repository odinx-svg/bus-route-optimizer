"""
Type definitions for Tutti backend.

This module contains type aliases and custom types used across the backend.
"""

from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import time

# =============================================================================
# Basic type aliases
# =============================================================================

# Coordinates as (lat, lon) tuples
Coordinates = Tuple[float, float]

# Time in minutes since midnight
Minutes = int

# Travel time matrix: {(source_idx, dest_idx): minutes}
TravelTimeMatrix = Dict[Tuple[int, int], int]

# Feasibility matrix: {(source_idx, dest_idx): bool}
FeasibilityMatrix = Dict[Tuple[int, int], bool]

# =============================================================================
# Parser types
# =============================================================================

# Excel cell value types
CellValue = Union[str, float, int, time, None]

# Column mapping from Excel
ColumnMapping = Dict[str, Optional[str]]

# =============================================================================
# Optimizer types
# =============================================================================

# Chain of route indices
RouteChain = List[int]

# Block number (1-4)
BlockNumber = int

# =============================================================================
# Router service types
# =============================================================================

# OSRM cache key format: "lat1,lon1|lat2,lon2"
CacheKey = str

# OSRM cache storage
TravelTimeCache = Dict[str, Optional[int]]

# =============================================================================
# PDF service types
# =============================================================================

# Schedule item dictionary (for PDF generation)
ScheduleItemDict = Dict[str, Any]

# Bus schedule dictionary (for PDF generation)
BusScheduleDict = Dict[str, Any]

# =============================================================================
# API types
# =============================================================================

# Response dictionary
APIResponse = Dict[str, Any]

# Stats dictionary
StatsDict = Dict[str, Union[int, float]]
