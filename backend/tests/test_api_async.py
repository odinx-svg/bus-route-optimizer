"""
Tests for async optimization API endpoints.

Validates REST API endpoints for:
- Async job creation (/optimize-async)
- Job status retrieval (/jobs/{job_id})
- Job results retrieval (/jobs/{job_id}/result)
- Job cancellation (/jobs/{job_id})
- Celery task status (/tasks/{task_id})
"""

import pytest
import json
import uuid
from datetime import datetime, time
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock

from fastapi.testclient import TestClient


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_routes_async() -> List[Dict[str, Any]]:
    """Create sample routes for async tests (small set for speed)."""
    return [
        {
            "id": "R001_E",
            "name": "Route 1 Entry",
            "stops": [
                {"name": "Stop 1", "lat": 42.24, "lon": -8.72, "order": 1, 
                 "time_from_start": 0, "passengers": 5, "is_school": False},
                {"name": "School", "lat": 42.25, "lon": -8.73, "order": 2,
                 "time_from_start": 20, "passengers": 0, "is_school": True}
            ],
            "school_id": "SCH001",
            "school_name": "Colegio Test",
            "arrival_time": "08:00:00",
            "departure_time": None,
            "capacity_needed": 10,
            "contract_id": "CNT001",
            "type": "entry",
            "days": ["L", "M", "Mc", "X", "V"]
        },
        {
            "id": "R002_X",
            "name": "Route 2 Exit",
            "stops": [
                {"name": "Stop 1", "lat": 42.24, "lon": -8.72, "order": 1,
                 "time_from_start": 0, "passengers": 5, "is_school": False},
                {"name": "School", "lat": 42.25, "lon": -8.73, "order": 2,
                 "time_from_start": 25, "passengers": 0, "is_school": True}
            ],
            "school_id": "SCH001",
            "school_name": "Colegio Test",
            "arrival_time": None,
            "departure_time": "14:30:00",
            "capacity_needed": 10,
            "contract_id": "CNT001",
            "type": "exit",
            "days": ["L", "M", "Mc", "X", "V"]
        }
    ]


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    try:
        from main import app
        return TestClient(app)
    except ImportError:
        pytest.skip("Main app not available")


@pytest.fixture
def db_session():
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


# ============================================================
# TESTS - OPTIMIZE-ASYNC ENDPOINT
# ============================================================

class TestOptimizeAsync:
    """Test /optimize-async endpoint."""
    
    def test_optimize_async_creates_job(self, client, sample_routes_async):
        """Test POST /optimize-async creates a job."""
        response = client.post(
            "/optimize-async",
            json=sample_routes_async
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "job_id" in data
        assert "status" in data
        assert "websocket_url" in data
        
        # Verify values
        assert data["status"] in ["queued", "completed"]
        assert "/ws/optimize/" in data["websocket_url"]
        assert data["job_id"] in data["websocket_url"]
    
    def test_optimize_async_returns_task_id_when_celery_enabled(self, client, sample_routes_async):
        """Test that task_id is returned when Celery is enabled."""
        response = client.post(
            "/optimize-async",
            json=sample_routes_async
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # task_id may be None (sync mode) or a string (async mode)
        assert "task_id" in data
    
    def test_optimize_async_with_empty_routes(self, client):
        """Test POST /optimize-async with empty routes."""
        response = client.post(
            "/optimize-async",
            json=[]
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_optimize_async_with_invalid_data(self, client):
        """Test POST /optimize-async with invalid route data."""
        response = client.post(
            "/optimize-async",
            json=[{"invalid": "data"}]
        )
        
        # Should return validation error
        assert response.status_code in [400, 422]
    
    def test_optimize_async_saves_job_to_database(self, client, sample_routes_async, db_session):
        """Test that job is saved to database."""
        from db.models import OptimizationJob
        
        response = client.post(
            "/optimize-async",
            json=sample_routes_async
        )
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Verify job exists in database
        job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
        assert job is not None
        assert job.status in ["queued", "completed", "running"]
        assert job.algorithm == "v6"
        assert job.input_data is not None
        
        # Clean up
        db_session.delete(job)
        db_session.commit()


# ============================================================
# TESTS - GET JOB STATUS ENDPOINT
# ============================================================

class TestGetJobStatus:
    """Test GET /jobs/{job_id} endpoint."""
    
    def test_get_job_status_not_found(self, client):
        """Test GET /jobs/{job_id} with non-existent job."""
        response = client.get(f"/jobs/{uuid.uuid4()}")
        
        assert response.status_code == 404
    
    def test_get_job_status_success(self, client, db_session):
        """Test GET /jobs/{job_id} returns job status."""
        from db.models import OptimizationJob
        
        # Create a job
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="running",
            algorithm="v6",
            created_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.get(f"/jobs/{job_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["job_id"] == job_id
            assert data["status"] == "running"
            assert data["algorithm"] == "v6"
            assert "created_at" in data
            
        finally:
            # Clean up
            db_session.delete(job)
            db_session.commit()
    
    def test_get_job_status_completed(self, client, db_session):
        """Test GET /jobs/{job_id} for completed job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="completed",
            algorithm="v6",
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result={"schedule": [], "stats": {}},
            stats={"total_buses": 5}
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.get(f"/jobs/{job_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "completed"
            assert "completed_at" in data
            
        finally:
            db_session.delete(job)
            db_session.commit()
    
    def test_get_job_status_failed(self, client, db_session):
        """Test GET /jobs/{job_id} for failed job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="failed",
            algorithm="v6",
            created_at=datetime.utcnow(),
            error_message="Optimization failed"
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.get(f"/jobs/{job_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "failed"
            assert data["error"] == "Optimization failed"
            
        finally:
            db_session.delete(job)
            db_session.commit()


# ============================================================
# TESTS - GET JOB RESULT ENDPOINT
# ============================================================

class TestGetJobResult:
    """Test GET /jobs/{job_id}/result endpoint."""
    
    def test_get_job_result_not_found(self, client):
        """Test GET /jobs/{job_id}/result with non-existent job."""
        response = client.get(f"/jobs/{uuid.uuid4()}/result")
        
        assert response.status_code == 404
    
    def test_get_job_result_completed(self, client, db_session):
        """Test GET /jobs/{job_id}/result for completed job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        result_data = {
            "schedule": [
                {"bus_id": "BUS001", "items": []}
            ],
            "stats": {"total_buses": 1}
        }
        
        job = OptimizationJob(
            id=job_id,
            status="completed",
            algorithm="v6",
            created_at=datetime.utcnow(),
            result=result_data,
            stats={"total_buses": 1}
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.get(f"/jobs/{job_id}/result")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["job_id"] == job_id
            assert data["status"] == "completed"
            assert "result" in data
            assert data["result"] == result_data
            assert "stats" in data
            
        finally:
            db_session.delete(job)
            db_session.commit()
    
    def test_get_job_result_running(self, client, db_session):
        """Test GET /jobs/{job_id}/result for running job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="running",
            algorithm="v6",
            created_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.get(f"/jobs/{job_id}/result")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["job_id"] == job_id
            assert data["status"] == "running"
            
        finally:
            db_session.delete(job)
            db_session.commit()
    
    def test_get_job_result_failed(self, client, db_session):
        """Test GET /jobs/{job_id}/result for failed job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="failed",
            algorithm="v6",
            created_at=datetime.utcnow(),
            error_message="Optimization error"
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.get(f"/jobs/{job_id}/result")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "failed"
            assert data["error"] == "Optimization error"
            
        finally:
            db_session.delete(job)
            db_session.commit()


# ============================================================
# TESTS - CANCEL JOB ENDPOINT
# ============================================================

class TestCancelJob:
    """Test DELETE /jobs/{job_id} endpoint."""
    
    def test_cancel_job_not_found(self, client):
        """Test DELETE /jobs/{job_id} with non-existent job."""
        response = client.delete(f"/jobs/{uuid.uuid4()}")
        
        assert response.status_code == 404
    
    def test_cancel_job_queued(self, client, db_session):
        """Test canceling a queued job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="queued",
            algorithm="v6",
            created_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.delete(f"/jobs/{job_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["job_id"] == job_id
            assert data["status"] == "cancelled"
            assert "message" in data
            
            # Verify job was updated in database
            db_session.refresh(job)
            assert job.status == "cancelled"
            
        finally:
            db_session.delete(job)
            db_session.commit()
    
    def test_cancel_job_running(self, client, db_session):
        """Test canceling a running job."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="running",
            algorithm="v6",
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.delete(f"/jobs/{job_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "cancelled"
            
            db_session.refresh(job)
            assert job.status == "cancelled"
            
        finally:
            db_session.delete(job)
            db_session.commit()
    
    def test_cancel_completed_job_fails(self, client, db_session):
        """Test that canceling a completed job fails."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="completed",
            algorithm="v6",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.delete(f"/jobs/{job_id}")
            
            assert response.status_code == 400
            
            # Verify job status unchanged
            db_session.refresh(job)
            assert job.status == "completed"
            
        finally:
            db_session.delete(job)
            db_session.commit()
    
    def test_cancel_cancelled_job_fails(self, client, db_session):
        """Test that canceling an already cancelled job fails."""
        from db.models import OptimizationJob
        
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            status="cancelled",
            algorithm="v6",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db_session.add(job)
        db_session.commit()
        
        try:
            response = client.delete(f"/jobs/{job_id}")
            
            assert response.status_code == 400
            
        finally:
            db_session.delete(job)
            db_session.commit()


# ============================================================
# TESTS - GET TASK STATUS ENDPOINT
# ============================================================

class TestGetTaskStatus:
    """Test GET /tasks/{task_id} endpoint."""
    
    def test_get_task_status(self, client):
        """Test GET /tasks/{task_id}."""
        # Note: This requires Celery to be running
        # In test environment, may return 503 if Celery not available
        response = client.get("/tasks/test-task-id")
        
        # Either returns task status or 503 if Celery not available
        assert response.status_code in [200, 503]
    
    def test_get_task_status_invalid_id(self, client):
        """Test GET /tasks/{task_id} with invalid task ID."""
        response = client.get("/tasks/invalid-task-id")
        
        # Should handle gracefully
        assert response.status_code in [200, 404, 503]


# ============================================================
# TESTS - HEALTH CHECK
# ============================================================

class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test GET /health returns service status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ok"
        assert data["service"] == "tutti-backend"
        assert "services" in data


# ============================================================
# TESTS - FALLBACK SYNC MODE
# ============================================================

class TestFallbackSyncMode:
    """Test fallback to sync mode when Celery is disabled."""
    
    def test_optimize_async_fallback(self, client, sample_routes_async, monkeypatch):
        """Test that optimize-async works even when Celery is disabled."""
        # Disable Celery
        monkeypatch.setenv("CELERY_ENABLED", "false")
        
        response = client.post(
            "/optimize-async",
            json=sample_routes_async
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # In fallback mode, job should complete synchronously
        assert "job_id" in data
        assert data["status"] in ["queued", "completed"]


# ============================================================
# TESTS - WEBSOCKET URL GENERATION
# ============================================================

class TestWebSocketURL:
    """Test WebSocket URL generation."""
    
    def test_websocket_url_format(self, client, sample_routes_async):
        """Test that WebSocket URL follows expected format."""
        response = client.post(
            "/optimize-async",
            json=sample_routes_async
        )
        
        assert response.status_code == 200
        data = response.json()
        
        websocket_url = data["websocket_url"]
        job_id = data["job_id"]
        
        # URL should contain /ws/optimize/ and job_id
        assert websocket_url.startswith("/ws/optimize/")
        assert job_id in websocket_url
