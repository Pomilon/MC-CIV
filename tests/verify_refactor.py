import asyncio
import json
import logging
import os
import subprocess
import sys

import websockets

logging.basicConfig(level=logging.INFO, format='[TEST] %(message)s')
logger = logging.getLogger("BusTest")

async def run_test():
    env = os.environ.copy()
    env["MOCK_MODE"] = "true"
    env["PYTHONPATH"] = os.getcwd()

    # Start the system with 1 bot
    logger.info("Starting System...")
    proc = subprocess.Popen(
        [sys.executable, "cli/main.py", "--mode", "mock", "--bots", "1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    success = False
    try:
        # Wait for orchestrator to be ready
        await asyncio.sleep(5)

        # Connect to the dashboard stream
        uri = "ws://localhost:8000/ws/client"
        async with websockets.connect(uri) as ws:
            logger.info("Connected to Orchestrator Dashboard stream.")

            # Wait for updates from Bot1
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 30:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)

                    if data.get("type") == "update" and data.get("bot_id") == "Bot1":
                        bot_data = data.get("data", {})
                        action_state = bot_data.get("action_state", {})
                        logger.info(f"Bot1 Update: Status={action_state.get('status')} Action={action_state.get('type')}")

                        if action_state.get('status') == 'running' or action_state.get('status') == 'completed':
                            logger.info("Service Bus Communication Verified!")
                            success = True
                            break
                except asyncio.TimeoutError:
                    continue

    except Exception as e:
        logger.error(f"Test Error: {e}")
    finally:
        logger.info("Cleaning up...")
        proc.terminate()
        try:
            # Also kill children if any stubborn ones
            subprocess.run(["pkill", "-9", "-f", "agents.controller"])
            subprocess.run(["pkill", "-9", "-f", "node index.js"])
        except Exception:
            pass

    return success

if __name__ == "__main__":
    if asyncio.run(run_test()):
        print("VERIFICATION SUCCESSFUL")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED")
        sys.exit(1)
