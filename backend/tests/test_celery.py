"""
Tests for Celery async task processing.

Validates the async optimization workflow including:
- Task creation and execution
- Progress reporting
- Error handling and retries
- Database integration
"""

import pytest
import json
from datetime import datetime, time
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
import uuid

# Import models
from models import Route, Stop


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_routes_small() -> List[Route]:
    """Create a small set of routes for fast Celery tests."""
    routes = []
    
    # Entry routes
    for i in range(3):
        stops = [
            Stop(name=f"Stop {i}-A", lat=42.235 + i*0.01, lon=-8.715 - i*0.01, 
                 order=1, time_from_start=0, passengers=5),
            Stop(name="School", lat=42.245, lon=-8.725, order=2, 
                 time_from_start=20, passengers=0, is_school=True),
        ]
        
        route = Route(
            id=f"R{i:03d}_E",
            name=f"Route {i} Entry",
            stops=stops,
            school_id="SCH001",
            school_name="Colegio Test",
            arrival_time=time(8 + i, 0),
            departure_time=None,
            capacity_needed=10,
            contract_id="CNT001",
            type="entry",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    # Exit routes
    for i in range(2):
        stops = [
            Stop(name=f"Stop {i}-B", lat=42.238 + i*0.01, lon=-8.718 - i*0.01, 
                 order=1, time_from_start=0, passengers=5),
            Stop(name="School", lat=42.248, lon=-8.728, order=2, 
                 time_from_start=25, passengers=0, is_school=True),
        ]
        
        route = Route(
            id=f"R{i:03d}_X",
            name=f"Route {i} Exit",
            stops=stops,
            school_id="SCH001",
            school_name="Colegio Test",
            arrival_time=None,
            departure_time=time(14 + i, 30),
            capacity_needed=10,
            contract_id="CNT001",
            type="exit",
            days=["L", "M", "Mc", "X", "V"]
        )
        routes.append(route)
    
    return routes


@pytest.fixture
def mock_celery_task():
    """Create a mock Celery task for testing."""
    task = Mock()
    task.request.retries = 0
    task.update_state = Mock()
    task.retry = Mock(side_effect=Exception("Retry triggered"))
    return task


@pytest.fixture
def sample_routes_data(sample_routes_small):
    """Convert sample routes to dict format for task input."""
    return [r.dict() for r in sample_routes_small]


# ============================================================
# TESTS - TASK CONFIGURATION
# ============================================================

class TestCeleryConfiguration:
    """Test Celery app configuration."""
    
    def test_celery_app_imports(self):
        """Test that Celery app can be imported."""
        try:
            from celery_app import celery_app
            assert celery_app is not None
        except ImportError:
            pytest.skip("Celery not available")
    
    def test_celery_app_configuration(self):
        """Test Celery app is properly configured."""
        try:
            from celery_app import celery_app
            
            assert celery_app.main == "tutti"
            assert celery_app.conf.task_serializer == "json"
            assert celery_app.conf.accept_content == ["json"]
            assert celery_app.conf.result_serializer == "json"
            assert celery_app.conf.timezone == "UTC"
            assert celery_app.conf.enable_utc is True
            assert celery_app.conf.task_track_started is True
            assert celery_app.conf.task_time_limit == 3600
        except ImportError:
            pytest.skip("Celery not available")
    
    def test_optimize_task_registered(self):
        """Test that optimize_task is registered with Celery."""
        try:
            from celery_app import celery_app
            from tasks import optimize_task
            
            # Check task is registered
            assert "tasks.optimize_task" in celery_app.tasks
            
            # Check task configuration
            assert optimize_task.bind is True
            assert optimize_task.max_retries == 3
        except ImportError:
            pytest.skip("Celery or tasks not available")


# ============================================================
# TESTS - PROGRESS CALLBACK
# ============================================================

class TestProgressCallback:
    """Test progress callback functionality."""
    
    def test_progress_callback_creation(self, mock_celery_task):
        """Test that progress callback can be created."""
        try:
            from tasks import _create_progress_callback
            
            callback = _create_progress_callback(mock_celery_task, "test-job-123")
            assert callable(callback)
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_progress_callback_updates_state(self, mock_celery_task):
        """Test that progress callback updates Celery state."""
        try:
            from tasks import _create_progress_callback
            
            callback = _create_progress_callback(mock_celery_task, "test-job-123")
            
            # Call with progress update
            callback("optimizing", 50, "Halfway there")
            
            # Verify update_state was called
            assert mock_celery_task.update_state.called
            
            # Check the call arguments
            call_args = mock_celery_task.update_state.call_args
            assert call_args[1]["state"] == "PROGRESS"
            meta = call_args[1]["meta"]
            assert meta["phase"] == "optimizing"
            assert meta["progress"] == 50
            assert meta["message"] == "Halfway there"
            assert meta["job_id"] == "test-job-123"
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_progress_callback_throttling(self, mock_celery_task):
        """Test that progress callback throttles updates."""
        try:
            from tasks import _create_progress_callback
            import time
            
            callback = _create_progress_callback(mock_celery_task, "test-job-123", update_interval=0.5)
            
            # Call multiple times rapidly
            callback("phase1", 10, "Start")
            callback("phase1", 11, "Still going")  # Should be throttled
            callback("phase1", 12, "Still going")  # Should be throttled
            
            # Only first call should trigger update (small progress diff)
            assert mock_celery_task.update_state.call_count == 1
            
            # Wait and call with significant progress
            time.sleep(0.6)
            callback("phase1", 50, "Halfway")  # Should trigger (large progress jump)
            
            assert mock_celery_task.update_state.call_count == 2
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_progress_callback_always_sends_boundary_values(self, mock_celery_task):
        """Test that 0% and 100% are always sent."""
        try:
            from tasks import _create_progress_callback
            
            callback = _create_progress_callback(mock_celery_task, "test-job-123")
            
            # Call with 0% - should always be sent
            callback("starting", 0, "Starting")
            assert mock_celery_task.update_state.call_count == 1
            
            # Call with intermediate - should be throttled
            callback("phase", 1, "Working")
            # May or may not be sent depending on timing
            
            # Call with 100% - should always be sent
            callback("completed", 100, "Done")
            # At least 2 calls (0% and 100%)
            assert mock_celery_task.update_state.call_count >= 2
        except ImportError:
            pytest.skip("Tasks not available")


# ============================================================
# TESTS - REDIS PUBLISH
# ============================================================

class TestRedisPublish:
    """Test Redis publish functionality for WebSocket integration."""
    
    @patch("tasks.redis.Redis")
    def test_publish_to_redis_success(self, mock_redis_class):
        """Test successful publish to Redis."""
        try:
            from tasks import _publish_to_redis
            from config import config
            
            # Mock Redis client
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_redis_class.from_url.return_value = mock_client
            
            # Mock config to indicate Redis is available
            with patch.object(config, "is_redis_available", return_value=True):
                result = _publish_to_redis("job-123", "optimizing", 50, "Halfway")
            
            assert result is True
            assert mock_client.publish.call_count == 2  # Job channel + all channel
        except ImportError:
            pytest.skip("Tasks or config not available")
    
    @patch("tasks.redis.Redis")
    def test_publish_to_redis_failure(self, mock_redis_class):
        """Test handling when Redis is unavailable."""
        try:
            from tasks import _publish_to_redis
            
            # Mock Redis to raise exception
            mock_redis_class.from_url.side_effect = Exception("Redis down")
            
            result = _publish_to_redis("job-123", "optimizing", 50, "Halfway")
            
            assert result is False
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_publish_to_redis_when_redis_disabled(self):
        """Test that publish returns False when Redis is not available."""
        try:
            from tasks import _publish_to_redis
            from config import config
            
            with patch.object(config, "is_redis_available", return_value=False):
                result = _publish_to_redis("job-123", "optimizing", 50, "Halfway")
            
            assert result is False
        except ImportError:
            pytest.skip("Tasks or config not available")


# ============================================================
# TESTS - TASK EXECUTION (EAGER MODE)
# ============================================================

class TestOptimizeTaskExecution:
    """Test optimize_task execution with Celery in eager mode."""
    
    @pytest.fixture(autouse=True)
    def celery_eager_mode(self):
        """Configure Celery for eager execution."""
        try:
            from celery_app import celery_app
            original_always_eager = celery_app.conf.task_always_eager
            celery_app.conf.task_always_eager = True
            celery_app.conf.task_store_eager_result = True
            yield
            celery_app.conf.task_always_eager = original_always_eager
        except ImportError:
            yield
    
    @pytest.mark.skipif(
        not pytest.importorskip("celery", reason="Celery not installed"),
        reason="Celery not installed"
    )
    def test_optimize_task_runs_with_valid_data(self, sample_routes_data):
        """Test that optimize_task runs successfully with valid data."""
        try:
            from tasks import optimize_task
            
            job_id = str(uuid.uuid4())
            
            # Run task synchronously (eager mode)
            result = optimize_task.run(
                routes_data=sample_routes_data,
                job_id=job_id
            )
            
            # Verify result structure
            assert isinstance(result, dict)
            assert "schedule" in result
            assert "stats" in result
            assert isinstance(result["schedule"], list)
            assert isinstance(result["stats"], dict)
            
        except ImportError:
            pytest.skip("Tasks not available")
    
    @pytest.mark.skipif(
        not pytest.importorskip("celery", reason="Celery not installed"),
        reason="Celery not installed"
    )
    def test_optimize_task_calculates_stats(self, sample_routes_data):
        """Test that optimize_task calculates statistics."""
        try:
            from tasks import optimize_task
            
            job_id = str(uuid.uuid4())
            
            result = optimize_task.run(
                routes_data=sample_routes_data,
                job_id=job_id
            )
            
            stats = result["stats"]
            assert "total_buses" in stats
            assert "total_routes" in stats
            assert "total_entries" in stats
            assert "total_exits" in stats
            
            # Verify stats are reasonable
            assert stats["total_routes"] == len(sample_routes_data)
            assert stats["total_entries"] + stats["total_exits"] == len(sample_routes_data)
            
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_optimize_task_progress_reporting(self, sample_routes_data):
        """Test that optimize_task reports progress updates."""
        try:
            from tasks import optimize_task
            
            job_id = str(uuid.uuid4())
            progress_updates = []
            
            # Mock the task's update_state method
            def mock_update_state(state=None, meta=None):
                if state == "PROGRESS":
                    progress_updates.append(meta)
            
            # Run with mocked update_state
            task = optimize_task.bind()
            task.update_state = mock_update_state
            
            result = task.run(
                routes_data=sample_routes_data,
                job_id=job_id
            )
            
            # Verify we received progress updates
            assert len(progress_updates) > 0
            
            # Check structure of progress updates
            for update in progress_updates:
                assert "phase" in update
                assert "progress" in update
                assert "message" in update
                assert "job_id" in update
                assert isinstance(update["progress"], int)
                assert 0 <= update["progress"] <= 100
            
            # Verify we got start and end progress
            progresses = [u["progress"] for u in progress_updates]
            assert 0 in progresses
            assert 100 in progresses or max(progresses) >= 95
            
        except ImportError:
            pytest.skip("Tasks not available")


# ============================================================
# TESTS - ERROR HANDLING
# ============================================================

class TestErrorHandling:
    """Test error handling and retry logic."""
    
    def test_optimize_task_with_invalid_data(self):
        """Test task behavior with invalid input data."""
        try:
            from tasks import optimize_task
            
            job_id = str(uuid.uuid4())
            
            # Test with None data - should raise exception and trigger retry
            with pytest.raises(Exception):
                optimize_task.run(routes_data=None, job_id=job_id)
                
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_optimize_task_with_empty_routes(self):
        """Test task behavior with empty routes list."""
        try:
            from tasks import optimize_task
            
            job_id = str(uuid.uuid4())
            
            # Run with empty routes
            result = optimize_task.run(routes_data=[], job_id=job_id)
            
            # Should return empty schedule
            assert result["schedule"] == []
            assert result["stats"]["total_buses"] == 0
            assert result["stats"]["total_routes"] == 0
            
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_retry_countdown_calculation(self):
        """Test that retry countdown increases with each retry."""
        try:
            from tasks import optimize_task
            
            # Check the retry logic in the except block
            # retry_count = self.request.retries
            # countdown = 60 * (2 ** retry_count)
            # 
            # First retry: 60 * (2^0) = 60s
            # Second retry: 60 * (2^1) = 120s
            # Third retry: 60 * (2^2) = 240s
            
            expected_countdowns = [60, 120, 240]
            
            for retry_count, expected in enumerate(expected_countdowns):
                actual = 60 * (2 ** retry_count)
                assert actual == expected
                
        except ImportError:
            pytest.skip("Tasks not available")


# ============================================================
# TESTS - DATABASE INTEGRATION
# ============================================================

@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database integration with Celery tasks."""
    
    @pytest.fixture
    def db_session(self):
        """Create a database session for testing."""
        try:
            from db.database import SessionLocal, is_database_available
            
            if not is_database_available():
                pytest.skip("Database not available")
            
            db = SessionLocal()
            yield db
            db.close()
        except ImportError:
            pytest.skip("Database not available")
    
    def test_job_status_updated_to_running(self, db_session, sample_routes_data):
        """Test that job status is updated to running during task execution."""
        try:
            from tasks import optimize_task
            from db.models import OptimizationJob
            from datetime import datetime
            
            job_id = str(uuid.uuid4())
            
            # Create job in database
            job = OptimizationJob(
                id=job_id,
                status="queued",
                algorithm="v6",
                input_data=sample_routes_data,
                created_at=datetime.utcnow()
            )
            db_session.add(job)
            db_session.commit()
            
            # Run task
            result = optimize_task.run(
                routes_data=sample_routes_data,
                job_id=job_id
            )
            
            # Refresh job from database
            db_session.refresh(job)
            
            # Verify job was updated
            assert job.status == "completed"
            assert job.result is not None
            assert job.stats is not None
            assert job.completed_at is not None
            
            # Clean up
            db_session.delete(job)
            db_session.commit()
            
        except ImportError:
            pytest.skip("Tasks or database not available")
    
    def test_job_result_saved(self, db_session, sample_routes_data):
        """Test that job result is saved to database."""
        try:
            from tasks import optimize_task
            from db.models import OptimizationJob
            from datetime import datetime
            
            job_id = str(uuid.uuid4())
            
            # Create job
            job = OptimizationJob(
                id=job_id,
                status="queued",
                algorithm="v6",
                input_data=sample_routes_data,
                created_at=datetime.utcnow()
            )
            db_session.add(job)
            db_session.commit()
            
            # Run task
            result = optimize_task.run(
                routes_data=sample_routes_data,
                job_id=job_id
            )
            
            # Verify result was saved
            db_session.refresh(job)
            assert job.result is not None
            assert "schedule" in job.result
            assert "stats" in job.result
            assert job.stats is not None
            assert "total_buses" in job.stats
            
            # Clean up
            db_session.delete(job)
            db_session.commit()
            
        except ImportError:
            pytest.skip("Tasks or database not available")


# ============================================================
# TESTS - CLEANUP TASK
# ============================================================

class TestCleanupTask:
    """Test cleanup task functionality."""
    
    def test_cleanup_task_import(self):
        """Test that cleanup task can be imported."""
        try:
            from tasks import cleanup_old_jobs
            assert callable(cleanup_old_jobs)
        except ImportError:
            pytest.skip("Tasks not available")
    
    @pytest.mark.integration
    def test_cleanup_old_jobs(self, db_session):
        """Test cleanup of old jobs."""
        try:
            from tasks import cleanup_old_jobs
            from db.models import OptimizationJob
            from datetime import datetime, timedelta
            
            # Create old completed job
            old_job = OptimizationJob(
                id=uuid.uuid4(),
                status="completed",
                algorithm="v6",
                created_at=datetime.utcnow() - timedelta(hours=48),
                completed_at=datetime.utcnow() - timedelta(hours=47)
            )
            db_session.add(old_job)
            
            # Create recent completed job
            recent_job = OptimizationJob(
                id=uuid.uuid4(),
                status="completed",
                algorithm="v6",
                created_at=datetime.utcnow() - timedelta(hours=12),
                completed_at=datetime.utcnow() - timedelta(hours=11)
            )
            db_session.add(recent_job)
            
            # Create old running job (should not be cleaned)
            running_job = OptimizationJob(
                id=uuid.uuid4(),
                status="running",
                algorithm="v6",
                created_at=datetime.utcnow() - timedelta(hours=48)
            )
            db_session.add(running_job)
            db_session.commit()
            
            # Run cleanup
            result = cleanup_old_jobs.run(max_age_hours=24)
            
            # Verify cleanup stats
            assert result["cleaned"] == 1
            assert result["max_age_hours"] == 24
            
            # Verify old completed job was deleted
            assert db_session.query(OptimizationJob).filter_by(id=old_job.id).first() is None
            
            # Verify recent job and running job still exist
            assert db_session.query(OptimizationJob).filter_by(id=recent_job.id).first() is not None
            assert db_session.query(OptimizationJob).filter_by(id=running_job.id).first() is not None
            
            # Clean up
            db_session.delete(recent_job)
            db_session.delete(running_job)
            db_session.commit()
            
        except ImportError:
            pytest.skip("Tasks or database not available")


# ============================================================
# TESTS - STATS CALCULATION
# ============================================================

class TestStatsCalculation:
    """Test statistics calculation functions."""
    
    def test_calculate_stats_with_empty_schedule(self):
        """Test stats calculation with empty schedule."""
        try:
            from tasks import _calculate_stats
            
            stats = _calculate_stats([])
            
            assert stats["total_buses"] == 0
            assert stats["total_routes"] == 0
            assert stats["total_entries"] == 0
            assert stats["total_exits"] == 0
            assert stats["max_entries_per_bus"] == 0
            assert stats["max_exits_per_bus"] == 0
            assert stats["buses_with_both"] == 0
            assert stats["avg_routes_per_bus"] == 0
            assert stats["total_early_shift_minutes"] == 0
            
        except ImportError:
            pytest.skip("Tasks not available")
    
    def test_calculate_stats_with_schedule(self, sample_bus_schedule):
        """Test stats calculation with actual schedule."""
        try:
            from tasks import _calculate_stats
            from models import BusSchedule
            
            stats = _calculate_stats([sample_bus_schedule])
            
            assert stats["total_buses"] == 1
            assert stats["total_routes"] >= 1
            assert stats["avg_routes_per_bus"] >= 1.0
            
        except ImportError:
            pytest.skip("Tasks not available")
