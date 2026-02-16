"""
Router service for OSRM (Open Source Routing Machine) integration.

Provides real travel time calculations using OSRM API with local caching.
"""

import logging
import requests
import math
import json
import os
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

OSRM_API_URL: str = os.getenv('OSRM_URL', 'https://router.project-osrm.org/route/v1/driving')
OSRM_TABLE_URL: str = os.getenv('OSRM_TABLE_URL', 'https://router.project-osrm.org/table/v1/driving')
CACHE_FILE: str = 'osrm_cache.json'

# Persistent Cache
_travel_time_cache: Dict[str, Optional[int]] = {}


def load_cache() -> None:
    """Load OSRM cache from disk."""
    global _travel_time_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                # Keys in JSON are strings, convert back to tuple if needed or keep string
                # Simpler: use string keys "lat1,lon1|lat2,lon2"
                _travel_time_cache = json.load(f)
                logger.debug(f"Loaded {len(_travel_time_cache)} entries from OSRM cache.")
        except Exception as e:
            print(f"Error loading OSRM cache: {e}")


def save_cache() -> None:
    """Save OSRM cache to disk."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_travel_time_cache, f)
    except Exception as e:
        print(f"Error saving OSRM cache: {e}")


def _get_cache_key(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Generate cache key for two coordinates."""
    return f"{round(lat1, 5)},{round(lon1, 5)}|{round(lat2, 5)},{round(lon2, 5)}"


def get_real_travel_time(
    lat1: float, 
    lon1: float, 
    lat2: float, 
    lon2: float
) -> Optional[int]:
    """
    Get travel time in minutes between two points using OSRM.
    
    Args:
        lat1: Origin latitude
        lon1: Origin longitude
        lat2: Destination latitude
        lon2: Destination longitude
        
    Returns:
        Travel time in minutes, or None if API fails
    """
    if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
        return None

    key = _get_cache_key(lat1, lon1, lat2, lon2)
    if key in _travel_time_cache:
        return _travel_time_cache[key]

    try:
        # Format: lon,lat;lon,lat
        url = f"{OSRM_API_URL}/{lon1},{lat1};{lon2},{lat2}?overview=false"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data: Dict[str, Any] = response.json()
            routes = data.get('routes', [])
            if data.get('code') == 'Ok' and routes and len(routes) > 0:
                duration_seconds = routes[0].get('duration')
                if duration_seconds is not None:
                    minutes = int(duration_seconds / 60)
                    _travel_time_cache[key] = minutes
                    return minutes
    except Exception as e:
        print(f"OSRM API Error: {e}")
    
    return None


def get_route_duration(stops: List[Any]) -> Optional[int]:
    """
    Calculates total driving time for a sequence of stops using OSRM.
    
    Args:
        stops: List of stop objects with .lat and .lon attributes
        
    Returns:
        Total minutes or None if failed
    """
    if not stops or len(stops) < 2:
        return 0
        
    # Extract coords
    coords: List[str] = []
    for s in stops:
        if s.lat == 0 or s.lon == 0:
            # Return None to trigger Haversine fallback in optimizer.
            return None
        coords.append(f"{s.lon},{s.lat}")
        
    # OSRM URL limit? usually 100, routes are typically small (< 20 stops)
    coord_str = ";".join(coords)
    
    # Check Cache
    if coord_str in _travel_time_cache:
        return _travel_time_cache[coord_str]

    url = f"{OSRM_API_URL}/{coord_str}?overview=false"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data: Dict[str, Any] = response.json()
            if data['code'] == 'Ok' and data['routes']:
                duration_seconds = data['routes'][0]['duration']
                minutes = int(duration_seconds / 60)
                _travel_time_cache[coord_str] = minutes
                return minutes
    except Exception as e:
        print(f"OSRM Route API Error: {e}")
        
    return None


def get_travel_time_matrix(
    sources: List[Tuple[float, float]], 
    destinations: List[Tuple[float, float]]
) -> List[List[Optional[int]]]:
    """
    Fetch travel time matrix for multiple sources and destinations.
    
    Handles chunking to respect OSRM limits (100 coords per request).
    
    Args:
        sources: List of (lat, lon) tuples for source points
        destinations: List of (lat, lon) tuples for destination points
        
    Returns:
        2D list where result[i][j] is time from sources[i] to destinations[j]
    """
    import time as _time

    n_src = len(sources)
    n_dest = len(destinations)

    # Initialize result matrix with None
    matrix: List[List[Optional[int]]] = [[None for _ in range(n_dest)] for _ in range(n_src)]

    # Fill from cache first
    cache_hits = 0
    for i in range(n_src):
        for j in range(n_dest):
            key = _get_cache_key(sources[i][0], sources[i][1], destinations[j][0], destinations[j][1])
            if key in _travel_time_cache:
                matrix[i][j] = _travel_time_cache[key]
                cache_hits += 1

    if cache_hits > 0:
        print(f"  OSRM cache: {cache_hits}/{n_src * n_dest} pairs from cache")

    # Check if we need to fetch anything
    missing = sum(1 for i in range(n_src) for j in range(n_dest) if matrix[i][j] is None)
    if missing == 0:
        return matrix

    # Chunk size - larger for self-hosted OSRM, smaller for public
    is_self_hosted = 'router.project-osrm.org' not in OSRM_TABLE_URL
    CHUNK_SIZE = 100 if is_self_hosted else 25
    MAX_RETRIES = 3

    # Track if we modified cache
    cache_updated = False

    for i in range(0, n_src, CHUNK_SIZE):
        src_chunk = sources[i:i + CHUNK_SIZE]

        for j in range(0, n_dest, CHUNK_SIZE):
            dest_chunk = destinations[j:j + CHUNK_SIZE]

            # Skip if all pairs in this chunk are cached
            chunk_missing = False
            for r in range(len(src_chunk)):
                for c in range(len(dest_chunk)):
                    if matrix[i + r][j + c] is None:
                        chunk_missing = True
                        break
                if chunk_missing:
                    break
            if not chunk_missing:
                continue

            # Prepare request
            all_coords: List[str] = []
            src_indices: List[str] = []
            dest_indices: List[str] = []

            idx = 0
            for lat, lon in src_chunk:
                all_coords.append(f"{lon},{lat}")
                src_indices.append(str(idx))
                idx += 1

            for lat, lon in dest_chunk:
                all_coords.append(f"{lon},{lat}")
                dest_indices.append(str(idx))
                idx += 1

            coord_str = ";".join(all_coords)
            src_str = ";".join(src_indices)
            dest_str = ";".join(dest_indices)

            url = f"{OSRM_TABLE_URL}/{coord_str}?sources={src_str}&destinations={dest_str}&annotations=duration"

            for retry in range(MAX_RETRIES):
                try:
                    timeout = 15 + retry * 10  # 15s, 25s, 35s
                    response = requests.get(url, timeout=timeout)

                    if response.status_code == 200:
                        data: Dict[str, Any] = response.json()
                        if data['code'] == 'Ok' and 'durations' in data:
                            durations = data['durations']
                            for r, row in enumerate(durations):
                                for c, duration in enumerate(row):
                                    if duration is not None:
                                        minutes = int(duration / 60)
                                        matrix[i + r][j + c] = minutes

                                        s_lat, s_lon = src_chunk[r]
                                        d_lat, d_lon = dest_chunk[c]
                                        key = _get_cache_key(s_lat, s_lon, d_lat, d_lon)
                                        _travel_time_cache[key] = minutes
                                        cache_updated = True
                            break  # Success, exit retry loop
                        else:
                            print(f"OSRM Table Error: {data.get('code')}")
                            break
                    elif response.status_code == 429:
                        # Rate limited, wait and retry
                        _time.sleep(2 + retry * 2)
                        continue
                    else:
                        print(f"OSRM HTTP Error: {response.status_code}")
                        break

                except Exception as e:
                    if retry < MAX_RETRIES - 1:
                        _time.sleep(1 + retry)
                        continue
                    print(f"OSRM Matrix Exception (after {MAX_RETRIES} retries): {e}")

            # Small delay between chunks for public OSRM only
            if not is_self_hosted:
                _time.sleep(0.3)

    if cache_updated:
        save_cache()

    return matrix


# Load on module import
load_cache()
