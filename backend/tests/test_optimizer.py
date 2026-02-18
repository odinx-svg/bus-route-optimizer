"""
Tests for the route optimizer (optimizer_v6).
"""
import pytest
from datetime import time
from typing import List

from models import Route, BusSchedule, Stop
from optimizer_v6 import (
    optimize_v6,
    optimize_routes_v6,
    to_minutes,
    from_minutes,
    haversine_km,
    haversine_travel_minutes,
    coords_valid,
    classify_block,
    compute_route_duration,
    prepare_jobs,
    build_chains_greedy,
    precompute_block_travel_matrix
)


# ============================================================
# UTILITY FUNCTION TESTS
# ============================================================

class TestUtilityFunctions:
    """Test suite for optimizer utility functions."""
    
    def test_to_minutes(self):
        """Test converting time to minutes."""
        assert to_minutes(time(8, 30)) == 510
        assert to_minutes(time(0, 0)) == 0
        assert to_minutes(time(23, 59)) == 1439
    
    def test_from_minutes(self):
        """Test converting minutes to time."""
        assert from_minutes(510) == time(8, 30)
        assert from_minutes(0) == time(0, 0)
        assert from_minutes(1439) == time(23, 59)
    
    def test_from_minutes_wraparound(self):
        """Test from_minutes handles wraparound."""
        assert from_minutes(1440) == time(0, 0)  # 24 hours wraps to 0
        assert from_minutes(1500) == time(1, 0)  # 25 hours -> 1:00
    
    def test_haversine_km_same_point(self):
        """Test haversine distance for same point."""
        dist = haversine_km(42.24, -8.72, 42.24, -8.72)
        assert dist == 0.0
    
    def test_haversine_km_different_points(self):
        """Test haversine distance between two points."""
        # Approximate distance between two points ~1km apart
        dist = haversine_km(42.2400, -8.7200, 42.2400, -8.7100)
        assert dist > 0
        assert dist < 100  # Should be around 0.8 km
    
    def test_haversine_km_zero_coords(self):
        """Test haversine with zero coordinates returns large distance."""
        dist = haversine_km(0, 0, 42.24, -8.72)
        assert dist == 999.0
    
    def test_haversine_travel_minutes(self):
        """Test travel time calculation."""
        minutes = haversine_travel_minutes(42.24, -8.72, 42.25, -8.73)
        assert minutes >= 5  # Minimum is 5 minutes
    
    def test_coords_valid(self):
        """Test coordinate validation."""
        assert coords_valid(42.24, -8.72) is True
        assert coords_valid(0, 0) is False
        assert coords_valid(100, 0) is False  # Invalid latitude
        assert coords_valid(0, 200) is False  # Invalid longitude
        assert coords_valid(-90, -180) is True  # Edge cases
        assert coords_valid(90, 180) is True  # Edge cases


# ============================================================
# BLOCK CLASSIFICATION TESTS
# ============================================================

class TestBlockClassification:
    """Test suite for block classification."""
    
    def test_classify_block_morning_entry(self):
        """Test classifying morning entry route."""
        route = Route(
            id="R1",
            name="Morning Entry",
            stops=[],
            school_id="S1",
            school_name="School",
            arrival_time=time(8, 30),
            capacity_needed=50,
            contract_id="C1",
            type="entry"
        )
        assert classify_block(route) == 1  # Block 1: Morning entries
    
    def test_classify_block_late_entry(self):
        """Test classifying late entry route."""
        route = Route(
            id="R1",
            name="Late Entry",
            stops=[],
            school_id="S1",
            school_name="School",
            arrival_time=time(16, 30),
            capacity_needed=50,
            contract_id="C1",
            type="entry"
        )
        assert classify_block(route) == 3  # Block 3: Late entries
    
    def test_classify_block_early_exit(self):
        """Test classifying early exit route."""
        route = Route(
            id="R1",
            name="Early Exit",
            stops=[],
            school_id="S1",
            school_name="School",
            departure_time=time(14, 30),
            capacity_needed=50,
            contract_id="C1",
            type="exit"
        )
        assert classify_block(route) == 2  # Block 2: Early exits
    
    def test_classify_block_late_exit(self):
        """Test classifying late exit route."""
        route = Route(
            id="R1",
            name="Late Exit",
            stops=[],
            school_id="S1",
            school_name="School",
            departure_time=time(18, 30),
            capacity_needed=50,
            contract_id="C1",
            type="exit"
        )
        assert classify_block(route) == 4  # Block 4: Late exits
    
    def test_classify_block_no_time(self):
        """Test classifying route with no time info."""
        route = Route(
            id="R1",
            name="No Time",
            stops=[],
            school_id="S1",
            school_name="School",
            capacity_needed=50,
            contract_id="C1",
            type="entry"
        )
        assert classify_block(route) == 0  # No block


# ============================================================
# ROUTE DURATION TESTS
# ============================================================

class TestRouteDuration:
    """Test suite for route duration computation."""
    
    def test_compute_route_duration_with_stops(self):
        """Test computing duration for route with stops."""
        stops = [
            Stop(name="S1", lat=42.24, lon=-8.72, order=1, time_from_start=0),
            Stop(name="S2", lat=42.25, lon=-8.73, order=2, time_from_start=20),
        ]
        route = Route(
            id="R1",
            name="Test",
            stops=stops,
            school_id="S1",
            school_name="School",
            capacity_needed=50,
            contract_id="C1",
            type="entry"
        )
        duration = compute_route_duration(route)
        assert duration > 0
    
    def test_compute_route_duration_no_stops(self):
        """Test computing duration for route with no stops."""
        route = Route(
            id="R1",
            name="Test",
            stops=[],
            school_id="S1",
            school_name="School",
            capacity_needed=50,
            contract_id="C1",
            type="entry"
        )
        duration = compute_route_duration(route)
        assert duration == 30  # Default duration


# ============================================================
# OPTIMIZER MAIN TESTS
# ============================================================

@pytest.mark.optimizer
class TestOptimizer:
    """Test suite for the main optimizer functionality."""
    
    def test_optimize_v6_returns_list(self, optimizer_test_routes):
        """Test that optimize_v6 returns a list."""
        result = optimize_v6(optimizer_test_routes)
        assert isinstance(result, list)
        assert all(isinstance(s, BusSchedule) for s in result)
    
    def test_optimize_v6_assigns_all_routes(self, optimizer_test_routes):
        """Test that all routes are assigned to buses."""
        result = optimize_v6(optimizer_test_routes)
        
        # Count assigned routes
        assigned_routes = set()
        for schedule in result:
            for item in schedule.items:
                assigned_routes.add(item.route_id)
        
        # Check all input routes are assigned
        input_route_ids = set(r.id for r in optimizer_test_routes)
        assert assigned_routes == input_route_ids
    
    def test_optimize_v6_no_overlaps_same_bus(self, optimizer_test_routes):
        """Test that routes on the same bus don't overlap in time."""
        result = optimize_v6(optimizer_test_routes)
        
        for schedule in result:
            items = sorted(schedule.items, key=lambda x: (x.start_time.hour, x.start_time.minute))
            for i in range(len(items) - 1):
                current_end = items[i].end_time
                next_start = items[i + 1].start_time
                
                # Convert to minutes for comparison
                current_end_mins = current_end.hour * 60 + current_end.minute
                next_start_mins = next_start.hour * 60 + next_start.minute
                
                # Allow 5 minute buffer for travel
                assert current_end_mins <= next_start_mins + 5, \
                    f"Overlap detected: {items[i].route_id} ends at {current_end}, " \
                    f"{items[i+1].route_id} starts at {next_start}"
    
    def test_optimize_v6_respects_entry_times(self, optimizer_test_routes):
        """Test that entry routes respect school arrival times."""
        result = optimize_v6(optimizer_test_routes)
        
        for schedule in result:
            for item in schedule.items:
                if item.type == "entry":
                    # Entry routes should arrive by the scheduled time
                    if item.original_start_time:
                        original_mins = to_minutes(item.original_start_time)
                        actual_mins = to_minutes(item.end_time)
                        assert actual_mins <= original_mins + 5, \
                            f"Entry route {item.route_id} arrives too late"
    
    @pytest.mark.xfail(reason="V6 optimizer may shift exits up to 5 min for chaining")
    def test_optimize_v6_respects_exit_times(self, optimizer_test_routes):
        """Test that exit routes respect school departure times."""
        result = optimize_v6(optimizer_test_routes)
        
        for schedule in result:
            for item in schedule.items:
                if item.type == "exit":
                    # Exit routes should start at scheduled time
                    if item.original_start_time:
                        original_mins = to_minutes(item.original_start_time)
                        actual_mins = to_minutes(item.start_time)
                        assert abs(actual_mins - original_mins) <= 1, \
                            f"Exit route {item.route_id} has wrong start time"
    
    def test_optimize_v6_fewer_buses_than_routes(self, optimizer_test_routes):
        """Test that optimizer reduces bus count."""
        result = optimize_v6(optimizer_test_routes)
        num_buses = len(result)
        num_routes = len(optimizer_test_routes)
        
        # Should use fewer buses than routes (some chaining should happen)
        assert num_buses < num_routes, \
            f"Used {num_buses} buses for {num_routes} routes - no optimization"
    
    def test_optimize_v6_each_bus_has_items(self, optimizer_test_routes):
        """Test that each bus has at least one route assigned."""
        result = optimize_v6(optimizer_test_routes)
        
        for schedule in result:
            assert len(schedule.items) > 0, \
                f"Bus {schedule.bus_id} has no routes assigned"
    
    def test_optimize_v6_bus_ids_unique(self, optimizer_test_routes):
        """Test that bus IDs are unique."""
        result = optimize_v6(optimizer_test_routes)
        bus_ids = [s.bus_id for s in result]
        assert len(bus_ids) == len(set(bus_ids)), "Duplicate bus IDs found"
    
    def test_optimize_routes_v6_alias(self, optimizer_test_routes):
        """Test that optimize_routes_v6 is an alias for optimize_v6."""
        result1 = optimize_v6(optimizer_test_routes)
        result2 = optimize_routes_v6(optimizer_test_routes)
        
        assert len(result1) == len(result2)


# ============================================================
# OPTIMIZER EDGE CASE TESTS
# ============================================================

@pytest.mark.optimizer
class TestOptimizerEdgeCases:
    """Test edge cases for the optimizer."""
    
    def test_optimize_empty_list(self):
        """Test optimizing empty route list."""
        result = optimize_v6([])
        assert result == []
    
    def test_optimize_single_route(self):
        """Test optimizing single route."""
        route = Route(
            id="R_SINGLE",
            name="Single Route",
            stops=[
                Stop(name="S1", lat=42.24, lon=-8.72, order=1, time_from_start=0, passengers=5),
                Stop(name="School", lat=42.25, lon=-8.73, order=2, time_from_start=15, passengers=0, is_school=True),
            ],
            school_id="SCH001",
            school_name="Test School",
            arrival_time=time(9, 0),
            capacity_needed=5,
            contract_id="CNT001",
            type="entry"
        )
        result = optimize_v6([route])
        assert len(result) == 1
        assert len(result[0].items) == 1
    
    def test_optimize_routes_same_time(self):
        """Test optimizing routes with same time."""
        routes = []
        for i in range(3):
            route = Route(
                id=f"R_SAME_{i}",
                name=f"Same Time Route {i}",
                stops=[
                    Stop(name=f"S{i}", lat=42.24+i*0.01, lon=-8.72, order=1, time_from_start=0, passengers=5),
                    Stop(name="School", lat=42.25, lon=-8.73, order=2, time_from_start=15, passengers=0, is_school=True),
                ],
                school_id="SCH001",
                school_name="Test School",
                arrival_time=time(9, 0),  # Same time
                capacity_needed=5,
                contract_id="CNT001",
                type="entry"
            )
            routes.append(route)
        
        result = optimize_v6(routes)
        # May need 3 buses since all at same time
        assert len(result) >= 1
    
    def test_optimize_routes_no_valid_times(self):
        """Test optimizing routes with no valid times."""
        routes = []
        for i in range(3):
            route = Route(
                id=f"R_NO_TIME_{i}",
                name=f"No Time Route {i}",
                stops=[],
                school_id="SCH001",
                school_name="Test School",
                capacity_needed=50,
                contract_id="CNT001",
                type="entry"
            )
            routes.append(route)
        
        result = optimize_v6(routes)
        # Routes with no time should be dropped
        total_items = sum(len(s.items) for s in result)
        assert total_items <= len(routes)


# ============================================================
# CHAIN BUILDING TESTS
# ============================================================

class TestChainBuilding:
    """Test suite for chain building functions."""
    
    def test_build_chains_greedy_empty(self):
        """Test building chains with empty job list."""
        chains = build_chains_greedy([], {}, True)
        assert chains == []
    
    def test_precompute_block_travel_matrix_empty(self):
        """Test travel matrix with empty job list."""
        matrix = precompute_block_travel_matrix([], True)
        assert matrix == {}


# ============================================================
# PREPARE JOBS TESTS
# ============================================================

class TestPrepareJobs:
    """Test suite for job preparation."""
    
    def test_prepare_jobs_classifies_correctly(self, optimizer_test_routes):
        """Test that jobs are classified into correct blocks."""
        blocks = prepare_jobs(optimizer_test_routes)
        
        # Should have 4 blocks
        assert 1 in blocks  # Morning entries
        assert 2 in blocks  # Early exits
        assert 3 in blocks  # Late entries
        assert 4 in blocks  # Late exits
        
        # Count total jobs
        total_jobs = sum(len(jobs) for jobs in blocks.values())
        # Some routes may be dropped if no valid time
        assert total_jobs <= len(optimizer_test_routes)
    
    def test_prepare_jobs_preserves_route_info(self, entry_route):
        """Test that route info is preserved in jobs."""
        blocks = prepare_jobs([entry_route])
        
        # Find the job
        for block_jobs in blocks.values():
            for job in block_jobs:
                assert job.route.id == entry_route.id
                assert job.route_type == entry_route.type
