"""
WebSocket handlers para Tutti backend.
"""

try:
    from backend.websocket.schedule_validation_ws import (
        ScheduleValidationWebSocket,
        validation_ws_handler,
        handle_schedule_validation_websocket
    )
except ImportError:
    from websocket.schedule_validation_ws import (
        ScheduleValidationWebSocket,
        validation_ws_handler,
        handle_schedule_validation_websocket
    )

__all__ = [
    'ScheduleValidationWebSocket',
    'validation_ws_handler',
    'handle_schedule_validation_websocket'
]
