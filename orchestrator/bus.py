import json
import logging
import os
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MessageBus")

app = FastAPI()

# Mount dashboard static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

class MessageBus:
    def __init__(self):
        # bot_id -> { "brain": websocket, "body": websocket }
        self.connections: Dict[str, Dict[str, WebSocket]] = {}
        self.web_clients: List[WebSocket] = []

    async def register_web(self, websocket: WebSocket):
        await websocket.accept()
        self.web_clients.append(websocket)
        logger.info("Web dashboard client connected")

    async def unregister_web(self, websocket: WebSocket):
        if websocket in self.web_clients:
            self.web_clients.remove(websocket)
        logger.info("Web dashboard client disconnected")

    async def broadcast_to_web(self, message: str, bot_id: str, side: str):
        if not self.web_clients:
            return

        payload = {
            "type": "update",
            "bot_id": bot_id,
            "side": side,
            "data": json.loads(message)
        }

        for client in self.web_clients:
            try:
                await client.send_json(payload)
            except Exception:
                pass

    async def register(self, bot_id: str, side: str, websocket: WebSocket):
        if bot_id not in self.connections:
            self.connections[bot_id] = {"brain": None, "body": None}

        self.connections[bot_id][side] = websocket
        logger.info(f"Registered {side} for {bot_id}")

    async def unregister(self, bot_id: str, side: str):
        if bot_id in self.connections:
            self.connections[bot_id][side] = None
            logger.info(f"Unregistered {side} for {bot_id}")

    async def route(self, bot_id: str, sender_side: str, message: str):
        # Broadcast to dashboard
        await self.broadcast_to_web(message, bot_id, sender_side)

        target_side = "body" if sender_side == "brain" else "brain"
        target_ws = self.connections.get(bot_id, {}).get(target_side)

        if target_ws:
            await target_ws.send_text(message)
        else:
            logger.warning(f"No {target_side} connected for {bot_id}. Message dropped.")
            # Notify sender
            sender_ws = self.connections.get(bot_id, {}).get(sender_side)
            if sender_ws:
                error_msg = json.dumps({"type": "error", "data": {"message": f"No {target_side} connected"}})
                await sender_ws.send_text(error_msg)

bus = MessageBus()

@app.get("/")
async def get_dashboard():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            return HTMLResponse(f.read())
    return HTMLResponse("Dashboard index.html not found.")

@app.websocket("/ws/client")
async def dashboard_endpoint(websocket: WebSocket):
    await bus.register_web(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await bus.unregister_web(websocket)

@app.websocket("/ws/brain/{bot_id}")
async def brain_endpoint(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    await bus.register(bot_id, "brain", websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await bus.route(bot_id, "brain", data)
    except WebSocketDisconnect:
        await bus.unregister(bot_id, "brain")

@app.websocket("/ws/body/{bot_id}")
async def body_endpoint(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    await bus.register(bot_id, "body", websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await bus.route(bot_id, "body", data)
    except WebSocketDisconnect:
        await bus.unregister(bot_id, "body")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
