import argparse
import threading
import time
import os
import signal
import sys
import socket
import subprocess
from agents.controller import AgentController
from agents.llm_core import get_llm_provider
from narrator.story_engine import StoryEngine
from infrastructure.rcon_client import RconClient, MockRconClient
from infrastructure.game_state import GameStateAPI

BOT_PROCESSES = {}
BOT_CONTROLLERS = []

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def start_node_bot(bot_id, mission):
    """Spawns a Node.js bot client process on a free port."""
    port = find_free_port()
    
    env = os.environ.copy()
    env["MC_USERNAME"] = bot_id
    env["MISSION"] = mission
    env["PORT"] = str(port)
    
    # Kill existing if any (simplistic)
    if bot_id in BOT_PROCESSES:
        BOT_PROCESSES[bot_id].terminate()
    
    print(f"Spawning {bot_id} on port {port}...")
    # Change cwd to bot-client to ensure node_modules are found
    proc = subprocess.Popen(
        ["node", "index.js"],
        cwd="bot-client",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    BOT_PROCESSES[bot_id] = proc
    return port

def cleanup_bots():
    print("Stopping bots...")
    for pid, proc in BOT_PROCESSES.items():
        proc.terminate()

def monitor_process(name, proc):
    def read_stream(stream, prefix):
        while True:
            output = stream.readline()
            if output:
                print(f"[{name} {prefix}] {output.strip()}")
            else:
                break
    
    # We need threads to read both stdout and stderr without blocking
    t_out = threading.Thread(target=read_stream, args=(proc.stdout, "OUT"), daemon=True)
    t_err = threading.Thread(target=read_stream, args=(proc.stderr, "ERR"), daemon=True)
    t_out.start()
    t_err.start()
    
    proc.wait()
    print(f"[{name}] Process exited with code {proc.returncode}")

def wait_for_port(port, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    return False

def main():
    parser = argparse.ArgumentParser(description="AI Minecraft Storytelling Server")
    parser.add_argument("--mode", choices=["real", "mock"], default="mock", help="Run with real server or mock")
    parser.add_argument("--provider", default="gemini", help="LLM Provider (gemini, openai)")
    parser.add_argument("--bots", type=int, default=2, help="Number of bots to spawn")
    args = parser.parse_args()

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        cleanup_bots()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    # Setup Infrastructure
    if args.mode == "real":
        rcon = RconClient(os.getenv("RCON_HOST", "localhost"), 
                          os.getenv("RCON_PORT", 25575), 
                          os.getenv("RCON_PASSWORD", "password")) 
    else:
        rcon = MockRconClient("localhost", 25575, "password")

    game_api = GameStateAPI(rcon)
    llm = get_llm_provider(args.provider)

    # Start Narrator
    narrator = StoryEngine(game_api, llm)
    narrator_thread = threading.Thread(target=narrator.run_loop, args=(10,), daemon=True)
    narrator_thread.start()

    # Start Swarm
    missions = [
        "Collect wood and build a shelter",
        "Explore the caves and find iron",
        "Farm food for the colony"
    ]
    
    for i in range(args.bots):
        bot_id = f"Bot{i+1}"
        mission = missions[i % len(missions)]
        
        port = start_node_bot(bot_id, mission)
        
        # Log bot output in thread
        threading.Thread(target=monitor_process, args=(bot_id, BOT_PROCESSES[bot_id]), daemon=True).start()
        
        # Wait for port to be open
        if wait_for_port(port):
             print(f"{bot_id} is ready on port {port}")
             controller = AgentController(f"http://localhost:{port}", llm, mission)
             BOT_CONTROLLERS.append(controller)
             
             agent_thread = threading.Thread(target=controller.run_loop, args=(5,), daemon=True)
             agent_thread.start()
             print(f"{bot_id} Controller Started.")
        else:
             print(f"Failed to start {bot_id} on port {port}. Check logs.")

    print(f"System Running with {args.bots} bots. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_bots()

if __name__ == "__main__":
    main()
