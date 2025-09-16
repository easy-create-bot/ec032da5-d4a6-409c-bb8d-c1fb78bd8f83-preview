from typing import List
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import run_agent
from models import Repo, Chat
import socketio
import uvicorn
from redis_client import redis_client
from socket_client import sio
from start_agent_queue import start_agent_queue
import json
import asyncio
import os

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Wrap Socket.IO as an ASGI app
socket_app = socketio.ASGIApp(
    socketio_server=sio,
    other_asgi_app=app,
    socketio_path='socket.io'
)

class AgentRequest(BaseModel):
    user_prompt: str
    repo: Repo
    project_id: str
    chat: Chat
    access_token: str
    llm_model_type: str
    llm_model_name: str
    socket_id: str

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    # Ensure the background queue worker is running when a client connects
    #await ensure_queue_worker_running()

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.event
async def register(sid, data):
    email = None
    try:
        email = data.get('email') if isinstance(data, dict) else None
    except Exception:
        email = None
    if email:
        await sio.enter_room(sid, email)

@app.get("/")
def test(): 
    return {"message": "Hello, World!"}

queue_worker_task: asyncio.Task | None = None
queue_worker_lock = asyncio.Lock()

async def ensure_queue_worker_running() -> None:
    global queue_worker_task
    async with queue_worker_lock:
        if queue_worker_task is None or queue_worker_task.done():
            queue_worker_task = asyncio.create_task(start_agent_queue())

@app.post("/agent")
async def run_agent_endpoint(request: AgentRequest):
    if redis_client.llen("agent_queue") > 10:
        return {"error": "Agent queue is full please try again in a few seconds"}
    redis_client.lpush("agent_queue", json.dumps(request.model_dump()))
    await ensure_queue_worker_running()
    return {"message": "Queued"}

if __name__ == "__main__":
    uvicorn.run(
        "agent:socket_app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
