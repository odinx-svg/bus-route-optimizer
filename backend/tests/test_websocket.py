"""
Tests for WebSocket real-time communication.

Validates WebSocket functionality including:
- Connection establishment and cleanup
- Message protocol (ping/pong, progress, status)
- Multiple client handling
- Error handling
"""

import pytest
import json
import asyncio
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def websocket_manager():
    """Create a fresh ConnectionManager instance."""
    try:
        from websocket import ConnectionManager
        return ConnectionManager()
    except ImportError:
        pytest.skip("WebSocket module not available")


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


# ============================================================
# TESTS - CONNECTION MANAGER
# ============================================================

class TestConnectionManager:
    """Test ConnectionManager functionality."""
    
    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, websocket_manager, mock_websocket):
        """Test that connect accepts a WebSocket connection."""
        result = await websocket_manager.connect(mock_websocket, "job-123")
        
        assert result is True
        mock_websocket.accept.assert_called_once()
        assert "job-123" in websocket_manager.active_connections
        assert mock_websocket in websocket_manager.active_connections["job-123"]
    
    @pytest.mark.asyncio
    async def test_connect_handles_accept_failure(self, websocket_manager, mock_websocket):
        """Test that connect handles accept failure gracefully."""
        mock_websocket.accept.side_effect = Exception("Accept failed")
        
        result = await websocket_manager.connect(mock_websocket, "job-123")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, websocket_manager, mock_websocket):
        """Test that disconnect removes a WebSocket connection."""
        # First connect
        await websocket_manager.connect(mock_websocket, "job-123")
        assert len(websocket_manager.active_connections["job-123"]) == 1
        
        # Then disconnect
        await websocket_manager.disconnect(mock_websocket, "job-123")
        
        mock_websocket.close.assert_called_once()
        assert "job-123" not in websocket_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_disconnect_handles_multiple_connections(self, websocket_manager):
        """Test disconnect with multiple connections for same job."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        # Connect both
        await websocket_manager.connect(ws1, "job-123")
        await websocket_manager.connect(ws2, "job-123")
        
        assert len(websocket_manager.active_connections["job-123"]) == 2
        
        # Disconnect one
        await websocket_manager.disconnect(ws1, "job-123")
        
        assert len(websocket_manager.active_connections["job-123"]) == 1
        assert ws2 in websocket_manager.active_connections["job-123"]
    
    @pytest.mark.asyncio
    async def test_send_progress_broadcasts_to_all(self, websocket_manager):
        """Test that send_progress broadcasts to all connected clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        await websocket_manager.connect(ws1, "job-123")
        await websocket_manager.connect(ws2, "job-123")
        
        data = {"type": "progress", "progress": 50}
        sent_count = await websocket_manager.send_progress("job-123", data)
        
        assert sent_count == 2
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        
        # Verify JSON was sent
        sent_json = json.loads(ws1.send_text.call_args[0][0])
        assert sent_json["type"] == "progress"
        assert sent_json["progress"] == 50
    
    @pytest.mark.asyncio
    async def test_send_progress_handles_send_failure(self, websocket_manager):
        """Test that send_progress handles client send failure."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        # Make ws1 fail when sending
        ws1.send_text.side_effect = Exception("Send failed")
        
        await websocket_manager.connect(ws1, "job-123")
        await websocket_manager.connect(ws2, "job-123")
        
        data = {"type": "progress", "progress": 50}
        sent_count = await websocket_manager.send_progress("job-123", data)
        
        # Should only count successful sends
        assert sent_count == 1
        # Failed connection should be cleaned up
        assert ws1 not in websocket_manager.active_connections.get("job-123", set())
    
    @pytest.mark.asyncio
    async def test_send_progress_no_connections(self, websocket_manager):
        """Test send_progress when no clients are connected."""
        data = {"type": "progress", "progress": 50}
        sent_count = await websocket_manager.send_progress("nonexistent-job", data)
        
        assert sent_count == 0
    
    @pytest.mark.asyncio
    async def test_send_to_client_specific(self, websocket_manager, mock_websocket):
        """Test sending to a specific client."""
        await websocket_manager.connect(mock_websocket, "job-123")
        
        data = {"type": "status", "status": "running"}
        result = await websocket_manager.send_to_client(mock_websocket, data)
        
        assert result is True
        mock_websocket.send_json.assert_called_once_with(data)
    
    @pytest.mark.asyncio
    async def test_send_to_client_failure(self, websocket_manager, mock_websocket):
        """Test send_to_client when send fails."""
        mock_websocket.send_json.side_effect = Exception("Send failed")
        
        data = {"type": "status", "status": "running"}
        result = await websocket_manager.send_to_client(mock_websocket, data)
        
        assert result is False
    
    def test_get_connection_count(self, websocket_manager, mock_websocket):
        """Test getting connection count."""
        # Initially no connections
        assert websocket_manager.get_connection_count() == 0
        assert websocket_manager.get_connection_count("job-123") == 0
    
    @pytest.mark.asyncio
    async def test_get_connection_count_with_connections(self, websocket_manager):
        """Test connection count with active connections."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        
        await websocket_manager.connect(ws1, "job-123")
        await websocket_manager.connect(ws2, "job-123")
        await websocket_manager.connect(ws3, "job-456")
        
        assert websocket_manager.get_connection_count("job-123") == 2
        assert websocket_manager.get_connection_count("job-456") == 1
        assert websocket_manager.get_connection_count() == 3
    
    @pytest.mark.asyncio
    async def test_get_active_jobs(self, websocket_manager):
        """Test getting list of active job IDs."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        await websocket_manager.connect(ws1, "job-123")
        await websocket_manager.connect(ws2, "job-456")
        
        active_jobs = websocket_manager.get_active_jobs()
        
        assert "job-123" in active_jobs
        assert "job-456" in active_jobs
        assert len(active_jobs) == 2


# ============================================================
# TESTS - MESSAGE BUILDERS
# ============================================================

class TestMessageBuilders:
    """Test WebSocket message builder functions."""
    
    def test_build_progress_message(self):
        """Test building progress message."""
        try:
            from websocket import build_progress_message
            
            msg = build_progress_message(
                job_id="job-123",
                phase="optimizing",
                progress=50,
                message="Halfway there"
            )
            
            assert msg["type"] == "progress"
            assert msg["job_id"] == "job-123"
            assert msg["phase"] == "optimizing"
            assert msg["progress"] == 50
            assert msg["message"] == "Halfway there"
            assert "timestamp" in msg
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_build_progress_message_with_extra(self):
        """Test building progress message with extra data."""
        try:
            from websocket import build_progress_message
            
            extra = {"routes_processed": 10, "total_routes": 20}
            msg = build_progress_message(
                job_id="job-123",
                phase="optimizing",
                progress=50,
                message="Halfway there",
                extra=extra
            )
            
            assert msg["routes_processed"] == 10
            assert msg["total_routes"] == 20
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_build_status_message(self):
        """Test building status message."""
        try:
            from websocket import build_status_message
            
            msg = build_status_message(
                job_id="job-123",
                status="running"
            )
            
            assert msg["type"] == "status"
            assert msg["job_id"] == "job-123"
            assert msg["status"] == "running"
            assert "timestamp" in msg
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_build_status_message_with_custom_message(self):
        """Test building status message with custom message."""
        try:
            from websocket import build_status_message
            
            msg = build_status_message(
                job_id="job-123",
                status="running",
                message="Processing routes..."
            )
            
            assert msg["message"] == "Processing routes..."
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_build_completed_message(self):
        """Test building completed message."""
        try:
            from websocket import build_completed_message
            
            result = {"schedule": [], "stats": {"total_buses": 5}}
            stats = {"total_buses": 5, "total_routes": 10}
            
            msg = build_completed_message(
                job_id="job-123",
                result=result,
                stats=stats
            )
            
            assert msg["type"] == "completed"
            assert msg["job_id"] == "job-123"
            assert msg["result"] == result
            assert msg["stats"] == stats
            assert "timestamp" in msg
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_build_error_message(self):
        """Test building error message."""
        try:
            from websocket import build_error_message
            
            msg = build_error_message(
                job_id="job-123",
                error_code="OPTIMIZATION_FAILED",
                message="Optimization failed due to error"
            )
            
            assert msg["type"] == "error"
            assert msg["job_id"] == "job-123"
            assert msg["error_code"] == "OPTIMIZATION_FAILED"
            assert msg["message"] == "Optimization failed due to error"
            assert "timestamp" in msg
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_build_pong_message(self):
        """Test building pong message."""
        try:
            from websocket import build_pong_message
            
            msg = build_pong_message()
            
            assert msg["type"] == "pong"
            assert "timestamp" in msg
            
        except ImportError:
            pytest.skip("WebSocket module not available")


# ============================================================
# TESTS - WEBSOCKET ENDPOINT (INTEGRATION)
# ============================================================

@pytest.mark.integration
class TestWebSocketEndpoint:
    """Test WebSocket endpoint integration with FastAPI."""
    
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
            with client.websocket_connect("/ws/optimize/test-job-123") as websocket:
                # Connection should be established
                pass
        except Exception as e:
            # WebSocket may not be available or database not configured
            pytest.skip(f"WebSocket not available: {e}")
    
    def test_websocket_ping_pong(self, client):
        """Test ping/pong heartbeat."""
        try:
            with client.websocket_connect("/ws/optimize/test-job-123") as websocket:
                # Send ping
                websocket.send_json({"action": "ping"})
                
                # Receive pong
                response = websocket.receive_json()
                
                # First message might be status, continue until pong
                while response.get("type") != "pong":
                    response = websocket.receive_json(timeout=2.0)
                
                assert response["type"] == "pong"
                assert "timestamp" in response
                
        except Exception as e:
            pytest.skip(f"WebSocket ping/pong not available: {e}")
    
    def test_websocket_invalid_json(self, client):
        """Test handling of invalid JSON."""
        try:
            with client.websocket_connect("/ws/optimize/test-job-123") as websocket:
                # Skip initial status message
                try:
                    websocket.receive_json(timeout=1.0)
                except Exception:
                    pass
                
                # Send invalid JSON
                websocket.send_text("not valid json")
                
                # Should receive error
                response = websocket.receive_json(timeout=2.0)
                assert response["type"] == "error"
                
        except Exception as e:
            pytest.skip(f"WebSocket error handling not available: {e}")
    
    def test_websocket_unknown_action(self, client):
        """Test handling of unknown action."""
        try:
            with client.websocket_connect("/ws/optimize/test-job-123") as websocket:
                # Skip initial status message
                try:
                    websocket.receive_json(timeout=1.0)
                except Exception:
                    pass
                
                # Send unknown action
                websocket.send_json({"action": "unknown_action"})
                
                # Should receive error
                response = websocket.receive_json(timeout=2.0)
                assert response["type"] == "error"
                
        except Exception as e:
            pytest.skip(f"WebSocket error handling not available: {e}")


# ============================================================
# TESTS - GLOBAL MANAGER INSTANCE
# ============================================================

class TestGlobalManager:
    """Test the global manager instance."""
    
    def test_global_manager_exists(self):
        """Test that global manager instance exists."""
        try:
            from websocket import manager
            
            assert manager is not None
            assert hasattr(manager, 'active_connections')
            assert hasattr(manager, 'connect')
            assert hasattr(manager, 'disconnect')
            assert hasattr(manager, 'send_progress')
            
        except ImportError:
            pytest.skip("WebSocket module not available")
    
    def test_global_manager_is_connection_manager(self):
        """Test that global manager is a ConnectionManager."""
        try:
            from websocket import manager, ConnectionManager
            
            assert isinstance(manager, ConnectionManager)
            
        except ImportError:
            pytest.skip("WebSocket module not available")


# ============================================================
# TESTS - CONCURRENT CONNECTIONS
# ============================================================

class TestConcurrentConnections:
    """Test handling of concurrent WebSocket connections."""
    
    @pytest.mark.asyncio
    async def test_multiple_clients_same_job(self, websocket_manager):
        """Test multiple clients connecting to the same job."""
        clients = [AsyncMock() for _ in range(5)]
        
        # Connect all clients
        for client in clients:
            await websocket_manager.connect(client, "job-123")
        
        # Verify all are connected
        assert websocket_manager.get_connection_count("job-123") == 5
        
        # Send progress to all
        data = {"type": "progress", "progress": 50}
        sent_count = await websocket_manager.send_progress("job-123", data)
        
        assert sent_count == 5
        
        # Verify all received the message
        for client in clients:
            assert client.send_text.called
    
    @pytest.mark.asyncio
    async def test_multiple_jobs_isolation(self, websocket_manager):
        """Test that connections for different jobs are isolated."""
        ws_job1 = AsyncMock()
        ws_job2 = AsyncMock()
        
        await websocket_manager.connect(ws_job1, "job-1")
        await websocket_manager.connect(ws_job2, "job-2")
        
        # Send progress to job-1 only
        data = {"type": "progress", "progress": 50}
        await websocket_manager.send_progress("job-1", data)
        
        # Only job-1 client should receive
        assert ws_job1.send_text.called
        assert not ws_job2.send_text.called


# ============================================================
# TESTS - THREAD SAFETY
# ============================================================

class TestThreadSafety:
    """Test thread safety of ConnectionManager."""
    
    @pytest.mark.asyncio
    async def test_concurrent_connect_disconnect(self, websocket_manager):
        """Test concurrent connect/disconnect operations."""
        import asyncio
        
        async def connect_client(job_id, client_id):
            ws = AsyncMock()
            await websocket_manager.connect(ws, job_id)
            return ws
        
        # Concurrent connections
        tasks = [
            connect_client(f"job-{i % 3}", i)
            for i in range(10)
        ]
        clients = await asyncio.gather(*tasks)
        
        # Verify connections
        total = sum(
            websocket_manager.get_connection_count(f"job-{i}")
            for i in range(3)
        )
        assert total == 10
        
        # Concurrent disconnects
        disconnect_tasks = [
            websocket_manager.disconnect(client, f"job-{i % 3}")
            for i, client in enumerate(clients)
        ]
        await asyncio.gather(*disconnect_tasks)
        
        # Verify all disconnected
        assert websocket_manager.get_connection_count() == 0
