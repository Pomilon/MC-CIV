import argparse
import time
import os
import signal
import sys
import subprocess
import threading
from narrator.story_engine import StoryEngine
from infrastructure.rcon_client import RconClient, MockRconClient
from infrastructure.game_state import GameStateAPI
from agents.llm_core import get_llm_provider

AGENT_PROCESSES = []

def cleanup_agents():
    print("Stopping all agents...")
    for proc in AGENT_PROCESSES:
        if proc.poll() is None:
            proc.terminate()
    # Wait a bit
    time.sleep(1)
    # Kill stubborn ones
    for proc in AGENT_PROCESSES:
        if proc.poll() is None:
            proc.kill()

def main():
    parser = argparse.ArgumentParser(description="AI Minecraft Storytelling Server")
    parser.add_argument("--mode", choices=["real", "mock"], default="mock", help="Run with real server or mock")
    parser.add_argument("--provider", default="gemini", help="LLM Provider (gemini, openai, ollama, llamacpp)")
    parser.add_argument("--model", help="Model name (e.g. llama3.1, gpt-4o)")
    parser.add_argument("--bots", type=int, default=2, help="Number of bots to spawn")
    
    # LAN / Connection Args
    parser.add_argument("--host", default="localhost", help="Minecraft Server IP")
    parser.add_argument("--port", type=int, default=25565, help="Minecraft Server Port")
    parser.add_argument("--disable-narrator", action="store_true", help="Disable Narrator & RCON (required for LAN worlds)")

    args = parser.parse_args()

    # Set connection info for child processes
    os.environ["MC_HOST"] = args.host
    os.environ["MC_PORT"] = str(args.port)

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        cleanup_agents()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    # Setup Infrastructure (Narrator runs in THIS main process)
    if not args.disable_narrator:
        if args.mode == "real":
            # Default RCON host to Game host if not explicitly set
            rcon_host = os.getenv("RCON_HOST", args.host)
            rcon = RconClient(rcon_host, 
                              os.getenv("RCON_PORT", 25575), 
                              os.getenv("RCON_PASSWORD", "password")) 
        else:
            rcon = MockRconClient("localhost", 25575, "password")

        game_api = GameStateAPI(rcon)
        
        llm_kwargs = {}
        if args.model:
            llm_kwargs["model_name"] = args.model
            
        llm = get_llm_provider(args.provider, **llm_kwargs)

        # Start Narrator in a background thread of the orchestrator
        narrator = StoryEngine(game_api, llm)
        narrator_thread = threading.Thread(target=narrator.run_loop, args=(10,), daemon=True)
        narrator_thread.start()
        print("Narrator engine started.")
    else:
        print("Narrator and RCON disabled (LAN Mode compatible).")

    # Start Agent Processes
    missions = [
        "Collect wood and build a shelter",
        "Explore the caves and find iron",
        "Farm food for the colony"
    ]
    
    python_executable = sys.executable

    for i in range(args.bots):
        bot_id = f"Bot{i+1}"
        mission = missions[i % len(missions)]
        
        print(f"Launching process for {bot_id}...")
        
        cmd = [python_executable, "-m", "agents.agent_process", 
             "--bot-id", bot_id, 
             "--mission", mission,
             "--provider", args.provider]
             
        if args.model:
            cmd.extend(["--model", args.model])
        
        # Spawn independent Python process for each agent
        proc = subprocess.Popen(
            cmd,
            cwd=os.getcwd(), # Ensure we are in project root so module imports work
            env=os.environ.copy()
        )
        AGENT_PROCESSES.append(proc)

    print(f"System Running with {args.bots} bot processes. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            for i, proc in enumerate(AGENT_PROCESSES):
                if proc.poll() is not None:
                    print(f"Warning: Agent process {i} exited with code {proc.returncode}")
    except KeyboardInterrupt:
        cleanup_agents()

if __name__ == "__main__":
    main()