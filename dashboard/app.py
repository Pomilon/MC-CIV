from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Dashboard")

app = FastAPI()

# Mount static files
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class ConnectionManager:
    def __init__(self):
        # web_clients: List[WebSocket]
        self.web_clients: List[WebSocket] = []
        # agents: Dict[bot_id, WebSocket]
        self.agents: Dict[str, WebSocket] = {}
        # agent_data: Dict[bot_id, latest_state]
        self.agent_data: Dict[str, dict] = {}

    async def connect_web(self, websocket: WebSocket):
        await websocket.accept()
        self.web_clients.append(websocket)
        # Send initial state
        await websocket.send_json({"type": "init", "data": self.agent_data})

    def disconnect_web(self, websocket: WebSocket):
        if websocket in self.web_clients:
            self.web_clients.remove(websocket)

    async def connect_agent(self, bot_id: str, websocket: WebSocket):
        await websocket.accept()
        self.agents[bot_id] = websocket
        logger.info(f"Agent {bot_id} connected to Dashboard.")

    def disconnect_agent(self, bot_id: str):
        if bot_id in self.agents:
            del self.agents[bot_id]
        logger.info(f"Agent {bot_id} disconnected from Dashboard.")

    async def broadcast_to_web(self, message: dict):
        for connection in self.web_clients:
            try:
                await connection.send_json(message)
            except:
                pass

    async def update_agent_state(self, bot_id: str, data: dict):
        self.agent_data[bot_id] = data
        await self.broadcast_to_web({
            "type": "update",
            "bot_id": bot_id,
            "data": data
        })

    async def send_command(self, bot_id: str, command: dict):
        if bot_id in self.agents:
            await self.agents[bot_id].send_json(command)
            return True
        return False

manager = ConnectionManager()

class CommandRequest(BaseModel):
    bot_id: str
    command: str

@app.get("/")
async def get():
    with open(os.path.join(static_dir, "index.html"), 'r') as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/client")
async def websocket_client_endpoint(websocket: WebSocket):
    await manager.connect_web(websocket)
    try:
        while True:
            # Client might send commands later
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_web(websocket)

@app.post("/api/command")
async def send_command(req: CommandRequest):
    success = await manager.send_command(req.bot_id, {"type": "user_command", "command": req.command})
    if success:
        return {"status": "sent"}
    raise HTTPException(status_code=404, detail="Agent not connected")

@app.websocket("/ws/agent/{bot_id}")
async def websocket_agent_endpoint(websocket: WebSocket, bot_id: str):
    await manager.connect_agent(bot_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Agent pushes its state
            await manager.update_agent_state(bot_id, data)
    except WebSocketDisconnect:
        manager.disconnect_agent(bot_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
