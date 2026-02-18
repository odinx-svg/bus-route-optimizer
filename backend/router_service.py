"""
Router service for OSRM (Open Source Routing Machine) integration.

Provides real travel time calculations with disk cache, short negative-cache,
and endpoint resolution suitable for desktop stable runtime.
"""

from __future__ import annotations

import json
import logging
import os
import time as time_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

DEFAULT_OSRM_BASE_URL = os.getenv("OSRM_DEFAULT_BASE_URL", "http://187.77.33.218:5000").strip()
NEGATIVE_CACHE_TTL_SEC = max(15, int(os.getenv("OSRM_NEGATIVE_CACHE_TTL_SEC", "120")))
OSRM_REQUEST_TIMEOUT = float(os.getenv("OSRM_TIMEOUT", "5.0"))


def _normalize_base_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def _derive_base_from_endpoint(url: str) -> str:
    endpoint = str(url or "").strip().rstrip("/")
    for suffix in ("/route/v1/driving", "/table/v1/driving"):
        if endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    return ""


def _resolve_osrm_endpoints() -> Tuple[str, str, str]:
    route_explicit = (os.getenv("OSRM_ROUTE_URL") or os.getenv("OSRM_URL") or "").strip()
    table_explicit = (os.getenv("OSRM_TABLE_URL") or "").strip()
    base_explicit = (os.getenv("OSRM_BASE_URL") or "").strip()

    base = _normalize_base_url(base_explicit)
    if not base and route_explicit:
        base = _normalize_base_url(_derive_base_from_endpoint(route_explicit))
    if not base and table_explicit:
        base = _normalize_base_url(_derive_base_from_endpoint(table_explicit))
    if not base:
        base = _normalize_base_url(DEFAULT_OSRM_BASE_URL)

    route_url = route_explicit or f"{base}/route/v1/driving"
    table_url = table_explicit or f"{base}/table/v1/driving"
    return base, route_url.rstrip("/"), table_url.rstrip("/")


def _resolve_cache_file() -> Path:
    explicit = (os.getenv("OSRM_CACHE_FILE") or "").strip()
    if explicit:
        path = Path(explicit).expanduser()
    else:
        tutti_data_dir = (os.getenv("TUTTI_DATA_DIR") or "").strip()
        if tutti_data_dir:
            path = Path(tutti_data_dir).expanduser() / "osrm_cache.json"
        else:
            path = Path("osrm_cache.json")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Keep working even when parent cannot be created.
        pass
    return path


OSRM_BASE_URL, OSRM_API_URL, OSRM_TABLE_URL = _resolve_osrm_endpoints()
CACHE_FILE_PATH = _resolve_cache_file()
CACHE_FILE = str(CACHE_FILE_PATH)

# Persistent cache (travel minutes by key)
_travel_time_cache: Dict[str, Optional[int]] = {}

# Negative cache: key -> expiry epoch seconds
_negative_cache: Dict[str, float] = {}

_router_metrics: Dict[str, int] = {
    "cache_hits": 0,
    "negative_cache_hits": 0,
    "http_requests": 0,
    "matrix_http_requests": 0,
    "api_errors": 0,
}


def reset_router_metrics() -> None:
    for key in list(_router_metrics.keys()):
        _router_metrics[key] = 0


def get_router_metrics() -> Dict[str, Any]:
    return {
        **_router_metrics,
        "cache_entries": len(_travel_time_cache),
        "negative_cache_entries": len(_negative_cache),
        "cache_file": str(CACHE_FILE_PATH),
        "osrm_base_url": OSRM_BASE_URL,
        "osrm_route_url": OSRM_API_URL,
        "osrm_table_url": OSRM_TABLE_URL,
    }


def _cache_get(key: str) -> Optional[int]:
    if key in _travel_time_cache:
        _router_metrics["cache_hits"] += 1
        return _travel_time_cache[key]
    return None


def _negative_key_alive(key: str) -> bool:
    expires_at = _negative_cache.get(key)
    if expires_at is None:
        return False
    now = time_module.time()
    if expires_at <= now:
        _negative_cache.pop(key, None)
        return False
    _router_metrics["negative_cache_hits"] += 1
    return True


def _mark_negative(key: str) -> None:
    _negative_cache[key] = time_module.time() + float(NEGATIVE_CACHE_TTL_SEC)


def load_cache() -> None:
    """Load OSRM cache from disk."""
    global _travel_time_cache
    if CACHE_FILE_PATH.exists():
        try:
            with CACHE_FILE_PATH.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                _travel_time_cache = loaded
                logger.info(
                    "OSRM cache loaded: %s entries from %s",
                    len(_travel_time_cache),
                    CACHE_FILE_PATH,
                )
        except Exception as exc:
            logger.warning("Error loading OSRM cache from %s: %s", CACHE_FILE_PATH, exc)


def save_cache() -> None:
    """Save OSRM cache to disk."""
    try:
        with CACHE_FILE_PATH.open("w", encoding="utf-8") as fh:
            json.dump(_travel_time_cache, fh)
    except Exception as exc:
        logger.warning("Error saving OSRM cache to %s: %s", CACHE_FILE_PATH, exc)


def _get_cache_key(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    return f"{round(lat1, 5)},{round(lon1, 5)}|{round(lat2, 5)},{round(lon2, 5)}"


def _safe_minutes_from_duration(duration_seconds: Any) -> Optional[int]:
    try:
        if duration_seconds is None:
            return None
        return max(0, int(float(duration_seconds) / 60.0))
    except Exception:
        return None


def get_real_travel_time(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> Optional[int]:
    """
    Get travel time in minutes between two points using OSRM.
    Returns None when OSRM is unavailable; caller may fallback.
    """
    if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
        return None

    key = _get_cache_key(lat1, lon1, lat2, lon2)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    neg_pair_key = f"pair:{key}"
    if _negative_key_alive(neg_pair_key):
        return None

    url = f"{OSRM_API_URL}/{lon1},{lat1};{lon2},{lat2}?overview=false"
    neg_url_key = f"url:{url}"
    if _negative_key_alive(neg_url_key):
        return None

    try:
        _router_metrics["http_requests"] += 1
        response = requests.get(url, timeout=OSRM_REQUEST_TIMEOUT)
        if response.status_code == 200:
            data: Dict[str, Any] = response.json()
            routes = data.get("routes", [])
            if data.get("code") == "Ok" and routes:
                minutes = _safe_minutes_from_duration(routes[0].get("duration"))
                if minutes is not None:
                    _travel_time_cache[key] = minutes
                    _negative_cache.pop(neg_pair_key, None)
                    _negative_cache.pop(neg_url_key, None)
                    return minutes
        _router_metrics["api_errors"] += 1
    except Exception as exc:
        _router_metrics["api_errors"] += 1
        logger.warning("OSRM route request failed: %s", exc)

    _mark_negative(neg_pair_key)
    _mark_negative(neg_url_key)
    return None


def get_route_duration(stops: List[Any]) -> Optional[int]:
    """Calculate total driving time for a stop sequence using OSRM route API."""
    if not stops or len(stops) < 2:
        return 0

    coords: List[str] = []
    for stop in stops:
        if stop.lat == 0 or stop.lon == 0:
            return None
        coords.append(f"{stop.lon},{stop.lat}")
    coord_str = ";".join(coords)

    cache_key = f"route:{coord_str}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    neg_key = f"route:{coord_str}"
    if _negative_key_alive(neg_key):
        return None

    url = f"{OSRM_API_URL}/{coord_str}?overview=false"
    neg_url_key = f"url:{url}"
    if _negative_key_alive(neg_url_key):
        return None

    try:
        _router_metrics["http_requests"] += 1
        response = requests.get(url, timeout=OSRM_REQUEST_TIMEOUT)
        if response.status_code == 200:
            data: Dict[str, Any] = response.json()
            routes = data.get("routes", [])
            if data.get("code") == "Ok" and routes:
                minutes = _safe_minutes_from_duration(routes[0].get("duration"))
                if minutes is not None:
                    _travel_time_cache[cache_key] = minutes
                    _negative_cache.pop(neg_key, None)
                    _negative_cache.pop(neg_url_key, None)
                    return minutes
        _router_metrics["api_errors"] += 1
    except Exception as exc:
        _router_metrics["api_errors"] += 1
        logger.warning("OSRM route duration request failed: %s", exc)

    _mark_negative(neg_key)
    _mark_negative(neg_url_key)
    return None


def get_travel_time_matrix(
    sources: List[Tuple[float, float]],
    destinations: List[Tuple[float, float]],
) -> List[List[Optional[int]]]:
    """
    Fetch travel-time matrix for multiple source/destination points.
    Returns minutes per pair or None where OSRM did not return a duration.
    """
    n_src = len(sources)
    n_dest = len(destinations)
    matrix: List[List[Optional[int]]] = [[None for _ in range(n_dest)] for _ in range(n_src)]

    if n_src == 0 or n_dest == 0:
        return matrix

    for i in range(n_src):
        for j in range(n_dest):
            key = _get_cache_key(
                sources[i][0],
                sources[i][1],
                destinations[j][0],
                destinations[j][1],
            )
            if key in _travel_time_cache:
                matrix[i][j] = _cache_get(key)

    missing = sum(1 for i in range(n_src) for j in range(n_dest) if matrix[i][j] is None)
    if missing == 0:
        return matrix

    is_self_hosted = "router.project-osrm.org" not in OSRM_TABLE_URL
    chunk_size = 100 if is_self_hosted else 25
    max_retries = 3
    cache_updated = False

    for i in range(0, n_src, chunk_size):
        src_chunk = sources[i : i + chunk_size]
        for j in range(0, n_dest, chunk_size):
            dest_chunk = destinations[j : j + chunk_size]

            chunk_has_missing = False
            for r in range(len(src_chunk)):
                for c in range(len(dest_chunk)):
                    if matrix[i + r][j + c] is None:
                        chunk_has_missing = True
                        break
                if chunk_has_missing:
                    break
            if not chunk_has_missing:
                continue

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
            url = (
                f"{OSRM_TABLE_URL}/{coord_str}"
                f"?sources={src_str}&destinations={dest_str}&annotations=duration"
            )
            neg_url_key = f"url:{url}"
            if _negative_key_alive(neg_url_key):
                continue

            ok = False
            effective_retries = min(max_retries, max(1, int(os.getenv("OSRM_MAX_RETRIES", str(max_retries)))))
            for retry in range(effective_retries):
                try:
                    _router_metrics["http_requests"] += 1
                    _router_metrics["matrix_http_requests"] += 1
                    timeout = min(OSRM_REQUEST_TIMEOUT * 3, 15 + retry * 10)
                    response = requests.get(url, timeout=timeout)
                    if response.status_code == 200:
                        data: Dict[str, Any] = response.json()
                        if data.get("code") == "Ok" and "durations" in data:
                            durations = data["durations"]
                            for r, row in enumerate(durations):
                                for c, duration in enumerate(row):
                                    if duration is None:
                                        continue
                                    minutes = _safe_minutes_from_duration(duration)
                                    if minutes is None:
                                        continue
                                    matrix[i + r][j + c] = minutes
                                    s_lat, s_lon = src_chunk[r]
                                    d_lat, d_lon = dest_chunk[c]
                                    key = _get_cache_key(s_lat, s_lon, d_lat, d_lon)
                                    _travel_time_cache[key] = minutes
                                    cache_updated = True
                            ok = True
                            _negative_cache.pop(neg_url_key, None)
                            break
                        _router_metrics["api_errors"] += 1
                        break
                    if response.status_code == 429 and retry < max_retries - 1:
                        time_module.sleep(2 + retry * 2)
                        continue
                    _router_metrics["api_errors"] += 1
                    break
                except Exception as exc:
                    if retry < max_retries - 1:
                        time_module.sleep(1 + retry)
                        continue
                    _router_metrics["api_errors"] += 1
                    logger.warning("OSRM matrix request failed after retries: %s", exc)
            if not ok:
                _mark_negative(neg_url_key)

            if not is_self_hosted:
                time_module.sleep(0.3)

    if cache_updated:
        save_cache()
    return matrix


load_cache()
logger.info(
    "OSRM endpoints configured | base=%s route=%s table=%s cache=%s",
    OSRM_BASE_URL,
    OSRM_API_URL,
    OSRM_TABLE_URL,
    CACHE_FILE_PATH,
)
