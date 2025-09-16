from socketio import AsyncServer

sio = AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=['http://localhost:5173'],
    logger=True,
    engineio_logger=True,
    ping_timeout=120,
    ping_interval=25,
)
