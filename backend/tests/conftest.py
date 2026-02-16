"""
Pytest configuration and shared fixtures for Tutti backend tests.
"""
import pytest
import json
import os
import sys
from datetime import time
from typing import List

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import Stop, Route, BusSchedule, ScheduleItem, Bus


# ============================================================
# FIXTURES FOR STOPS
# ============================================================

@pytest.fixture
def sample_stop() -> Stop:
    """Create a basic stop fixture."""
    return Stop(
        name="Test Stop",
        lat=42.2406,
        lon=-8.7207,
        order=1,
        time_from_start=5,
        passengers=10,
        is_school=False
    )


@pytest.fixture
def school_stop() -> Stop:
    """Create a school stop fixture."""
    return Stop(
        name="Colexio Test",
        lat=42.2500,
        lon=-8.7300,
        order=99,
        time_from_start=30,
        passengers=0,
        is_school=True
    )


@pytest.fixture
def multiple_stops() -> List[Stop]:
    """Create a list of stops for a route."""
    return [
        Stop(name="Stop 1", lat=42.2400, lon=-8.7200, order=1, time_from_start=0, passengers=5),
        Stop(name="Stop 2", lat=42.2410, lon=-8.7210, order=2, time_from_start=5, passengers=8),
        Stop(name="Stop 3", lat=42.2420, lon=-8.7220, order=3, time_from_start=10, passengers=7),
        Stop(name="School", lat=42.2500, lon=-8.7300, order=4, time_from_start=25, passengers=0, is_school=True),
    ]


# ============================================================
# FIXTURES FOR ROUTES
# ============================================================

@pytest.fixture
def entry_route(multiple_stops) -> Route:
    """Create an entry route fixture (morning pickup)."""
    return Route(
        id="R001_E1_E",
        name="Route 001 Entry",
        stops=multiple_stops,
        school_id="SCH001",
        school_name="Colexio Test",
        arrival_time=time(9, 0),
        departure_time=None,
        capacity_needed=20,
        contract_id="CNT001",
        type="entry",
        days=["L", "M", "Mc", "X", "V"]
    )


@pytest.fixture
def exit_route(multiple_stops) -> Route:
    """Create an exit route fixture (afternoon dropoff)."""
    return Route(
        id="R001_E1_X",
        name="Route 001 Exit",
        stops=multiple_stops,
        school_id="SCH001",
        school_name="Colexio Test",
        arrival_time=None,
        departure_time=time(14, 30),
        capacity_needed=20,
        contract_id="CNT001",
        type="exit",
        days=["L", "M", "Mc", "X", "V"]
    )


@pytest.fixture
def multiple_entry_routes() -> List[Route]:
    """Create multiple entry routes for testing optimizer."""
    routes = []
    base_time = 8 * 60  # 8:00 AM in minutes
    
    for i in range(5):
        stops = [
            Stop(name=f"Stop {i}-1", lat=42.24 + i*0.001, lon=-8.72 - i*0.001, 
                 order=1, time_from_start=0, passengers=5),
            Stop(name=f"Stop {i}-2", lat=42.241 + i*0.001, lon=-8.721 - i*0.001, 
                 order=2, time_from_start=10, passengers=5),
            Stop(name="School", lat=42.25, lon=-8.73, order=3, 
                 time_from_start=25, passengers=0, is_school=True),
        ]
        
        route = Route(
            id=f"R{i:03d}_E",
            name=f"Route {i:03d} Entry",
            stops=stops,
            school_id="SCH001",
            school_name="Colexio Test",
            arrival_time=time(8 + i//2, (i*15) % 60),
            departure_time=None,
            capacity_needed=10,
            contract_id="CNT001",
            type="entry",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    return routes


@pytest.fixture
def multiple_exit_routes() -> List[Route]:
    """Create multiple exit routes for testing optimizer."""
    routes = []
    
    for i in range(5):
        stops = [
            Stop(name=f"Stop {i}-1", lat=42.24 + i*0.001, lon=-8.72 - i*0.001, 
                 order=1, time_from_start=0, passengers=5),
            Stop(name=f"Stop {i}-2", lat=42.241 + i*0.001, lon=-8.721 - i*0.001, 
                 order=2, time_from_start=10, passengers=5),
            Stop(name="School", lat=42.25, lon=-8.73, order=3, 
                 time_from_start=25, passengers=0, is_school=True),
        ]
        
        route = Route(
            id=f"R{i:03d}_X",
            name=f"Route {i:03d} Exit",
            stops=stops,
            school_id="SCH001",
            school_name="Colexio Test",
            arrival_time=None,
            departure_time=time(14 + i//2, (i*20) % 60),
            capacity_needed=10,
            contract_id="CNT001",
            type="exit",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    return routes


@pytest.fixture
def mixed_routes(multiple_entry_routes, multiple_exit_routes) -> List[Route]:
    """Create mixed entry and exit routes."""
    return multiple_entry_routes + multiple_exit_routes


@pytest.fixture
def optimizer_test_routes() -> List[Route]:
    """
    Create 15 routes suitable for optimizer testing.
    Mix of entry (morning) and exit (afternoon) routes.
    """
    routes = []
    
    # Entry routes (Block 1: morning 8:00-9:30)
    for i in range(8):
        stops = [
            Stop(name=f"E-Stop {i}-A", lat=42.235 + i*0.002, lon=-8.715 - i*0.002, 
                 order=1, time_from_start=0, passengers=4),
            Stop(name=f"E-Stop {i}-B", lat=42.236 + i*0.002, lon=-8.716 - i*0.002, 
                 order=2, time_from_start=8, passengers=4),
            Stop(name="School A", lat=42.245, lon=-8.725, order=3, 
                 time_from_start=20, passengers=0, is_school=True),
        ]
        
        # Vary arrival times across morning
        hour = 8 + (i // 3)
        minute = (i * 20) % 60
        
        route = Route(
            id=f"E{i+1:03d}_ENTRY",
            name=f"Entry Route {i+1}",
            stops=stops,
            school_id=f"SCH{100 + i//4}",
            school_name=f"School {100 + i//4}",
            arrival_time=time(hour, minute),
            departure_time=None,
            capacity_needed=8,
            contract_id="CONTRACT_1",
            type="entry",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    # Exit routes (Block 2: afternoon 14:00-16:15)
    for i in range(7):
        stops = [
            Stop(name=f"X-Stop {i}-A", lat=42.238 + i*0.002, lon=-8.718 - i*0.002, 
                 order=1, time_from_start=0, passengers=5),
            Stop(name=f"X-Stop {i}-B", lat=42.239 + i*0.002, lon=-8.719 - i*0.002, 
                 order=2, time_from_start=10, passengers=5),
            Stop(name="School B", lat=42.248, lon=-8.728, order=3, 
                 time_from_start=25, passengers=0, is_school=True),
        ]
        
        hour = 14 + (i // 3)
        minute = (i * 25) % 60
        
        route = Route(
            id=f"X{i+1:03d}_EXIT",
            name=f"Exit Route {i+1}",
            stops=stops,
            school_id=f"SCH{200 + i//4}",
            school_name=f"School {200 + i//4}",
            arrival_time=None,
            departure_time=time(hour, minute),
            capacity_needed=10,
            contract_id="CONTRACT_2",
            type="exit",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    return routes


# ============================================================
# FIXTURES FOR BUSES AND SCHEDULES
# ============================================================

@pytest.fixture
def sample_bus() -> Bus:
    """Create a bus fixture."""
    return Bus(
        id="BUS001",
        capacity=55,
        plate="1234 ABC"
    )


@pytest.fixture
def sample_schedule_item(entry_route) -> ScheduleItem:
    """Create a schedule item fixture."""
    return ScheduleItem(
        route_id=entry_route.id,
        start_time=time(8, 30),
        end_time=time(9, 0),
        type="entry",
        original_start_time=time(9, 0),
        time_shift_minutes=0,
        deadhead_minutes=10,
        school_name=entry_route.school_name,
        stops=entry_route.stops,
        contract_id=entry_route.contract_id
    )


@pytest.fixture
def sample_bus_schedule(sample_schedule_item) -> BusSchedule:
    """Create a bus schedule fixture."""
    return BusSchedule(
        bus_id="BUS001",
        items=[sample_schedule_item],
        last_loc=(42.25, -8.73)
    )


# ============================================================
# FIXTURES FOR FILE PATHS
# ============================================================

@pytest.fixture
def fixtures_dir() -> str:
    """Return the path to the fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def sample_json_path(fixtures_dir) -> str:
    """Return the path to the sample routes JSON file."""
    return os.path.join(fixtures_dir, "sample_routes.json")


@pytest.fixture
def sample_excel_path(fixtures_dir) -> str:
    """Return the path to the sample Excel file."""
    return os.path.join(fixtures_dir, "sample_excel.xlsx")


# ============================================================
# FIXTURES FOR ASYNC TESTING (CELERY + WEBSOCKET)
# ============================================================

@pytest.fixture(scope="session")
def celery_config():
    """Configure Celery for testing."""
    return {
        "broker_url": "redis://localhost:6379/1",  # Use different DB for tests
        "result_backend": "redis://localhost:6379/1",
        "task_always_eager": True,  # Execute tasks synchronously in tests
        "task_store_eager_result": True,
    }


@pytest.fixture
def celery_worker():
    """Configure Celery app for eager execution in tests."""
    try:
        from celery_app import celery_app
        
        # Store original config
        original_always_eager = celery_app.conf.task_always_eager
        original_store_eager = celery_app.conf.task_store_eager_result
        
        # Configure for testing
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_store_eager_result = True
        
        yield celery_app
        
        # Restore original config
        celery_app.conf.task_always_eager = original_always_eager
        celery_app.conf.task_store_eager_result = original_store_eager
        
    except ImportError:
        pytest.skip("Celery not available")


@pytest.fixture
def sample_routes_async() -> List[Route]:
    """
    Create a small set of routes for fast async tests.
    
    These routes are smaller than the standard fixtures to ensure
    tests run quickly while still providing realistic test data.
    """
    routes = []
    
    # Entry routes (2 routes for speed)
    for i in range(2):
        stops = [
            Stop(
                name=f"Async Stop {i}-A",
                lat=42.235 + i*0.01,
                lon=-8.715 - i*0.01,
                order=1,
                time_from_start=0,
                passengers=5
            ),
            Stop(
                name="School",
                lat=42.245,
                lon=-8.725,
                order=2,
                time_from_start=20,
                passengers=0,
                is_school=True
            ),
        ]
        
        route = Route(
            id=f"ASYNC_R{i:03d}_E",
            name=f"Async Route {i} Entry",
            stops=stops,
            school_id="SCH_ASYNC",
            school_name="Colegio Async",
            arrival_time=time(8 + i, 0),
            departure_time=None,
            capacity_needed=10,
            contract_id="CNT_ASYNC",
            type="entry",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    # Exit routes (1 route for speed)
    for i in range(1):
        stops = [
            Stop(
                name=f"Async Stop {i}-B",
                lat=42.238 + i*0.01,
                lon=-8.718 - i*0.01,
                order=1,
                time_from_start=0,
                passengers=5
            ),
            Stop(
                name="School",
                lat=42.248,
                lon=-8.728,
                order=2,
                time_from_start=25,
                passengers=0,
                is_school=True
            ),
        ]
        
        route = Route(
            id=f"ASYNC_R{i:03d}_X",
            name=f"Async Route {i} Exit",
            stops=stops,
            school_id="SCH_ASYNC",
            school_name="Colegio Async",
            arrival_time=None,
            departure_time=time(14 + i, 30),
            capacity_needed=10,
            contract_id="CNT_ASYNC",
            type="exit",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    return routes


@pytest.fixture
def sample_optimization_job():
    """Create a sample optimization job dict for testing."""
    return {
        "id": "test-job-123",
        "status": "queued",
        "algorithm": "v6",
        "input_data": {"routes": []},
        "created_at": "2026-02-10T12:00:00"
    }


@pytest.fixture
def mock_celery_task():
    """Create a mock Celery task for unit testing."""
    from unittest.mock import Mock
    
    task = Mock()
    task.request.retries = 0
    task.update_state = Mock()
    task.retry = Mock(side_effect=Exception("Retry triggered"))
    return task


@pytest.fixture
def websocket_manager():
    """Create a fresh ConnectionManager instance for testing."""
    try:
        from websocket import ConnectionManager
        return ConnectionManager()
    except ImportError:
        pytest.skip("WebSocket module not available")


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    from unittest.mock import AsyncMock
    
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


# ============================================================
# TEST CONFIGURATION
# ============================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "optimizer: marks tests as optimizer tests")
    config.addinivalue_line("markers", "async_test: marks tests as async tests requiring special setup")
