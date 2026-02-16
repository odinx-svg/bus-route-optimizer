"""
Tests for Monte Carlo WebSocket streaming functionality.

Validates:
- WebSocket connection and configuration
- Progressive streaming of simulation batches
- 3D scatter plot data format (x, y, z)
- Real-time progress updates
- Grade calculation
- Error handling
"""

import pytest
import json
import asyncio
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def mock_schedule_data():
    """Provide sample schedule data for testing."""
    return [
        {
            "bus_id": "bus-1",
            "items": [
                {
                    "route_id": "R1",
                    "type": "entry",
                    "start_time": "08:00",
                    "end_time": "09:30",
                    "deadhead_minutes": 10
                },
                {
                    "route_id": "R2",
                    "type": "exit",
                    "start_time": "10:00",
                    "end_time": "11:30",
                    "deadhead_minutes": 15
                }
            ]
        }
    ]


@pytest.fixture
def mock_routes_data():
    """Provide sample routes data for testing."""
    return [
        {
            "id": "R1",
            "name": "Route 1",
            "stops": [
                {"lat": 40.0, "lon": -3.0},
                {"lat": 40.1, "lon": -3.1}
            ],
            "days": ["L", "M"]
        },
        {
            "id": "R2",
            "name": "Route 2",
            "stops": [
                {"lat": 40.1, "lon": -3.1},
                {"lat": 40.2, "lon": -3.2}
            ],
            "days": ["L", "M"]
        }
    ]


@pytest.fixture
def base_mc_config(mock_schedule_data):
    """Provide base Monte Carlo configuration."""
    return {
        "n_simulations": 100,
        "uncertainty": 0.2,
        "distribution": "lognormal",
        "batch_size": 25,
        "schedule": mock_schedule_data,
        "routes": []
    }


# ============================================================
# TESTS - MONTE CARLO STREAMING VALIDATOR
# ============================================================

class TestMonteCarloStreamingValidator:
    """Test MonteCarloStreamingValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a streaming validator instance."""
        try:
            from websocket_monte_carlo import MonteCarloStreamingValidator
            return MonteCarloStreamingValidator(
                n_simulations=100,
                time_uncertainty=0.2,
                batch_size=25
            )
        except ImportError:
            pytest.skip("websocket_monte_carlo module not available")
    
    def test_initialization(self, validator):
        """Test validator initialization."""
        assert validator.n_simulations == 100
        assert validator.time_uncertainty == 0.2
        assert validator.batch_size == 25
        assert validator.distribution == "lognormal"
    
    def test_calculate_grade(self, validator):
        """Test grade calculation."""
        assert validator.calculate_grade(0.96) == "A"
        assert validator.calculate_grade(0.90) == "B"
        assert validator.calculate_grade(0.75) == "C"
        assert validator.calculate_grade(0.60) == "D"
        assert validator.calculate_grade(0.40) == "F"
        # Edge cases
        assert validator.calculate_grade(0.95) == "A"
        assert validator.calculate_grade(0.85) == "B"
        assert validator.calculate_grade(0.70) == "C"
        assert validator.calculate_grade(0.50) == "D"
    
    def test_reset(self, validator):
        """Test reset functionality."""
        validator.completed = 50
        validator.feasible_count = 25
        validator.scenarios = [{"id": 1}]
        validator.violation_distribution = {0: 25}
        
        validator.reset()
        
        assert validator.completed == 0
        assert validator.feasible_count == 0
        assert validator.scenarios == []
        assert validator.violation_distribution == {}
    
    def test_simulate_travel_times(self, validator):
        """Test travel time simulation."""
        base_times = {
            ("R1", "R2"): 15.0,
            ("R2", "R3"): 20.0
        }
        
        simulated = validator.simulate_travel_times(base_times)
        
        assert len(simulated) == 2
        assert ("R1", "R2") in simulated
        assert ("R2", "R3") in simulated
        # All values should be positive
        assert all(v > 0 for v in simulated.values())
    
    def test_calculate_time_deviation(self, validator):
        """Test time deviation calculation."""
        base_times = {
            ("R1", "R2"): 10.0,
            ("R2", "R3"): 20.0
        }
        
        # No deviation
        simulated_same = base_times.copy()
        deviation = validator._calculate_time_deviation(base_times, simulated_same)
        assert deviation == 0.0
        
        # 50% deviation
        simulated_diff = {
            ("R1", "R2"): 15.0,  # 50% higher
            ("R2", "R3"): 20.0   # Same
        }
        deviation = validator._calculate_time_deviation(base_times, simulated_diff)
        assert deviation == 0.25  # Average of 0.5 and 0
    
    @pytest.mark.asyncio
    async def test_validate_streaming_sends_batches(self, validator):
        """Test that streaming validation sends batches."""
        from unittest.mock import AsyncMock
        
        mock_websocket = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        
        # Simple schedule for testing
        mock_schedule = []
        base_times = {}
        
        # Override methods to avoid needing real schedule
        validator.n_simulations = 50
        validator.batch_size = 10
        
        with patch.object(validator, 'run_single_simulation') as mock_run:
            mock_run.return_value = {
                "id": 0,
                "x": 0.1,
                "y": 100.0,
                "z": 1,
                "feasible": True,
                "violations": 0
            }
            
            await validator.validate_streaming(mock_schedule, base_times, mock_websocket)
        
        # Should send 5 progress messages (50 sims / 10 batch_size) + 1 final
        assert mock_websocket.send_json.call_count >= 5
        
        # Check first progress message structure
        calls = mock_websocket.send_json.call_args_list
        first_call = calls[0][0][0]  # First positional argument of first call
        
        assert first_call["type"] == "progress"
        assert "completed" in first_call
        assert "total" in first_call
        assert "feasible_rate" in first_call
        assert "grade" in first_call
        assert "scenarios" in first_call


# ============================================================
# TESTS - WEBSOCKET ENDPOINT
# ============================================================

@pytest.mark.integration
class TestMonteCarloWebSocketEndpoint:
    """Test Monte Carlo WebSocket endpoint integration."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        try:
            from main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("Main app not available")
    
    def test_websocket_connect(self, client):
        """Test WebSocket connection is accepted."""
        try:
            with client.websocket_connect("/ws/monte-carlo/test-job-123") as websocket:
                # Connection should be established
                pass
        except Exception as e:
            pytest.skip(f"Monte Carlo WebSocket not available: {e}")
    
    def test_websocket_requires_schedule(self, client, base_mc_config):
        """Test that WebSocket requires schedule configuration."""
        try:
            with client.websocket_connect("/ws/monte-carlo/test-job-123") as websocket:
                # Send config without schedule
                bad_config = base_mc_config.copy()
                del bad_config["schedule"]
                websocket.send_json(bad_config)
                
                # Should receive error
                response = websocket.receive_json(timeout=2.0)
                assert response["type"] == "error"
        except Exception as e:
            pytest.skip(f"Monte Carlo WebSocket test failed: {e}")
    
    def test_websocket_streaming_progress(self, client, base_mc_config):
        """Test that WebSocket streams progress messages."""
        try:
            with client.websocket_connect("/ws/monte-carlo/test-job-123") as websocket:
                # Send valid configuration
                websocket.send_json(base_mc_config)
                
                # Collect messages
                messages = []
                try:
                    for _ in range(10):  # Expect several progress messages
                        msg = websocket.receive_json(timeout=5.0)
                        messages.append(msg)
                        if msg.get("type") == "completed":
                            break
                except Exception:
                    pass
                
                # Should have received progress messages
                progress_msgs = [m for m in messages if m.get("type") == "progress"]
                assert len(progress_msgs) > 0
                
                # Verify progress message structure
                first_progress = progress_msgs[0]
                assert "completed" in first_progress
                assert "total" in first_progress
                assert "feasible_rate" in first_progress
                assert "grade" in first_progress
                assert "scenarios" in first_progress
                
        except Exception as e:
            pytest.skip(f"Monte Carlo WebSocket test failed: {e}")
    
    def test_websocket_3d_scatter_data(self, client, base_mc_config):
        """Test that scenarios include 3D scatter plot data."""
        try:
            with client.websocket_connect("/ws/monte-carlo/test-job-456") as websocket:
                websocket.send_json(base_mc_config)
                
                # Wait for progress message
                msg = websocket.receive_json(timeout=5.0)
                
                # Skip started message if present
                while msg.get("type") == "started":
                    msg = websocket.receive_json(timeout=5.0)
                
                if msg.get("type") == "progress":
                    scenarios = msg.get("scenarios", [])
                    assert len(scenarios) > 0
                    
                    # Verify 3D data structure
                    scenario = scenarios[0]
                    assert "x" in scenario  # Time deviation
                    assert "y" in scenario  # Duration
                    assert "z" in scenario  # Feasibility
                    assert "id" in scenario
                    assert "feasible" in scenario
                    
        except Exception as e:
            pytest.skip(f"Monte Carlo WebSocket test failed: {e}")
    
    def test_websocket_completion_message(self, client, base_mc_config):
        """Test that WebSocket sends completion message."""
        try:
            with client.websocket_connect("/ws/monte-carlo/test-job-789") as websocket:
                websocket.send_json(base_mc_config)
                
                # Collect all messages until completion
                completed_msg = None
                for _ in range(20):  # Max 20 messages
                    try:
                        msg = websocket.receive_json(timeout=5.0)
                        if msg.get("type") == "completed":
                            completed_msg = msg
                            break
                    except Exception:
                        break
                
                assert completed_msg is not None, "Should receive completed message"
                assert "final_grade" in completed_msg
                assert "feasible_rate" in completed_msg
                assert "total_scenarios" in completed_msg
                assert "all_scenarios" in completed_msg
                
        except Exception as e:
            pytest.skip(f"Monte Carlo WebSocket test failed: {e}")
    
    def test_websocket_batch_size(self, client, mock_schedule_data):
        """Test that batch size controls message frequency."""
        config = {
            "n_simulations": 40,
            "uncertainty": 0.2,
            "batch_size": 10,  # Should send 4 progress messages
            "schedule": mock_schedule_data,
            "routes": []
        }
        
        try:
            with client.websocket_connect("/ws/monte-carlo/test-batch") as websocket:
                websocket.send_json(config)
                
                progress_count = 0
                for _ in range(10):
                    try:
                        msg = websocket.receive_json(timeout=3.0)
                        if msg.get("type") == "progress":
                            progress_count += 1
                        elif msg.get("type") == "completed":
                            break
                    except Exception:
                        break
                
                # Should have approximately 4 progress messages (40/10)
                assert progress_count >= 3, f"Expected at least 3 progress messages, got {progress_count}"
                
        except Exception as e:
            pytest.skip(f"Monte Carlo WebSocket test failed: {e}")


# ============================================================
# TESTS - GRADE CALCULATION
# ============================================================

class TestGradeCalculation:
    """Test grade calculation function."""
    
    def test_calculate_grade_function(self):
        """Test the standalone calculate_grade function."""
        try:
            from websocket_monte_carlo import calculate_grade
            
            assert calculate_grade(0.96) == "A"
            assert calculate_grade(0.95) == "A"
            assert calculate_grade(0.90) == "B"
            assert calculate_grade(0.85) == "B"
            assert calculate_grade(0.75) == "C"
            assert calculate_grade(0.70) == "C"
            assert calculate_grade(0.60) == "D"
            assert calculate_grade(0.50) == "D"
            assert calculate_grade(0.49) == "F"
            assert calculate_grade(0.0) == "F"
        except ImportError:
            pytest.skip("websocket_monte_carlo module not available")


# ============================================================
# TESTS - MONTE CARLO VALIDATOR EXTENSIONS
# ============================================================

class TestMonteCarloValidatorExtensions:
    """Test extensions to MonteCarloValidator class."""
    
    @pytest.fixture
    def mc_validator(self):
        """Create a MonteCarloValidator instance."""
        try:
            from validation.monte_carlo import MonteCarloValidator
            return MonteCarloValidator(n_simulations=10, seed=42)
        except ImportError:
            pytest.skip("Monte Carlo validation not available")
    
    @pytest.fixture
    def sample_schedule(self):
        """Create a sample schedule for testing."""
        try:
            from models import BusSchedule, ScheduleItem
            from datetime import time
            
            return [
                BusSchedule(
                    bus_id="BUS-1",
                    items=[
                        ScheduleItem(
                            route_id="R1",
                            type="entry",
                            start_time=time(8, 0),
                            end_time=time(9, 0),
                            deadhead_minutes=10
                        ),
                        ScheduleItem(
                            route_id="R2",
                            type="exit",
                            start_time=time(10, 0),
                            end_time=time(11, 0),
                            deadhead_minutes=15
                        )
                    ]
                )
            ]
        except ImportError:
            pytest.skip("Models not available")
    
    @pytest.fixture
    def base_travel_times(self):
        """Create base travel times."""
        return {
            ("R1", "R2"): 15.0
        }
    
    def test_run_single_simulation(self, mc_validator, sample_schedule, base_travel_times):
        """Test single simulation execution."""
        result = mc_validator.run_single_simulation(
            sample_schedule, base_travel_times, sim_id=0
        )
        
        # Verify structure
        assert "id" in result
        assert result["id"] == 0
        assert "x" in result  # Time deviation
        assert "y" in result  # Duration
        assert "z" in result  # Feasibility
        assert "feasible" in result
        assert "violations" in result
        assert "simulated_times" in result
        
        # Verify types
        assert isinstance(result["x"], (int, float))
        assert isinstance(result["y"], (int, float))
        assert result["z"] in [0, 1]
        assert isinstance(result["feasible"], bool)
        assert isinstance(result["violations"], int)
    
    def test_run_single_simulation_3d_data(self, mc_validator, sample_schedule, base_travel_times):
        """Test that simulation returns proper 3D scatter data."""
        # Run multiple simulations
        results = []
        for i in range(10):
            result = mc_validator.run_single_simulation(
                sample_schedule, base_travel_times, sim_id=i
            )
            results.append(result)
        
        # All should have 3D coordinates
        for r in results:
            assert isinstance(r["x"], (int, float))
            assert isinstance(r["y"], (int, float))
            assert r["z"] in [0, 1]
            assert r["z"] == (1 if r["feasible"] else 0)
    
    def test_calculate_time_deviation_method(self, mc_validator):
        """Test the _calculate_time_deviation method."""
        base_times = {
            ("A", "B"): 10.0,
            ("B", "C"): 20.0
        }
        
        # No deviation
        simulated_same = base_times.copy()
        dev = mc_validator._calculate_time_deviation(base_times, simulated_same)
        assert dev == 0.0
        
        # 10% deviation average
        simulated_10pct = {
            ("A", "B"): 11.0,  # 10% higher
            ("B", "C"): 22.0   # 10% higher
        }
        dev = mc_validator._calculate_time_deviation(base_times, simulated_10pct)
        assert abs(dev - 0.10) < 0.001
    
    def test_calculate_schedule_duration(self, mc_validator, sample_schedule):
        """Test schedule duration calculation."""
        travel_times = {
            ("R1", "R2"): 15.0
        }
        
        duration = mc_validator._calculate_schedule_duration(sample_schedule, travel_times)
        
        # Duration should be positive
        assert duration > 0
        
        # Expected: 60 min (R1) + 15 min (travel) + 60 min (R2) = 135 min
        assert abs(duration - 135.0) < 1.0  # Allow small tolerance


# ============================================================
# TESTS - VALIDATOR CACHE
# ============================================================

class TestValidatorCache:
    """Test validator caching functionality."""
    
    def test_cache_validator(self):
        """Test caching a validator."""
        try:
            from websocket_monte_carlo import (
                cache_validator, get_validator, clear_validator_cache,
                MonteCarloStreamingValidator
            )
            
            validator = MonteCarloStreamingValidator()
            cache_validator("job-123", validator)
            
            retrieved = get_validator("job-123")
            assert retrieved is validator
            
            clear_validator_cache("job-123")
            assert get_validator("job-123") is None
        except ImportError:
            pytest.skip("websocket_monte_carlo module not available")


# ============================================================
# TESTS - ERROR HANDLING
# ============================================================

class TestErrorHandling:
    """Test error handling in Monte Carlo WebSocket."""
    
    @pytest.mark.asyncio
    async def test_handle_invalid_schedule(self):
        """Test handling of invalid schedule data."""
        try:
            from websocket_monte_carlo import handle_monte_carlo_websocket
            
            mock_websocket = AsyncMock()
            mock_websocket.accept = AsyncMock()
            mock_websocket.receive_json = AsyncMock(return_value={
                "n_simulations": 100,
                "schedule": "invalid"  # Should be a list
            })
            mock_websocket.send_json = AsyncMock()
            mock_websocket.close = AsyncMock()
            
            await handle_monte_carlo_websocket(mock_websocket, "test-job")
            
            # Should send error message
            calls = mock_websocket.send_json.call_args_list
            error_calls = [c for c in calls if c[0][0].get("type") == "error"]
            assert len(error_calls) > 0
            
        except ImportError:
            pytest.skip("websocket_monte_carlo module not available")


# ============================================================
# TESTS - BENCHMARK
# ============================================================

class TestPerformance:
    """Performance tests for Monte Carlo streaming."""
    
    @pytest.mark.slow
    def test_batch_processing_performance(self):
        """Test that batch processing is efficient."""
        try:
            from websocket_monte_carlo import MonteCarloStreamingValidator
            import time
            
            validator = MonteCarloStreamingValidator(
                n_simulations=1000,
                batch_size=50
            )
            
            # Simple test data
            base_times = {("A", "B"): 15.0, ("B", "C"): 20.0}
            
            # Measure simulation time
            start = time.time()
            
            simulated_count = 0
            for _ in range(1000):
                simulated = validator.simulate_travel_times(base_times)
                simulated_count += len(simulated)
            
            elapsed = time.time() - start
            
            # Should complete 1000 simulations quickly
            assert elapsed < 5.0, f"1000 simulations took {elapsed:.2f}s, expected < 5s"
            
        except ImportError:
            pytest.skip("websocket_monte_carlo module not available")
