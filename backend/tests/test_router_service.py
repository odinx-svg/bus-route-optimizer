"""
Tests for router service module.
Uses mocks to avoid actual OSRM API calls.
"""
import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock

import router_service as _rs
from router_service import (
    load_cache,
    save_cache,
    get_real_travel_time,
    get_route_duration,
    get_travel_time_matrix,
    _get_cache_key
)


@pytest.fixture(autouse=True)
def _clean_router_state():
    """Reset travel-time cache and negative cache between every test."""
    _rs._travel_time_cache.clear()
    _rs._negative_cache.clear()
    yield
    _rs._travel_time_cache.clear()
    _rs._negative_cache.clear()


# ============================================================
# CACHE TESTS
# ============================================================

class TestCache:
    """Test suite for cache functionality."""
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_load_cache_exists(self, mock_json_load, mock_file, mock_exists):
        """Test loading cache when file exists."""
        mock_exists.return_value = True
        mock_json_load.return_value = {"key1": 10, "key2": 20}
        
        # Import after patching
        import router_service
        router_service._travel_time_cache = {}
        router_service.load_cache()
        
        assert router_service._travel_time_cache == {"key1": 10, "key2": 20}
    
    @patch('pathlib.Path.exists', return_value=False)
    def test_load_cache_not_exists(self, mock_exists):
        """Test loading cache when file doesn't exist."""
        import router_service
        router_service._travel_time_cache = {}
        router_service.load_cache()

        assert router_service._travel_time_cache == {}
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_cache(self, mock_json_dump, mock_file):
        """Test saving cache."""
        import router_service
        router_service._travel_time_cache = {"key1": 10}
        
        router_service.save_cache()
        
        mock_json_dump.assert_called_once()
    
    def test_get_cache_key(self):
        """Test cache key generation."""
        key = _get_cache_key(42.2406, -8.7207, 42.2500, -8.7300)
        assert isinstance(key, str)
        assert "42.2406" in key
        assert "-8.7207" in key
        assert "|" in key


# ============================================================
# TRAVEL TIME TESTS
# ============================================================

class TestTravelTime:
    """Test suite for travel time functions."""
    
    def test_get_real_travel_time_zero_coords(self):
        """Test travel time with zero coordinates."""
        result = get_real_travel_time(0, 0, 42.24, -8.72)
        assert result is None
    
    def test_get_real_travel_time_from_cache(self):
        """Test travel time from cache."""
        import router_service
        key = _get_cache_key(42.24, -8.72, 42.25, -8.73)
        router_service._travel_time_cache[key] = 15
        
        result = get_real_travel_time(42.24, -8.72, 42.25, -8.73)
        assert result == 15
    
    @patch('router_service.requests.get')
    def test_get_real_travel_time_api_success(self, mock_get):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 'Ok',
            'routes': [{'duration': 900}]  # 15 minutes
        }
        mock_get.return_value = mock_response
        
        # Clear cache first
        import router_service
        router_service._travel_time_cache = {}
        
        result = get_real_travel_time(42.24, -8.72, 42.25, -8.73)
        assert result == 15
    
    @patch('router_service.requests.get')
    def test_get_real_travel_time_api_error(self, mock_get):
        """Test API error handling."""
        mock_get.side_effect = Exception("Connection error")
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        result = get_real_travel_time(42.24, -8.72, 42.25, -8.73)
        assert result is None
    
    @patch('router_service.requests.get')
    def test_get_real_travel_time_api_not_ok(self, mock_get):
        """Test API response not OK."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 'Error',
            'routes': []
        }
        mock_get.return_value = mock_response
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        result = get_real_travel_time(42.24, -8.72, 42.25, -8.73)
        assert result is None
    
    @patch('router_service.requests.get')
    def test_get_real_travel_time_api_404(self, mock_get):
        """Test API 404 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        result = get_real_travel_time(42.24, -8.72, 42.25, -8.73)
        assert result is None


# ============================================================
# ROUTE DURATION TESTS
# ============================================================

class TestRouteDuration:
    """Test suite for route duration calculation."""
    
    def test_get_route_duration_empty(self):
        """Test duration for empty stops."""
        result = get_route_duration([])
        assert result == 0
    
    def test_get_route_duration_single_stop(self):
        """Test duration for single stop."""
        stop = MagicMock()
        stop.lat = 42.24
        stop.lon = -8.72
        result = get_route_duration([stop])
        assert result == 0
    
    def test_get_route_duration_zero_coords(self):
        """Test duration with zero coordinates."""
        stop1 = MagicMock()
        stop1.lat = 0
        stop1.lon = 0
        stop2 = MagicMock()
        stop2.lat = 42.24
        stop2.lon = -8.72
        
        result = get_route_duration([stop1, stop2])
        assert result is None
    
    @patch('router_service.requests.get')
    def test_get_route_duration_success(self, mock_get):
        """Test successful route duration calculation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 'Ok',
            'routes': [{'duration': 1200}]  # 20 minutes
        }
        mock_get.return_value = mock_response
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        stop1 = MagicMock()
        stop1.lat = 42.24
        stop1.lon = -8.72
        stop2 = MagicMock()
        stop2.lat = 42.25
        stop2.lon = -8.73
        
        result = get_route_duration([stop1, stop2])
        assert result == 20
    
    @patch('router_service.requests.get')
    def test_get_route_duration_api_error(self, mock_get):
        """Test route duration API error."""
        mock_get.side_effect = Exception("API Error")
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        stop1 = MagicMock()
        stop1.lat = 42.24
        stop1.lon = -8.72
        stop2 = MagicMock()
        stop2.lat = 42.25
        stop2.lon = -8.73
        
        result = get_route_duration([stop1, stop2])
        assert result is None


# ============================================================
# TRAVEL TIME MATRIX TESTS
# ============================================================

class TestTravelTimeMatrix:
    """Test suite for travel time matrix."""
    
    def test_get_travel_time_matrix_empty(self):
        """Test matrix with empty inputs."""
        result = get_travel_time_matrix([], [])
        assert result == []
    
    def test_get_travel_time_matrix_from_cache(self):
        """Test matrix from cache."""
        import router_service
        # Pre-populate cache
        key1 = _get_cache_key(42.24, -8.72, 42.25, -8.73)
        router_service._travel_time_cache[key1] = 10
        
        sources = [(42.24, -8.72)]
        destinations = [(42.25, -8.73)]
        
        result = get_travel_time_matrix(sources, destinations)
        assert result == [[10]]
    
    @patch('router_service.requests.get')
    def test_get_travel_time_matrix_success(self, mock_get):
        """Test successful matrix calculation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 'Ok',
            'durations': [[600]]  # 10 minutes
        }
        mock_get.return_value = mock_response
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        sources = [(42.24, -8.72)]
        destinations = [(42.25, -8.73)]
        
        result = get_travel_time_matrix(sources, destinations)
        assert result == [[10]]
    
    @patch('router_service.requests.get')
    def test_get_travel_time_matrix_api_error(self, mock_get):
        """Test matrix API error handling."""
        mock_get.side_effect = Exception("API Error")
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        sources = [(42.24, -8.72)]
        destinations = [(42.25, -8.73)]
        
        result = get_travel_time_matrix(sources, destinations)
        # Should return matrix with None values
        assert result == [[None]]
    
    @patch('router_service.requests.get')
    def test_get_travel_time_matrix_rate_limit(self, mock_get):
        """Test matrix rate limit handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429  # Rate limited
        mock_get.return_value = mock_response
        
        # Clear cache
        import router_service
        router_service._travel_time_cache = {}
        
        sources = [(42.24, -8.72)]
        destinations = [(42.25, -8.73)]
        
        result = get_travel_time_matrix(sources, destinations)
        # Should return matrix with None values
        assert result == [[None]]


# ============================================================
# EDGE CASE TESTS
# ============================================================

class TestRouterServiceEdgeCases:
    """Test edge cases for router service."""
    
    def test_get_cache_key_rounding(self):
        """Test cache key with many decimal places."""
        key = _get_cache_key(42.240623456, -8.720723456, 42.250012345, -8.730012345)
        # Should be rounded to 5 decimal places
        assert "42.24062" in key
        assert "-8.72072" in key
    
    def test_get_real_travel_time_same_point(self):
        """Test travel time for same point."""
        # Should handle gracefully (OSRM returns 0)
        with patch('router_service.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'code': 'Ok',
                'routes': [{'duration': 0}]
            }
            mock_get.return_value = mock_response
            
            import router_service
            router_service._travel_time_cache = {}
            
            result = get_real_travel_time(42.24, -8.72, 42.24, -8.72)
            assert result == 0
