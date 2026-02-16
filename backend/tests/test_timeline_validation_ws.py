"""
Tests para el WebSocket de validación de timeline.
"""

import pytest
import asyncio
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

# Importar el handler
try:
    from backend.websocket.timeline_validation_ws import (
        TimelineValidationWebSocket,
        CompatibilityQuality,
        timeline_validation_ws
    )
except ImportError:
    from websocket.timeline_validation_ws import (
        TimelineValidationWebSocket,
        CompatibilityQuality,
        timeline_validation_ws
    )


@pytest.fixture
def ws_handler():
    """Crea una instancia fresca del handler para cada test."""
    handler = TimelineValidationWebSocket()
    handler.osrm_cache.clear()
    return handler


@pytest.fixture
def mock_websocket():
    """Crea un mock de WebSocket."""
    ws = AsyncMock()
    return ws


class TestTimelineValidationWebSocket:
    """Tests para TimelineValidationWebSocket."""
    
    @pytest.mark.asyncio
    async def test_connect(self, ws_handler, mock_websocket):
        """Test de conexión inicial."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        assert "test-session-123" in ws_handler.active_connections
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_json.assert_called_once()
        
        # Verificar mensaje de conexión
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "connected"
        assert call_args["session_id"] == "test-session-123"
    
    @pytest.mark.asyncio
    async def test_disconnect(self, ws_handler, mock_websocket):
        """Test de desconexión."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        await ws_handler.disconnect("test-session-123")
        
        assert "test-session-123" not in ws_handler.active_connections
    
    def test_get_cache_key(self, ws_handler):
        """Test de generación de clave de cache."""
        key = ws_handler._get_cache_key((42.24, -8.72), (42.25, -8.73))
        assert isinstance(key, str)
        assert "|" in key
    
    def test_cache_operations(self, ws_handler):
        """Test de operaciones de cache."""
        coords_a = (42.24, -8.72)
        coords_b = (42.25, -8.73)
        
        # Cache vacío
        assert ws_handler._get_from_cache(coords_a, coords_b) is None
        
        # Guardar en cache
        ws_handler._set_cache(coords_a, coords_b, 15.5)
        
        # Recuperar del cache
        cached = ws_handler._get_from_cache(coords_a, coords_b)
        assert cached == 15.5
        assert ws_handler._stats['cache_hits'] == 1
    
    def test_cache_ttl_expiration(self, ws_handler):
        """Test de expiración de cache."""
        coords_a = (42.24, -8.72)
        coords_b = (42.25, -8.73)
        
        # Guardar en cache
        ws_handler._set_cache(coords_a, coords_b, 15.5)
        
        # Forzar expiración
        key = ws_handler._get_cache_key(coords_a, coords_b)
        ws_handler.osrm_cache[key]['timestamp'] = 0  # Muy viejo
        
        # Debe retornar None por expiración
        assert ws_handler._get_from_cache(coords_a, coords_b) is None
    
    def test_get_quality(self, ws_handler):
        """Test de cálculo de calidad."""
        assert ws_handler._get_quality(20) == CompatibilityQuality.EXCELLENT
        assert ws_handler._get_quality(12) == CompatibilityQuality.GOOD
        assert ws_handler._get_quality(7) == CompatibilityQuality.TIGHT
        assert ws_handler._get_quality(3) == CompatibilityQuality.INCOMPATIBLE
    
    def test_time_diff_minutes(self, ws_handler):
        """Test de cálculo de diferencia de tiempo."""
        assert ws_handler._time_diff_minutes("08:00", "09:00") == 60
        assert ws_handler._time_diff_minutes("08:30", "09:00") == 30
        assert ws_handler._time_diff_minutes("09:00", "08:00") == -60
    
    def test_extract_coordinates(self, ws_handler):
        """Test de extracción de coordenadas."""
        # Lista
        assert ws_handler._extract_coordinates([42.24, -8.72]) == (42.24, -8.72)
        
        # Tupla
        assert ws_handler._extract_coordinates((42.24, -8.72)) == (42.24, -8.72)
        
        # Dict con lat/lon
        assert ws_handler._extract_coordinates({"lat": 42.24, "lon": -8.72}) == (42.24, -8.72)
        
        # Dict con latitude/longitude
        assert ws_handler._extract_coordinates({"latitude": 42.24, "longitude": -8.72}) == (42.24, -8.72)
        
        # None
        assert ws_handler._extract_coordinates(None) is None
    
    def test_fallback_travel_time(self, ws_handler):
        """Test de cálculo de fallback."""
        # Coordenadas cercanas (menos de 1 km)
        time1 = ws_handler._fallback_travel_time((42.24, -8.72), (42.2401, -8.7201))
        assert time1 > 0
        assert time1 < 5  # Debe ser muy corto
        
        # Coordenadas más lejanas
        time2 = ws_handler._fallback_travel_time((42.24, -8.72), (42.26, -8.74))
        assert time2 > time1
    
    @pytest.mark.asyncio
    async def test_handle_check_compatibility_success(self, ws_handler, mock_websocket):
        """Test de validación de compatibilidad exitosa."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        # Mock del servicio OSRM
        mock_result = MagicMock()
        mock_result.minutes = 15.5
        mock_result.error = None
        mock_result.from_fallback = False
        
        with patch('services.osrm_service.get_osrm_service') as mock_service:
            mock_service.return_value.get_travel_time = AsyncMock(return_value=mock_result)
            
            message = {
                "type": "check_compatibility",
                "request_id": "req-123",
                "route_a": {
                    "endCoordinates": [42.24, -8.72],
                    "endTime": "08:00"
                },
                "route_b": {
                    "startCoordinates": [42.25, -8.73],
                    "startTime": "09:00"
                }
            }
            
            await ws_handler._handle_check_compatibility(
                mock_websocket, "test-session-123", message
            )
            
            # Verificar respuesta
            calls = mock_websocket.send_json.call_args_list
            
            # Primera llamada debe ser "validating"
            assert calls[-2][0][0]["type"] == "validating"
            
            # Segunda llamada debe ser "compatibility_result"
            result = calls[-1][0][0]
            assert result["type"] == "compatibility_result"
            assert result["request_id"] == "req-123"
            assert result["is_compatible"] == True  # 60 - 15.5 > 5
            assert result["travel_time_minutes"] == 15.5
            assert result["buffer_minutes"] == 44.5
            assert result["time_available"] == 60
            assert result["quality"] == "excellent"
    
    @pytest.mark.asyncio
    async def test_handle_check_compatibility_incompatible(self, ws_handler, mock_websocket):
        """Test de validación de compatibilidad incompatible."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        mock_result = MagicMock()
        mock_result.minutes = 10.0
        mock_result.error = None
        mock_result.from_fallback = False
        
        with patch('services.osrm_service.get_osrm_service') as mock_service:
            mock_service.return_value.get_travel_time = AsyncMock(return_value=mock_result)
            
            message = {
                "type": "check_compatibility",
                "request_id": "req-124",
                "route_a": {
                    "endCoordinates": [42.24, -8.72],
                    "endTime": "08:00"
                },
                "route_b": {
                    "startCoordinates": [42.25, -8.73],
                    "startTime": "08:10"  # Solo 10 minutos disponibles
                }
            }
            
            await ws_handler._handle_check_compatibility(
                mock_websocket, "test-session-123", message
            )
            
            result = mock_websocket.send_json.call_args_list[-1][0][0]
            assert result["is_compatible"] == False  # 10 - 10 = 0 < 5
            assert result["buffer_minutes"] == 0
            assert result["quality"] == "incompatible"
    
    @pytest.mark.asyncio
    async def test_handle_check_compatibility_fallback(self, ws_handler, mock_websocket):
        """Test de validación con fallback."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        mock_result = MagicMock()
        mock_result.minutes = 12.0
        mock_result.error = "OSRM timeout"
        mock_result.from_fallback = True
        
        with patch('services.osrm_service.get_osrm_service') as mock_service:
            mock_service.return_value.get_travel_time = AsyncMock(return_value=mock_result)
            
            message = {
                "type": "check_compatibility",
                "request_id": "req-125",
                "route_a": {
                    "endCoordinates": [42.24, -8.72],
                    "endTime": "08:00"
                },
                "route_b": {
                    "startCoordinates": [42.25, -8.73],
                    "startTime": "09:00"
                }
            }
            
            await ws_handler._handle_check_compatibility(
                mock_websocket, "test-session-123", message
            )
            
            result = mock_websocket.send_json.call_args_list[-1][0][0]
            assert result["from_fallback"] == True
            assert "warning" in result
    
    @pytest.mark.asyncio
    async def test_handle_get_suggestions(self, ws_handler, mock_websocket):
        """Test de obtención de sugerencias."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        # Mock de _calculate_position_score para evitar complejidad
        with patch.object(ws_handler, '_calculate_position_score', return_value=(85, ["Buena posición"])):
            message = {
                "type": "get_suggestions",
                "request_id": "req-126",
                "route": {
                    "startCoordinates": [42.24, -8.72],
                    "endCoordinates": [42.25, -8.73],
                    "startTime": "09:00",
                    "endTime": "09:30"
                },
                "buses": [
                    {
                        "busId": "B1",
                        "routes": [
                            {
                                "startCoordinates": [42.23, -8.71],
                                "endCoordinates": [42.24, -8.72],
                                "startTime": "08:00",
                                "endTime": "08:45"
                            }
                        ]
                    },
                    {
                        "busId": "B2",
                        "routes": []
                    }
                ]
            }
            
            await ws_handler._handle_get_suggestions(
                mock_websocket, "test-session-123", message
            )
            
            result = mock_websocket.send_json.call_args_list[-1][0][0]
            assert result["type"] == "suggestions"
            assert result["request_id"] == "req-126"
            assert "suggestions" in result
            assert len(result["suggestions"]) > 0
    
    @pytest.mark.asyncio
    async def test_handle_batch_validate(self, ws_handler, mock_websocket):
        """Test de validación batch."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        # Mock _get_travel_time_from_osrm para evitar llamadas reales
        with patch.object(ws_handler, '_get_travel_time_from_osrm', new_callable=AsyncMock, return_value=(10.0, False, None)):
            message = {
                "type": "batch_validate",
                "request_id": "req-127",
                "pairs": [
                    {
                        "id": "pair-1",
                        "route_a": {
                            "endCoordinates": [42.24, -8.72],
                            "endTime": "08:00"
                        },
                        "route_b": {
                            "startCoordinates": [42.25, -8.73],
                            "startTime": "09:00"
                        }
                    }
                ]
            }
            
            await ws_handler._handle_batch_validate(
                mock_websocket, "test-session-123", message
            )
            
            result = mock_websocket.send_json.call_args_list[-1][0][0]
            assert result["type"] == "batch_results"
            assert result["request_id"] == "req-127"
            assert len(result["results"]) == 1
            assert result["results"][0]["id"] == "pair-1"
    
    @pytest.mark.asyncio
    async def test_handle_message_ping(self, ws_handler, mock_websocket):
        """Test de mensaje ping."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        message = {"type": "ping"}
        await ws_handler.handle_message(mock_websocket, "test-session-123", message)
        
        result = mock_websocket.send_json.call_args_list[-1][0][0]
        assert result["type"] == "pong"
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_handle_message_unknown_type(self, ws_handler, mock_websocket):
        """Test de mensaje con tipo desconocido."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        message = {"type": "unknown_type"}
        await ws_handler.handle_message(mock_websocket, "test-session-123", message)
        
        result = mock_websocket.send_json.call_args_list[-1][0][0]
        assert result["type"] == "error"
        assert "unknown" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_handle_check_compatibility_missing_params(self, ws_handler, mock_websocket):
        """Test de validación con parámetros faltantes."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        message = {
            "type": "check_compatibility",
            "request_id": "req-128"
            # Falta route_a y route_b
        }
        
        await ws_handler._handle_check_compatibility(
            mock_websocket, "test-session-123", message
        )
        
        result = mock_websocket.send_json.call_args_list[-1][0][0]
        assert result["type"] == "error"
    
    def test_get_stats(self, ws_handler):
        """Test de obtención de estadísticas."""
        stats = ws_handler.get_stats()
        
        assert "validations" in stats
        assert "cache_hits" in stats
        assert "osrm_calls" in stats
        assert "fallbacks" in stats
        assert "errors" in stats
        assert "cache_size" in stats
        assert "active_connections" in stats


class TestCalculatePositionScore:
    """Tests específicos para el cálculo de score de posición."""
    
    @pytest.fixture
    def ws_handler(self):
        return TimelineValidationWebSocket()
    
    @pytest.mark.asyncio
    async def test_empty_bus(self, ws_handler):
        """Test de score para bus vacío."""
        route = {
            "startCoordinates": [42.24, -8.72],
            "endCoordinates": [42.25, -8.73],
            "startTime": "09:00",
            "endTime": "09:30"
        }
        
        score, reasons = await ws_handler._calculate_position_score(route, [], 0)
        
        # Debe tener buen score por bus vacío
        assert score > 80
        assert any("baja carga" in r.lower() for r in reasons)
    
    @pytest.mark.asyncio
    async def test_compatible_position(self, ws_handler):
        """Test de score para posición compatible."""
        with patch.object(ws_handler, '_get_travel_time_from_osrm', new_callable=AsyncMock, return_value=(10.0, False, None)):
            route = {
                "startCoordinates": [42.24, -8.72],
                "endCoordinates": [42.25, -8.73],
                "startTime": "09:00",
                "endTime": "09:30"
            }
            bus_routes = [
                {
                    "endCoordinates": [42.23, -8.71],
                    "endTime": "08:45"  # 15 minutos de margen
                }
            ]
            
            score, reasons = await ws_handler._calculate_position_score(route, bus_routes, 1)
            
            assert score > 70
            assert any("Buen margen" in r for r in reasons)
    
    @pytest.mark.asyncio
    async def test_incompatible_position(self, ws_handler):
        """Test de score para posición incompatible."""
        # Probar en posición 0 con conflicto con la siguiente ruta
        with patch.object(ws_handler, '_get_travel_time_from_osrm', new_callable=AsyncMock, return_value=(10.0, False, None)):
            route = {
                "startCoordinates": [42.24, -8.72],
                "endCoordinates": [42.25, -8.73],
                "startTime": "08:00",
                "endTime": "09:30"  # Termina tarde
            }
            bus_routes = [
                {
                    "startCoordinates": [42.26, -8.74],
                    "startTime": "09:00",  # Empieza antes de que termine la primera
                    "endTime": "10:00"
                }
            ]
            
            # Position 0: la nueva ruta va ANTES de bus_routes[0]
            score, reasons = await ws_handler._calculate_position_score(route, bus_routes, 0)
            
            # El score debe reflejar que hay problemas con la siguiente ruta
            assert score < 100
            assert len(reasons) > 0


class TestCacheBehavior:
    """Tests de comportamiento del cache."""
    
    @pytest.fixture
    def ws_handler(self):
        return TimelineValidationWebSocket()
    
    @pytest.mark.asyncio
    async def test_osrm_not_called_when_cached(self, ws_handler, mock_websocket):
        """Test de que OSRM no se llama cuando hay cache."""
        await ws_handler.connect(mock_websocket, "test-session-123")
        
        coords_a = (42.24, -8.72)
        coords_b = (42.25, -8.73)
        
        # Pre-poblar cache
        ws_handler._set_cache(coords_a, coords_b, 15.0)
        
        mock_result = MagicMock()
        mock_result.minutes = 15.0
        mock_result.error = None
        mock_result.from_fallback = False
        
        with patch('services.osrm_service.get_osrm_service') as mock_service:
            mock_service.return_value.get_travel_time = AsyncMock(return_value=mock_result)
            
            message = {
                "type": "check_compatibility",
                "request_id": "req-cache-test",
                "route_a": {
                    "endCoordinates": list(coords_a),
                    "endTime": "08:00"
                },
                "route_b": {
                    "startCoordinates": list(coords_b),
                    "startTime": "09:00"
                }
            }
            
            await ws_handler._handle_check_compatibility(
                mock_websocket, "test-session-123", message
            )
            
            # OSRM no debe ser llamado porque hay cache
            mock_service.return_value.get_travel_time.assert_not_called()
            
            # Verificar que se usó el cache
            assert ws_handler._stats['cache_hits'] == 1
    
    def test_clear_expired_cache(self, ws_handler):
        """Test de limpieza de cache expirado."""
        coords_a = (42.24, -8.72)
        coords_b = (42.25, -8.73)
        
        # Guardar con timestamp viejo
        key = ws_handler._get_cache_key(coords_a, coords_b)
        ws_handler.osrm_cache[key] = {
            'travel_time': 15.0,
            'timestamp': 0  # Expirado
        }
        
        # Limpiar expirados
        ws_handler._clear_expired_cache()
        
        # Debe estar vacío
        assert key not in ws_handler.osrm_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
