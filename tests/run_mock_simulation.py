import asyncio
import subprocess
import os
import sys
import time
import json
import logging
import websockets

# Configure logging
logging.basicConfig(level=logging.INFO, format='[SIM] %(message)s')
logger = logging.getLogger("Simulation")

DASHBOARD_PORT = 8000
AGENT_PORT = 0 # Will be assigned by agent process

async def wait_for_port(port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.close()
            await writer.wait_closed()
            return True
        except:
            await asyncio.sleep(0.5)
    return False

async def run_simulation():
    env = os.environ.copy()
    env["MOCK_MODE"] = "true"
    env["PYTHONPATH"] = os.getcwd()

    # 1. Start Dashboard
    logger.info("Starting Dashboard...")
    dashboard_proc = subprocess.Popen(
        [sys.executable, "dashboard/app.py"],
        env=env,
        stdout=subprocess.DEVNULL, # Keep it clean
        stderr=subprocess.DEVNULL
    )
    
    if not await wait_for_port(DASHBOARD_PORT):
        logger.error("Dashboard failed to start.")
        dashboard_proc.terminate()
        return False

    # 2. Start Agent
    logger.info("Starting Mock Agent...")
    agent_proc = subprocess.Popen(
        [sys.executable, "-m", "agents.agent_process", "--bot-id", "MockBot1", "--mission", "Test E2E"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    success = False
    
    try:
        # 3. Connect to Dashboard Client WS
        uri = f"ws://localhost:{DASHBOARD_PORT}/ws/client"
        async with websockets.connect(uri) as ws:
            logger.info("Connected to Dashboard stream.")
            
            # Wait for updates
            start_time = time.time()
            while time.time() - start_time < 30: # 30s timeout
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(msg)
                    
                    if data.get("type") == "update" and data.get("bot_id") == "MockBot1":
                        agent_data = data.get("data", {})
                        action_state = agent_data.get("action_state", {})
                        
                        logger.info(f"Received Update: State={agent_data.get('internal_state')} Action={action_state.get('type')}")
                        
                        # Check for signs of life
                        if agent_data.get("internal_state") == "EXECUTING":
                            logger.info("Agent is EXECUTING! Pipeline verified.")
                            success = True
                            break
                        
                        if action_state.get("status") == "completed":
                            logger.info("Agent completed an action! Pipeline verified.")
                            success = True
                            break
                            
                except asyncio.TimeoutError:
                    logger.warning("No message received in 5s...")
                    # Check if agent is still running
                    if agent_proc.poll() is not None:
                        logger.error(f"Agent process died with code {agent_proc.returncode}")
                        stdout, stderr = agent_proc.communicate()
                        print("Agent STDOUT:", stdout.decode())
                        print("Agent STDERR:", stderr.decode())
                        break

    except Exception as e:
        logger.error(f"Simulation Error: {e}")
    finally:
        logger.info("Cleaning up...")
        agent_proc.terminate()
        dashboard_proc.terminate()
        
        # Log Agent Output if failed
        if not success:
            stdout, stderr = agent_proc.communicate()
            print("--- AGENT LOGS ---")
            print(stdout.decode())
            print(stderr.decode())

    return success

if __name__ == "__main__":
    try:
        if asyncio.run(run_simulation()):
            logger.info("TEST PASSED: Unified Data Stream Verified.")
            sys.exit(0)
        else:
            logger.error("TEST FAILED: Data stream interrupted or incomplete.")
            sys.exit(1)
    except KeyboardInterrupt:
        pass
