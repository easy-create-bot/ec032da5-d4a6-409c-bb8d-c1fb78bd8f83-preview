from redis_client import redis_client
import json
from main import run_agent
from socket_client import sio
import requests
import os
import asyncio
from models import Repo

async def start_agent_queue():
    while True:
        try:
            # Run blocking Redis call in a thread to avoid freezing the event loop
            raw = await asyncio.to_thread(redis_client.brpop, "agent_queue", 1)
            if not raw:
                continue
            _, payload = raw
            req = json.loads(payload)
            # Normalize repo to Repo model to ensure attribute access works downstream
            repo_obj = Repo(**req["repo"]) if isinstance(req.get("repo"), dict) else req["repo"]
            pr_url, session_id = await run_agent(
                req["user_prompt"], repo_obj, req["access_token"],
                req["socket_id"], None, req["llm_model_type"], req["llm_model_name"]
            )
            event = "pr_submitted" if 'github.com' in pr_url else "agent_error"
            # Attach PR URL to chat before persisting and emitting
            if event == 'pr_submitted':
                req["chat"]["pullRequestUrl"] = pr_url
                try:
                    # Run blocking HTTP call in a thread to avoid freezing the event loop
                    res = await asyncio.to_thread(
                        requests.put,
                        f"{os.getenv('BACKEND_API')}/project/{req['project_id']}/chat/{req['chat']['id']}",
                        json={"chat": req["chat"]},
                        timeout=15
                    )
                    
                    if res.status_code != 200:
                        error_msg = None
                        try:
                            error_msg = res.json().get('error')
                        except Exception:
                            error_msg = res.text
                        event = "agent_error"
                except Exception as e:
                    event = "agent_error"
            else:
                event = "agent_error"
                # Fallback emit to socket id and email room
                await sio.emit(event, {"pr_url": pr_url, "session": session_id, "chat": req["chat"]}, room=req["socket_id"]) 
                if req.get("chat") and req["chat"].get("userEmail"):
                    await sio.emit(event, {"pr_url": pr_url, "session": session_id, "chat": req["chat"]}, room=req["chat"]["userEmail"])                
            
            print(f'Emitting event: {event}')
            # Emit final event to the specific client socket and the user's email room
            await sio.emit(event, {"pr_url": pr_url, "session": session_id, "chat": req["chat"]}, room=req["socket_id"])
            if req.get("chat") and req["chat"].get("userEmail"):
                await sio.emit(event, {"pr_url": pr_url, "session": session_id, "chat": req["chat"]}, room=req["chat"]["userEmail"])            
        except Exception as e:
            # Try to notify client about the failure, then keep the worker alive
            try:
                error_payload = {"pr_url": str(e), "session": None}
                if 'req' in locals() and isinstance(req, dict):
                    if req.get("chat"):
                        error_payload["chat"] = req["chat"]
                    if req.get("socket_id"):
                        await sio.emit("agent_error", error_payload, room=req["socket_id"])
                    user_email = req.get("chat", {}).get("userEmail") if req.get("chat") else None
                    if user_email:
                        await sio.emit("agent_error", error_payload, room=user_email)
            except Exception:
                pass
            await asyncio.sleep(0.5)
