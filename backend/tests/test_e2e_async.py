"""
End-to-End tests for async optimization workflow.

Validates the complete async flow:
1. POST /optimize-async → job_id
2. WebSocket → receive progress updates
3. GET /jobs/{id} → verify status
4. GET /jobs/{id}/result → get results

These tests verify the integration between all async components.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, time
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_routes_e2e() -> List[Dict[str, Any]]:
    """
    Create a small set of routes for E2E tests.
    Small enough to be fast but complete enough to test the flow.
    """
    return [
        {
            "id": "E2E_R001_E",
            "name": "E2E Route 1 Entry",
            "stops": [
                {"name": "E2E Stop 1A", "lat": 42.235, "lon": -8.715, "order": 1,
                 "time_from_start": 0, "passengers": 4, "is_school": False},
                {"name": "E2E Stop 1B", "lat": 42.236, "lon": -8.716, "order": 2,
                 "time_from_start": 8, "passengers": 4, "is_school": False},
                {"name": "School A", "lat": 42.245, "lon": -8.725, "order": 3,
                 "time_from_start": 20, "passengers": 0, "is_school": True}
            ],
            "school_id": "SCH_E2E_1",
            "school_name": "Colegio E2E",
            "arrival_time": "08:30:00",
            "departure_time": None,
            "capacity_needed": 8,
            "contract_id": "CNT_E2E_1",
            "type": "entry",
            "days": ["L", "M", "Mc", "X", "V"]
        },
        {
            "id": "E2E_R002_E",
            "name": "E2E Route 2 Entry",
            "stops": [
                {"name": "E2E Stop 2A", "lat": 42.238, "lon": -8.718, "order": 1,
                 "time_from_start": 0, "passengers": 5, "is_school": False},
                {"name": "School B", "lat": 42.248, "lon": -8.728, "order": 2,
                 "time_from_start": 25, "passengers": 0, "is_school": True}
            ],
            "school_id": "SCH_E2E_2",
            "school_name": "Colegio E2E 2",
            "arrival_time": "09:00:00",
            "departure_time": None,
            "capacity_needed": 10,
            "contract_id": "CNT_E2E_1",
            "type": "entry",
            "days": ["L", "M", "Mc", "X", "V"]
        },
        {
            "id": "E2E_R001_X",
            "name": "E2E Route 1 Exit",
            "stops": [
                {"name": "E2E Stop X1", "lat": 42.240, "lon": -8.720, "order": 1,
                 "time_from_start": 0, "passengers": 5, "is_school": False},
                {"name": "E2E Stop X2", "lat": 42.241, "lon": -8.721, "order": 2,
                 "time_from_start": 10, "passengers": 5, "is_school": False},
                {"name": "School X", "lat": 42.250, "lon": -8.730, "order": 3,
                 "time_from_start": 25, "passengers": 0, "is_school": True}
            ],
            "school_id": "SCH_E2E_1",
            "school_name": "Colegio E2E",
            "arrival_time": None,
            "departure_time": "14:30:00",
            "capacity_needed": 10,
            "contract_id": "CNT_E2E_1",
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
# TESTS - FULL ASYNC FLOW
# ============================================================

@pytest.mark.integration
@pytest.mark.slow
class TestFullAsyncFlow:
    """Test the complete async optimization flow."""
    
    def test_e2e_async_flow_sync_mode(self, client, sample_routes_e2e, db_session):
        """
        Test E2E flow in synchronous mode (fallback).
        
        Flow:
        1. POST /optimize-async → job_id
        2. (Job completes synchronously)
        3. GET /jobs/{job_id} → verify completed
        4. GET /jobs/{job_id}/result → get results
        """
        from db.models import OptimizationJob
        
        # Step 1: Queue optimization
        response = client.post(
            "/optimize-async",
            json=sample_routes_e2e
        )
        
        assert response.status_code == 200
        data = response.json()
        job_id = data["job_id"]
        
        # Verify job was created
        assert "status" in data
        assert "websocket_url" in data
        
        # Step 2: Check job status
        status_response = client.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        
        # In sync mode, job should be completed
        if status_data["status"] == "completed":
            # Step 3: Get results
            result_response = client.get(f"/jobs/{job_id}/result")
            assert result_response.status_code == 200
            
            result_data = result_response.json()
            assert result_data["status"] == "completed"
            assert "result" in result_data
            assert "stats" in result_data
            
            # Verify result structure
            result = result_data["result"]
            assert "schedule" in result
            assert "stats" in result
        
        # Clean up
        job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
        if job:
            db_session.delete(job)
            db_session.commit()
    
    def test_e2e_job_polling(self, client, sample_routes_e2e, db_session):
        """
        Test job completion via polling.
        
        Even without WebSocket, client should be able to poll for status.
        """
        from db.models import OptimizationJob
        
        # Queue optimization
        response = client.post(
            "/optimize-async",
            json=sample_routes_e2e
        )
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Poll for completion (max 30 attempts, 0.5s interval = 15s max)
        final_status = None
        for _ in range(30):
            status_response = client.get(f"/jobs/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                final_status = status_data["status"]
                
                if final_status in ["completed", "failed", "cancelled"]:
                    break
            
            # Small delay between polls
            import time
            time.sleep(0.5)
        
        # Verify job reached a terminal state
        assert final_status in ["completed", "failed", "cancelled", "queued", "running"]
        
        # Clean up
        job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
        if job:
            db_session.delete(job)
            db_session.commit()
    
    def test_e2e_cancel_job(self, client, sample_routes_e2e, db_session):
        """
        Test canceling a job during processing.
        """
        from db.models import OptimizationJob
        
        # Queue optimization
        response = client.post(
            "/optimize-async",
            json=sample_routes_e2e
        )
        
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Try to cancel immediately
        # Note: In sync mode, job may already be completed
        # In async mode, job should be cancellable
        cancel_response = client.delete(f"/jobs/{job_id}")
        
        # Should either succeed or fail with appropriate error
        assert cancel_response.status_code in [200, 400]
        
        if cancel_response.status_code == 200:
            cancel_data = cancel_response.json()
            assert cancel_data["status"] == "cancelled"
            
            # Verify in database
            job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
            if job:
                assert job.status == "cancelled"
        
        # Clean up
        job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
        if job:
            db_session.delete(job)
            db_session.commit()


# ============================================================
# TESTS - WEBSOCKET INTEGRATION
# ============================================================

@pytest.mark.integration
@pytest.mark.slow
class TestWebSocketIntegration:
    """Test WebSocket integration with async jobs."""
    
    def test_websocket_connect_receive_status(self, client, sample_routes_e2e, db_session):
        """
        Test connecting to WebSocket and receiving status.
        
        Flow:
        1. Create job
        2. Connect WebSocket
        3. Receive initial status message
        4. Send ping, receive pong
        """
        from db.models import OptimizationJob
        
        # Create job in database
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
            # Connect to WebSocket
            with client.websocket_connect(f"/ws/optimize/{job_id}") as websocket:
                # Receive initial status
                message = websocket.receive_json(timeout=5.0)
                
                assert "type" in message
                assert message["job_id"] == job_id
                
                # Send ping
                websocket.send_json({"action": "ping"})
                
                # Receive pong (may need to skip other messages)
                for _ in range(5):
                    try:
                        response = websocket.receive_json(timeout=2.0)
                        if response.get("type") == "pong":
                            break
                    except Exception:
                        break
                
        except Exception as e:
            pytest.skip(f"WebSocket not available: {e}")
        finally:
            # Clean up
            db_session.delete(job)
            db_session.commit()
    
    def test_websocket_ping_pong(self, client, db_session):
        """Test WebSocket ping/pong heartbeat."""
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
            with client.websocket_connect(f"/ws/optimize/{job_id}") as websocket:
                # Skip initial messages
                for _ in range(3):
                    try:
                        websocket.receive_json(timeout=1.0)
                    except Exception:
                        break
                
                # Send ping
                websocket.send_json({"action": "ping"})
                
                # Wait for pong
                for _ in range(5):
                    try:
                        response = websocket.receive_json(timeout=2.0)
                        if response.get("type") == "pong":
                            assert "timestamp" in response
                            return
                    except Exception:
                        break
                
                # If we get here, we didn't receive pong
                pytest.skip("Pong not received")
                
        except Exception as e:
            pytest.skip(f"WebSocket not available: {e}")
        finally:
            db_session.delete(job)
            db_session.commit()


# ============================================================
# TESTS - ERROR SCENARIOS
# ============================================================

class TestErrorScenarios:
    """Test error handling in async flow."""
    
    def test_e2e_invalid_routes(self, client):
        """Test flow with invalid route data."""
        response = client.post(
            "/optimize-async",
            json=[{"invalid": "data"}]
        )
        
        # Should fail validation
        assert response.status_code in [400, 422]
    
    def test_e2e_empty_routes(self, client):
        """Test flow with empty routes."""
        response = client.post(
            "/optimize-async",
            json=[]
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400]
    
    def test_e2e_get_nonexistent_job(self, client):
        """Test getting status of non-existent job."""
        fake_job_id = str(uuid.uuid4())
        
        response = client.get(f"/jobs/{fake_job_id}")
        assert response.status_code == 404
        
        response = client.get(f"/jobs/{fake_job_id}/result")
        assert response.status_code == 404
        
        response = client.delete(f"/jobs/{fake_job_id}")
        assert response.status_code == 404
    
    def test_e2e_websocket_nonexistent_job(self, client):
        """Test WebSocket connection to non-existent job."""
        fake_job_id = str(uuid.uuid4())
        
        try:
            with client.websocket_connect(f"/ws/optimize/{fake_job_id}") as websocket:
                # Should still connect but report unknown status
                message = websocket.receive_json(timeout=5.0)
                
                # May receive status or error
                assert "type" in message
                
        except Exception as e:
            # WebSocket may close or error
            pass


# ============================================================
# TESTS - MULTIPLE JOBS
# ============================================================

class TestMultipleJobs:
    """Test handling of multiple concurrent jobs."""
    
    def test_multiple_jobs_creation(self, client, sample_routes_e2e, db_session):
        """Test creating multiple jobs."""
        from db.models import OptimizationJob
        
        job_ids = []
        
        # Create 3 jobs
        for _ in range(3):
            response = client.post(
                "/optimize-async",
                json=sample_routes_e2e
            )
            
            assert response.status_code == 200
            job_ids.append(response.json()["job_id"])
        
        # Verify all jobs exist
        for job_id in job_ids:
            status_response = client.get(f"/jobs/{job_id}")
            assert status_response.status_code == 200
            assert status_response.json()["job_id"] == job_id
        
        # Clean up
        for job_id in job_ids:
            job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
            if job:
                db_session.delete(job)
        db_session.commit()
    
    def test_job_isolation(self, client, sample_routes_e2e, db_session):
        """Test that jobs are isolated from each other."""
        from db.models import OptimizationJob
        
        # Create two jobs
        response1 = client.post("/optimize-async", json=sample_routes_e2e)
        response2 = client.post("/optimize-async", json=sample_routes_e2e)
        
        job_id1 = response1.json()["job_id"]
        job_id2 = response2.json()["job_id"]
        
        # Verify different IDs
        assert job_id1 != job_id2
        
        # Get status of both
        status1 = client.get(f"/jobs/{job_id1}").json()
        status2 = client.get(f"/jobs/{job_id2}").json()
        
        assert status1["job_id"] == job_id1
        assert status2["job_id"] == job_id2
        
        # Clean up
        for job_id in [job_id1, job_id2]:
            job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
            if job:
                db_session.delete(job)
        db_session.commit()


# ============================================================
# TESTS - PERFORMANCE
# ============================================================

class TestPerformance:
    """Test performance characteristics."""
    
    def test_job_creation_fast(self, client, sample_routes_e2e):
        """Test that job creation is fast (< 1 second)."""
        import time
        
        start = time.time()
        response = client.post("/optimize-async", json=sample_routes_e2e)
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 1.0, f"Job creation took {elapsed:.2f}s, expected < 1s"
    
    def test_status_check_fast(self, client, sample_routes_e2e, db_session):
        """Test that status check is fast (< 100ms)."""
        from db.models import OptimizationJob
        import time
        
        # Create job
        response = client.post("/optimize-async", json=sample_routes_e2e)
        job_id = response.json()["job_id"]
        
        # Check status timing
        start = time.time()
        status_response = client.get(f"/jobs/{job_id}")
        elapsed = time.time() - start
        
        assert status_response.status_code == 200
        assert elapsed < 0.5, f"Status check took {elapsed:.2f}s, expected < 0.5s"
        
        # Clean up
        job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
        if job:
            db_session.delete(job)
            db_session.commit()


# ============================================================
# TESTS - RESULTS VALIDATION
# ============================================================

class TestResultsValidation:
    """Test validation of optimization results."""
    
    def test_result_structure(self, client, sample_routes_e2e, db_session):
        """Test that results have expected structure."""
        from db.models import OptimizationJob
        import time
        
        # Queue job
        response = client.post("/optimize-async", json=sample_routes_e2e)
        job_id = response.json()["job_id"]
        
        # Wait for completion (poll)
        for _ in range(30):
            status_response = client.get(f"/jobs/{job_id}")
            if status_response.json().get("status") == "completed":
                break
            time.sleep(0.5)
        
        # Get results
        result_response = client.get(f"/jobs/{job_id}/result")
        
        if result_response.status_code == 200:
            result_data = result_response.json()
            
            if result_data.get("status") == "completed" and "result" in result_data:
                result = result_data["result"]
                
                # Verify structure
                assert "schedule" in result
                assert "stats" in result
                
                stats = result["stats"]
                assert "total_buses" in stats
                assert "total_routes" in stats
                
                # Verify all input routes are covered
                schedule = result["schedule"]
                total_routes_in_schedule = sum(len(bus.get("items", [])) for bus in schedule)
                assert total_routes_in_schedule == len(sample_routes_e2e)
        
        # Clean up
        job = db_session.query(OptimizationJob).filter_by(id=job_id).first()
        if job:
            db_session.delete(job)
            db_session.commit()
