"""
Redis Pub/Sub listener for progress updates.

This module listens for progress updates published by Celery tasks
and forwards them to WebSocket clients via the ConnectionManager.

Usage:
    # In main.py or startup script:
    from progress_listener import start_progress_listener
    asyncio.create_task(start_progress_listener())
"""

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Flag to track if listener is running
_listener_started: bool = False
_listener_task: Optional[asyncio.Task] = None


async def listen_progress_updates(websocket_manager):
    """
    Listen for progress updates from Redis and forward to WebSockets.
    
    This function runs indefinitely and should be started as a background task.
    
    Args:
        websocket_manager: The ConnectionManager instance to use for sending updates
    """
    global _listener_started
    
    try:
        # Try to use redis-py with asyncio support (redis 4.2+)
        from redis.asyncio import Redis
        
        from config import config
        
        if not config.is_redis_available():
            logger.warning("Redis not available, progress listener disabled")
            _listener_started = False
            return
        
        redis = Redis.from_url(config.REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        
        # Subscribe to all progress channels
        await pubsub.psubscribe("job_progress:*")
        logger.info("Progress listener started, subscribed to job_progress:*")
        
        _listener_started = True
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    # Parse the message data
                    data = json.loads(message["data"])
                    job_id = data.get("job_id")
                    
                    if job_id:
                        # Forward to WebSocket clients
                        await websocket_manager.send_progress(job_id, data)
                        logger.debug(f"Forwarded progress update for job {job_id}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode progress message: {e}")
                except Exception as e:
                    logger.error(f"Error processing progress message: {e}")
                    
    except ImportError:
        logger.warning("redis asyncio support not available, trying aioredis...")
        await _listen_with_aioredis(websocket_manager)
    except Exception as e:
        logger.error(f"Progress listener error: {e}")
        _listener_started = False
        raise


async def _listen_with_aioredis(websocket_manager):
    """
    Fallback listener using aioredis (legacy support).
    
    Args:
        websocket_manager: The ConnectionManager instance
    """
    global _listener_started
    
    try:
        import aioredis
        from config import config
        
        redis = await aioredis.from_url(config.REDIS_URL)
        pubsub = redis.pubsub()
        await pubsub.psubscribe("job_progress:*")
        
        logger.info("Progress listener started with aioredis")
        _listener_started = True
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    data = json.loads(message["data"])
                    job_id = data.get("job_id")
                    
                    if job_id:
                        await websocket_manager.send_progress(job_id, data)
                        
                except Exception as e:
                    logger.error(f"Error processing progress message: {e}")
                    
    except ImportError:
        logger.error("Neither redis asyncio nor aioredis available. Progress listener disabled.")
        _listener_started = False


async def start_progress_listener(websocket_manager) -> bool:
    """
    Start the progress listener as a background task.
    
    Args:
        websocket_manager: The ConnectionManager instance
        
    Returns:
        True if listener was started, False otherwise
    """
    global _listener_started, _listener_task
    
    if _listener_started:
        logger.debug("Progress listener already running")
        return True
    
    try:
        # Test Redis connection first
        from config import config
        if not config.is_redis_available():
            logger.warning("Redis not available, cannot start progress listener")
            return False
        
        # Start the listener
        _listener_task = asyncio.create_task(
            listen_progress_updates(websocket_manager),
            name="progress_listener"
        )
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        return _listener_started
        
    except Exception as e:
        logger.error(f"Failed to start progress listener: {e}")
        return False


def stop_progress_listener() -> bool:
    """
    Stop the progress listener.
    
    Returns:
        True if listener was stopped, False if it wasn't running
    """
    global _listener_started, _listener_task
    
    if _listener_task and not _listener_task.done():
        _listener_task.cancel()
        _listener_started = False
        logger.info("Progress listener stopped")
        return True
    
    return False


def is_listener_running() -> bool:
    """Check if the progress listener is running."""
    global _listener_started, _listener_task
    
    if not _listener_started:
        return False
    
    if _listener_task and _listener_task.done():
        _listener_started = False
        return False
    
    return True


# Synchronous helper for Celery tasks to publish progress
def publish_progress(job_id: str, phase: str, progress: int, message: str) -> bool:
    """
    Publish a progress update to Redis (synchronous, for use in Celery tasks).
    
    Args:
        job_id: The job ID
        phase: Current optimization phase
        progress: Progress percentage (0-100)
        message: Human-readable message
        
    Returns:
        True if message was published successfully
    """
    try:
        import redis
        import json
        from datetime import datetime
        from config import config
        
        client = redis.Redis.from_url(config.REDIS_URL)
        
        data = {
            "job_id": job_id,
            "type": "progress",
            "phase": phase,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        client.publish(f"job_progress:{job_id}", json.dumps(data))
        return True
        
    except Exception as e:
        logger.error(f"Failed to publish progress: {e}")
        return False
