import argparse
import asyncio
import os
import sys
import socket
import logging
import signal
import uvicorn
from agents.controller import AgentController, create_app
from agents.llm_core import get_llm_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger("AgentProcess")

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class AgentProcess:
    def __init__(self, bot_id, mission, provider="gemini", model_name=None, profile_path=None):
        self.bot_id = bot_id
        self.mission = mission
        self.provider = provider
        self.model_name = model_name
        self.profile_path = profile_path
        self.port = find_free_port()
        self.node_process = None

    async def start_node_bot(self):
        env = os.environ.copy()
        env["MC_USERNAME"] = self.bot_id
        env["MISSION"] = self.mission
        env["PORT"] = str(self.port)
        # Pass MOCK_MODE if set globally
        
        logger.info(f"Spawning Node.js bot {self.bot_id} on port {self.port}...")
        
        # Use asyncio subprocess
        self.node_process = await asyncio.create_subprocess_exec(
            "node", "index.js",
            cwd="bot-client",
            env=env,
            stdout=sys.stdout, 
            stderr=sys.stderr
        )

    async def run(self):
        # 1. Initialize Controller
        logger.info(f"Initializing Controller for {self.bot_id}...")
        
        llm_kwargs = {}
        if self.model_name:
            llm_kwargs["model_name"] = self.model_name
            
        llm = get_llm_provider(self.provider, **llm_kwargs)
        
        controller = AgentController(
            self.bot_id, 
            self.mission,
            llm, 
            profile_path=self.profile_path
        )
        
        app = create_app(controller)
        
        # 2. Start Uvicorn Server
        config = uvicorn.Config(app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        
        # Run server in background task
        server_task = asyncio.create_task(server.serve())
        
        # 3. Start Node Bot (after a brief delay to ensure server is up)
        await asyncio.sleep(2)
        await self.start_node_bot()
        
        # 4. Wait for Node Bot to finish (or crash)
        try:
            await self.node_process.wait()
        except asyncio.CancelledError:
            logger.info("Agent process cancelled.")
        finally:
            if self.node_process:
                try:
                    self.node_process.terminate()
                    await self.node_process.wait()
                except ProcessLookupError:
                    pass
            # Stop server
            server.should_exit = True
            await server_task

    def shutdown(self):
        # This is handled by asyncio cancellation in run() mostly
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default=None)
    parser.add_argument("--profile", default=None, help="Path to agent profile JSON")
    args = parser.parse_args()

    agent = AgentProcess(args.bot_id, args.mission, args.provider, args.model, args.profile)
    
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass
