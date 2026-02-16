"""
WebSocket module for Tutti backend.

Provides real-time progress updates for optimization jobs using
FastAPI's native WebSocket support.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional, Any
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for job progress updates.
    
    Tracks active connections per job_id and handles message broadcasting.
    """
    
    def __init__(self):
        # job_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, job_id: str) -> bool:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to register
            job_id: The job ID this connection is subscribing to
            
        Returns:
            True if connection was accepted, False otherwise
        """
        try:
            await websocket.accept()
            
            async with self._lock:
                if job_id not in self.active_connections:
                    self.active_connections[job_id] = set()
                self.active_connections[job_id].add(websocket)
            
            logger.info(f"WebSocket connected for job {job_id}. Total connections: {len(self.active_connections[job_id])}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection for job {job_id}: {e}")
            return False
    
    async def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Unregister and close a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to unregister
            job_id: The job ID this connection was subscribed to
        """
        async with self._lock:
            if job_id in self.active_connections:
                self.active_connections[job_id].discard(websocket)
                
                # Clean up empty job entries
                if not self.active_connections[job_id]:
                    del self.active_connections[job_id]
                    logger.info(f"No more connections for job {job_id}, cleaned up")
        
        try:
            await websocket.close()
        except Exception:
            pass  # Connection might already be closed
    
    async def send_progress(self, job_id: str, data: dict) -> int:
        """
        Send progress update to all clients subscribed to a job.
        
        Args:
            job_id: The job ID to send progress for
            data: The progress data to send
            
        Returns:
            Number of clients that received the message
        """
        async with self._lock:
            if job_id not in self.active_connections:
                return 0
            
            connections = self.active_connections[job_id].copy()
        
        message = json.dumps(data)
        disconnected: Set[WebSocket] = set()
        sent_count = 0
        
        for connection in connections:
            try:
                await connection.send_text(message)
                sent_count += 1
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket for job {job_id}: {e}")
                disconnected.add(connection)
        
        # Clean up dead connections
        if disconnected:
            async with self._lock:
                if job_id in self.active_connections:
                    for conn in disconnected:
                        self.active_connections[job_id].discard(conn)
                    if not self.active_connections[job_id]:
                        del self.active_connections[job_id]
        
        return sent_count
    
    async def send_to_client(self, websocket: WebSocket, data: dict) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            websocket: The specific WebSocket connection
            data: The data to send
            
        Returns:
            True if message was sent successfully
        """
        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.debug(f"Failed to send to specific WebSocket: {e}")
            return False
    
    def get_connection_count(self, job_id: Optional[str] = None) -> int:
        """
        Get the number of active connections.
        
        Args:
            job_id: Optional job ID to count connections for. If None, counts all.
            
        Returns:
            Number of active connections
        """
        if job_id:
            return len(self.active_connections.get(job_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_active_jobs(self) -> list:
        """Get list of job_ids with active connections."""
        return list(self.active_connections.keys())


# Global connection manager instance
manager = ConnectionManager()


# Message builders for consistent protocol
def build_progress_message(
    job_id: str, 
    phase: str, 
    progress: int, 
    message: str,
    extra: Optional[dict] = None
) -> dict:
    """
    Build a standardized progress message.
    
    Args:
        job_id: The job ID
        phase: Current optimization phase
        progress: Progress percentage (0-100)
        message: Human-readable message
        extra: Optional additional data
        
    Returns:
        Formatted progress message dictionary
    """
    data = {
        "type": "progress",
        "job_id": job_id,
        "phase": phase,
        "progress": progress,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    if extra:
        data.update(extra)
    return data


def build_status_message(job_id: str, status: str, message: Optional[str] = None) -> dict:
    """
    Build a standardized status message.
    
    Args:
        job_id: The job ID
        status: Job status (queued, running, completed, failed, cancelled)
        message: Optional human-readable message
        
    Returns:
        Formatted status message dictionary
    """
    return {
        "type": "status",
        "job_id": job_id,
        "status": status,
        "message": message or f"Job status: {status}",
        "timestamp": datetime.utcnow().isoformat()
    }


def build_completed_message(
    job_id: str, 
    result: dict, 
    stats: Optional[dict] = None
) -> dict:
    """
    Build a standardized completion message.
    
    Args:
        job_id: The job ID
        result: The optimization result
        stats: Optional statistics
        
    Returns:
        Formatted completion message dictionary
    """
    return {
        "type": "completed",
        "job_id": job_id,
        "result": result,
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_error_message(job_id: str, error_code: str, message: str) -> dict:
    """
    Build a standardized error message.
    
    Args:
        job_id: The job ID
        error_code: Error code for programmatic handling
        message: Human-readable error message
        
    Returns:
        Formatted error message dictionary
    """
    return {
        "type": "error",
        "job_id": job_id,
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }


def build_pong_message() -> dict:
    """Build a pong response for heartbeat."""
    return {
        "type": "pong",
        "timestamp": datetime.utcnow().isoformat()
    }
