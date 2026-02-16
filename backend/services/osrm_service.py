"""
Servicio OSRM para calculo de tiempos de viaje.
"""

import asyncio
import json
import logging
import math
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx

try:
    from backend.config.osrm import osrm_config
    from backend.models.validation import Coordinates
except ImportError:
    from config.osrm import osrm_config
    from models.validation import Coordinates

logger = logging.getLogger(__name__)


@dataclass
class TravelTimeResult:
    """Resultado de calculo de tiempo de viaje."""
    minutes: float
    distance_km: Optional[float] = None
    from_cache: bool = False
    from_fallback: bool = False
    error: Optional[str] = None


class OSRMCache:
    """Cache para respuestas de OSRM."""
    
    def __init__(self, cache_file: str = None, max_size: int = None):
        self.cache_file = cache_file or osrm_config.CACHE_FILE
        self.max_size = max_size or osrm_config.CACHE_MAX_SIZE
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def _get_key(self, start: Coordinates, end: Coordinates) -> str:
        return f"{round(start.lat, 5)},{round(start.lon, 5)}|{round(end.lat, 5)},{round(end.lon, 5)}"
    
    def _load(self) -> None:
        if not osrm_config.CACHE_ENABLED:
            return
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"[OSRM Cache] Loaded {len(self._cache)} entries")
            except Exception as e:
                logger.warning(f"[OSRM Cache] Error loading: {e}")
                self._cache = {}
    
    def save(self) -> None:
        if not osrm_config.CACHE_ENABLED:
            return
        try:
            if len(self._cache) > self.max_size:
                sorted_items = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].get('timestamp', 0),
                    reverse=True
                )
                self._cache = dict(sorted_items[:self.max_size])
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f)
            logger.debug(f"[OSRM Cache] Saved {len(self._cache)} entries")
        except Exception as e:
            logger.error(f"[OSRM Cache] Error saving: {e}")
    
    def get(self, start: Coordinates, end: Coordinates) -> Optional[TravelTimeResult]:
        if not osrm_config.CACHE_ENABLED:
            return None
        key = self._get_key(start, end)
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp = entry.get('timestamp', 0)
        if time.time() - timestamp > osrm_config.CACHE_TTL_SECONDS:
            del self._cache[key]
            return None
        return TravelTimeResult(
            minutes=entry['minutes'],
            distance_km=entry.get('distance_km'),
            from_cache=True
        )
    
    def set(self, start: Coordinates, end: Coordinates, result: TravelTimeResult) -> None:
        if not osrm_config.CACHE_ENABLED:
            return
        key = self._get_key(start, end)
        self._cache[key] = {
            'minutes': result.minutes,
            'distance_km': result.distance_km,
            'timestamp': time.time()
        }
    
    def clear(self) -> None:
        self._cache.clear()
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception as e:
                logger.warning(f"[OSRM Cache] Error removing file: {e}")
    
    @property
    def size(self) -> int:
        return len(self._cache)


class OSRMService:
    """Servicio para calculo de tiempos de viaje usando OSRM."""
    
    def __init__(self):
        self.cache = OSRMCache()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(10)
        self._last_request_time = 0.0
        self._stats = {'requests': 0, 'cache_hits': 0, 'fallbacks': 0, 'errors': 0}
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=osrm_config.TIMEOUT_SECONDS,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
            )
        return self._http_client
    
    def _euclidean_distance_km(self, start: Coordinates, end: Coordinates) -> float:
        """Distancia Haversine en km."""
        R = 6371
        lat1 = math.radians(start.lat)
        lat2 = math.radians(end.lat)
        dlat = math.radians(end.lat - start.lat)
        dlon = math.radians(end.lon - start.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    
    def _fallback_travel_time(self, start: Coordinates, end: Coordinates) -> TravelTimeResult:
        """Calculo de fallback por distancia."""
        distance_km = self._euclidean_distance_km(start, end)
        speed = osrm_config.FALLBACK_SPEED_KMH
        minutes = (distance_km / speed) * 60
        self._stats['fallbacks'] += 1
        logger.debug(f"[OSRM Fallback] {distance_km:.2f}km, {minutes:.1f}min")
        return TravelTimeResult(
            minutes=minutes,
            distance_km=distance_km,
            from_fallback=True
        )
    
    async def _rate_limit(self) -> None:
        if not osrm_config.RATE_LIMIT_ENABLED:
            return
        min_interval = 1.0 / osrm_config.RATE_LIMIT_REQUESTS_PER_SECOND
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()
    
    async def get_travel_time(self, start: Coordinates, end: Coordinates) -> TravelTimeResult:
        """Obtener tiempo de viaje entre dos puntos."""
        if start.lat == 0 and start.lon == 0 or end.lat == 0 and end.lon == 0:
            return TravelTimeResult(minutes=0, error="Coordenadas invalidas")
        
        cached = self.cache.get(start, end)
        if cached:
            self._stats['cache_hits'] += 1
            return cached
        
        async with self._semaphore:
            return await self._fetch_from_osrm(start, end)
    
    async def _fetch_from_osrm(self, start: Coordinates, end: Coordinates) -> TravelTimeResult:
        url = f"{osrm_config.get_route_url()}/{start.lon},{start.lat};{end.lon},{end.lat}"
        params = {"overview": "false"}
        self._stats['requests'] += 1
        
        for attempt in range(osrm_config.MAX_RETRIES):
            try:
                await self._rate_limit()
                client = await self._get_client()
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == 'Ok' and data.get('routes'):
                        route = data['routes'][0]
                        duration = route.get('duration', 0)
                        distance = route.get('distance', 0)
                        minutes = duration / 60
                        distance_km = distance / 1000 if distance else None
                        result = TravelTimeResult(minutes=minutes, distance_km=distance_km)
                        self.cache.set(start, end, result)
                        return result
                elif response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except httpx.TimeoutException:
                logger.warning(f"[OSRM] Timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"[OSRM] Error: {e}")
                self._stats['errors'] += 1
            
            if attempt < osrm_config.MAX_RETRIES - 1:
                await asyncio.sleep(osrm_config.RETRY_DELAY_SECONDS * (attempt + 1))
        
        if osrm_config.FALLBACK_ENABLED:
            logger.warning("[OSRM] Using fallback")
            return self._fallback_travel_time(start, end)
        
        return TravelTimeResult(minutes=0, error="OSRM unavailable")
    
    async def health_check(self) -> Dict[str, Any]:
        """Verificar estado de OSRM."""
        start = time.time()
        try:
            test_start = Coordinates(lat=-33.4489, lon=-70.6693)
            test_end = Coordinates(lat=-33.4567, lon=-70.6500)
            result = await self.get_travel_time(test_start, test_end)
            response_time = (time.time() - start) * 1000
            
            if result.error:
                return {
                    'status': 'degraded' if result.from_fallback else 'unavailable',
                    'response_time_ms': response_time,
                    'cache_size': self.cache.size,
                    'base_url': osrm_config.BASE_URL,
                    'error': result.error
                }
            return {
                'status': 'healthy',
                'response_time_ms': response_time,
                'cache_size': self.cache.size,
                'base_url': osrm_config.BASE_URL,
                'error': None
            }
        except Exception as e:
            return {
                'status': 'unavailable',
                'response_time_ms': None,
                'cache_size': self.cache.size,
                'base_url': osrm_config.BASE_URL,
                'error': str(e)
            }
    
    def get_stats(self) -> Dict[str, int]:
        return self._stats.copy()
    
    def clear_cache(self) -> None:
        self.cache.clear()
        logger.info("[OSRM] Cache cleared")
    
    async def close(self) -> None:
        self.cache.save()
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


_osrm_service: Optional[OSRMService] = None


def get_osrm_service() -> OSRMService:
    global _osrm_service
    if _osrm_service is None:
        _osrm_service = OSRMService()
    return _osrm_service


async def close_osrm_service() -> None:
    global _osrm_service
    if _osrm_service:
        await _osrm_service.close()
        _osrm_service = None
