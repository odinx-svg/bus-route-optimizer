"""
Tests for Pydantic models (Stop, Route, BusSchedule, etc.)
"""
import pytest
from datetime import time
from typing import List

from models import Stop, Route, BusSchedule, ScheduleItem, Bus


# ============================================================
# STOP MODEL TESTS
# ============================================================

class TestStop:
    """Test suite for Stop model."""
    
    def test_create_basic_stop(self, sample_stop):
        """Test creating a basic stop."""
        assert sample_stop.name == "Test Stop"
        assert sample_stop.lat == 42.2406
        assert sample_stop.lon == -8.7207
        assert sample_stop.order == 1
        assert sample_stop.time_from_start == 5
        assert sample_stop.passengers == 10
        assert sample_stop.is_school is False
    
    def test_create_school_stop(self, school_stop):
        """Test creating a school stop."""
        assert school_stop.is_school is True
        assert school_stop.passengers == 0
        assert "Colexio" in school_stop.name
    
    def test_stop_default_values(self):
        """Test stop default values."""
        stop = Stop(
            name="Default Stop",
            lat=42.0,
            lon=-8.0,
            order=1,
            time_from_start=0
        )
        assert stop.passengers == 0
        assert stop.is_school is False
    
    def test_stop_validation_lat_range(self):
        """Test latitude validation (should be -90 to 90)."""
        # Valid latitudes
        Stop(name="Valid", lat=0, lon=0, order=1, time_from_start=0)
        Stop(name="Valid", lat=90, lon=0, order=1, time_from_start=0)
        Stop(name="Valid", lat=-90, lon=0, order=1, time_from_start=0)
        
        # Invalid latitudes - Pydantic will coerce but we can check the value
        stop = Stop(name="Invalid", lat=100, lon=0, order=1, time_from_start=0)
        assert stop.lat == 100  # Pydantic accepts it, validation would be in business logic
    
    def test_stop_validation_lon_range(self):
        """Test longitude validation."""
        stop = Stop(name="Valid", lat=0, lon=180, order=1, time_from_start=0)
        assert stop.lon == 180
        
        stop = Stop(name="Valid", lat=0, lon=-180, order=1, time_from_start=0)
        assert stop.lon == -180
    
    def test_stop_negative_passengers(self):
        """Test that negative passengers are accepted (validation would be in business logic)."""
        stop = Stop(
            name="Test",
            lat=42.0,
            lon=-8.0,
            order=1,
            time_from_start=0,
            passengers=-5
        )
        assert stop.passengers == -5
    
    def test_stop_serialization(self, sample_stop):
        """Test stop serialization to dict."""
        data = sample_stop.model_dump()
        assert data["name"] == "Test Stop"
        assert data["lat"] == 42.2406
        assert data["passengers"] == 10
    
    def test_stop_json_serialization(self, sample_stop):
        """Test stop JSON serialization."""
        json_str = sample_stop.model_dump_json()
        assert "Test Stop" in json_str
        assert "42.2406" in json_str


# ============================================================
# ROUTE MODEL TESTS
# ============================================================

class TestRoute:
    """Test suite for Route model."""
    
    def test_create_entry_route(self, entry_route):
        """Test creating an entry route."""
        assert entry_route.id == "R001_E1_E"
        assert entry_route.type == "entry"
        assert entry_route.arrival_time == time(9, 0)
        assert entry_route.departure_time is None
        assert entry_route.capacity_needed == 20
    
    def test_create_exit_route(self, exit_route):
        """Test creating an exit route."""
        assert exit_route.id == "R001_E1_X"
        assert exit_route.type == "exit"
        assert exit_route.departure_time == time(14, 30)
        assert exit_route.arrival_time is None
    
    def test_route_num_students_computed(self, entry_route):
        """Test computed_field num_students."""
        # 5 + 8 + 7 + 0 = 20
        assert entry_route.num_students == 20
    
    def test_route_num_students_empty_stops(self):
        """Test num_students with empty stops."""
        route = Route(
            id="R_EMPTY",
            name="Empty Route",
            stops=[],
            school_id="SCH001",
            school_name="Test School",
            capacity_needed=0,
            contract_id="CNT001",
            type="entry"
        )
        assert route.num_students == 0
    
    def test_route_days_default(self):
        """Test default days value."""
        route = Route(
            id="R001",
            name="Test Route",
            stops=[],
            school_id="SCH001",
            school_name="Test School",
            capacity_needed=50,
            contract_id="CNT001",
            type="entry"
        )
        assert route.days == []
    
    def test_route_serialization(self, entry_route):
        """Test route serialization."""
        data = entry_route.model_dump()
        assert data["id"] == "R001_E1_E"
        assert data["type"] == "entry"
        assert "num_students" in data  # computed_field is included
    
    def test_route_with_multiple_stops(self, multiple_stops):
        """Test route with multiple stops."""
        route = Route(
            id="R_MULTI",
            name="Multi Stop Route",
            stops=multiple_stops,
            school_id="SCH001",
            school_name="Test School",
            arrival_time=time(8, 30),
            capacity_needed=20,
            contract_id="CNT001",
            type="entry"
        )
        assert len(route.stops) == 4
        assert route.num_students == 20  # 5+8+7+0


# ============================================================
# BUS MODEL TESTS
# ============================================================

class TestBus:
    """Test suite for Bus model."""
    
    def test_create_bus(self, sample_bus):
        """Test creating a bus."""
        assert sample_bus.id == "BUS001"
        assert sample_bus.capacity == 55
        assert sample_bus.plate == "1234 ABC"
    
    def test_bus_optional_plate(self):
        """Test bus with optional plate."""
        bus = Bus(id="BUS002", capacity=60)
        assert bus.plate is None
    
    def test_bus_serialization(self, sample_bus):
        """Test bus serialization."""
        data = sample_bus.model_dump()
        assert data["id"] == "BUS001"
        assert data["capacity"] == 55


# ============================================================
# SCHEDULE ITEM TESTS
# ============================================================

class TestScheduleItem:
    """Test suite for ScheduleItem model."""
    
    def test_create_schedule_item(self, sample_schedule_item, entry_route):
        """Test creating a schedule item."""
        assert sample_schedule_item.route_id == entry_route.id
        assert sample_schedule_item.start_time == time(8, 30)
        assert sample_schedule_item.end_time == time(9, 0)
        assert sample_schedule_item.type == "entry"
        assert sample_schedule_item.deadhead_minutes == 10
    
    def test_schedule_item_defaults(self):
        """Test schedule item default values."""
        item = ScheduleItem(
            route_id="R001",
            start_time=time(8, 0),
            end_time=time(9, 0),
            type="entry"
        )
        assert item.time_shift_minutes == 0
        assert item.deadhead_minutes == 0
        assert item.school_name is None
        assert item.contract_id is None
        assert item.stops == []
    
    def test_schedule_item_with_shift(self, entry_route):
        """Test schedule item with time shift."""
        item = ScheduleItem(
            route_id=entry_route.id,
            start_time=time(8, 30),
            end_time=time(9, 0),
            type="entry",
            original_start_time=time(9, 0),
            time_shift_minutes=30,
            school_name=entry_route.school_name
        )
        assert item.time_shift_minutes == 30
        assert item.original_start_time == time(9, 0)


# ============================================================
# BUS SCHEDULE TESTS
# ============================================================

class TestBusSchedule:
    """Test suite for BusSchedule model."""
    
    def test_create_bus_schedule(self, sample_bus_schedule):
        """Test creating a bus schedule."""
        assert sample_bus_schedule.bus_id == "BUS001"
        assert len(sample_bus_schedule.items) == 1
        assert sample_bus_schedule.last_loc == (42.25, -8.73)
    
    def test_bus_schedule_multiple_items(self, entry_route, exit_route):
        """Test bus schedule with multiple items."""
        items = [
            ScheduleItem(
                route_id=entry_route.id,
                start_time=time(8, 0),
                end_time=time(9, 0),
                type="entry",
                school_name=entry_route.school_name
            ),
            ScheduleItem(
                route_id=exit_route.id,
                start_time=time(14, 0),
                end_time=time(15, 0),
                type="exit",
                school_name=exit_route.school_name
            )
        ]
        schedule = BusSchedule(bus_id="BUS002", items=items)
        assert len(schedule.items) == 2
    
    def test_bus_schedule_optional_location(self):
        """Test bus schedule without last location."""
        schedule = BusSchedule(
            bus_id="BUS003",
            items=[],
            last_loc=None
        )
        assert schedule.last_loc is None
    
    def test_bus_schedule_serialization(self, sample_bus_schedule):
        """Test bus schedule serialization."""
        data = sample_bus_schedule.model_dump()
        assert data["bus_id"] == "BUS001"
        assert len(data["items"]) == 1


# ============================================================
# EDGE CASE TESTS
# ============================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_route_with_zero_capacity(self):
        """Test route with zero capacity."""
        route = Route(
            id="R_ZERO",
            name="Zero Capacity",
            stops=[],
            school_id="SCH001",
            school_name="Test",
            capacity_needed=0,
            contract_id="CNT001",
            type="entry"
        )
        assert route.capacity_needed == 0
    
    def test_stop_with_zero_coordinates(self):
        """Test stop with zero coordinates (invalid but accepted)."""
        stop = Stop(
            name="Zero Coords",
            lat=0.0,
            lon=0.0,
            order=1,
            time_from_start=0
        )
        assert stop.lat == 0.0
        assert stop.lon == 0.0
    
    def test_route_with_very_long_name(self):
        """Test route with very long name."""
        long_name = "A" * 1000
        route = Route(
            id="R_LONG",
            name=long_name,
            stops=[],
            school_id="SCH001",
            school_name="Test",
            capacity_needed=50,
            contract_id="CNT001",
            type="entry"
        )
        assert route.name == long_name
    
    def test_time_edge_cases(self):
        """Test time edge cases (midnight, noon)."""
        route = Route(
            id="R_TIME",
            name="Time Test",
            stops=[],
            school_id="SCH001",
            school_name="Test",
            arrival_time=time(0, 0),  # Midnight
            departure_time=time(12, 0),  # Noon
            capacity_needed=50,
            contract_id="CNT001",
            type="entry"
        )
        assert route.arrival_time == time(0, 0)
        assert route.departure_time == time(12, 0)
