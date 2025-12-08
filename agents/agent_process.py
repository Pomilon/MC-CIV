import argparse
import subprocess
import os
import sys
import time
import socket
import logging
import signal
from agents.controller import AgentController
from agents.llm_core import get_llm_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger("AgentProcess")

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class AgentProcess:
    def __init__(self, bot_id, mission, provider="gemini", model_name=None):
        self.bot_id = bot_id
        self.mission = mission
        self.provider = provider
        self.model_name = model_name
        self.node_process = None
        self.controller = None
        self.port = find_free_port()

    def start_node_bot(self):
        env = os.environ.copy()
        env["MC_USERNAME"] = self.bot_id
        env["MISSION"] = self.mission
        env["PORT"] = str(self.port)
        
        logger.info(f"Spawning Node.js bot {self.bot_id} on port {self.port}...")
        
        # We start the node process. 
        # We redirect stdout/stderr to this process's stdout/stderr so they are aggregated or can be piped.
        self.node_process = subprocess.Popen(
            ["node", "index.js"],
            cwd="bot-client",
            env=env,
            stdout=sys.stdout, 
            stderr=sys.stderr,
            text=True
        )

    def wait_for_node_server(self, timeout=20):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.create_connection(("localhost", self.port), timeout=1):
                    return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                time.sleep(0.5)
        return False

    def run(self):
        # 1. Start Node Bot
        self.start_node_bot()
        
        # 2. Wait for it to be ready
        if not self.wait_for_node_server():
            logger.error("Node bot failed to start API server.")
            self.shutdown()
            sys.exit(1)

        # 3. Initialize Controller
        logger.info(f"Node bot ready. Initializing Controller for {self.bot_id}...")
        
        llm_kwargs = {}
        if self.model_name:
            llm_kwargs["model_name"] = self.model_name
            
        llm = get_llm_provider(self.provider, **llm_kwargs)
        self.controller = AgentController(f"http://localhost:{self.port}", llm, self.mission, self.bot_id)

        # 4. Run Controller Loop
        # The controller loop is now the main thread of this process.
        try:
            self.controller.run_loop()
        except KeyboardInterrupt:
            logger.info("Agent process interrupted.")
        except Exception as e:
            logger.error(f"Agent process crashed: {e}")
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down agent process...")
        if self.node_process:
            self.node_process.terminate()
            try:
                self.node_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.node_process.kill()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    agent = AgentProcess(args.bot_id, args.mission, args.provider, args.model)
    
    # Handle signals to ensure child process cleanup
    def signal_handler(sig, frame):
        agent.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    agent.run()
