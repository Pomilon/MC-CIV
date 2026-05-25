import argparse
import asyncio
import os
import signal
import subprocess
import sys
import threading
import time

from dotenv import load_dotenv

from agents.llm_core import get_llm_provider
from infrastructure.game_state import GameStateAPI
from infrastructure.rcon_client import MockRconClient, RconClient
from narrator.agent import NarratorAgent

load_dotenv()

AGENT_PROCESSES = []
ORCHESTRATOR_PROCESS = None

def cleanup_agents():
    print("Stopping all agents...")
    for proc in AGENT_PROCESSES:
        if proc.poll() is None:
            proc.terminate()

    if ORCHESTRATOR_PROCESS and ORCHESTRATOR_PROCESS.poll() is None:
        ORCHESTRATOR_PROCESS.terminate()

    # Wait a bit
    time.sleep(1)
    # Kill stubborn ones
    for proc in AGENT_PROCESSES:
        if proc.poll() is None:
            proc.kill()
    if ORCHESTRATOR_PROCESS and ORCHESTRATOR_PROCESS.poll() is None:
        ORCHESTRATOR_PROCESS.kill()

def main():
    parser = argparse.ArgumentParser(description="AI Minecraft Storytelling Server")
    parser.add_argument("--mode", choices=["real", "mock"], default="mock", help="Run with real server or mock")
    parser.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "gemini"), help="LLM Provider (gemini, openai, ollama, llamacpp)")
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL"), help="Model name (e.g. llama3.1, gpt-4o)")
    parser.add_argument("--bots", type=int, default=2, help="Number of bots to spawn")

    # LAN / Connection Args
    parser.add_argument("--host", default=os.environ.get("MC_HOST", "localhost"), help="Minecraft Server IP")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MC_PORT", "25565")), help="Minecraft Server Port")
    parser.add_argument("--orchestrator-port", type=int, default=8000, help="Port for the message bus")
    parser.add_argument("--disable-narrator", action="store_true", help="Disable Narrator & RCON (required for LAN worlds)")

    args = parser.parse_args()

    # Set MOCK_MODE env var
    if args.mode == "mock":
        os.environ["MOCK_MODE"] = "true"
    else:
        os.environ["MOCK_MODE"] = "false"

    python_executable = sys.executable

    # 1. Start Orchestrator
    print(f"Launching Orchestrator on port {args.orchestrator_port}...")
    global ORCHESTRATOR_PROCESS
    ORCHESTRATOR_PROCESS = subprocess.Popen(
        [python_executable, "-m", "uvicorn", "orchestrator.bus:app", "--host", "0.0.0.0", "--port", str(args.orchestrator_port)],
        env=os.environ.copy()
    )

    orchestrator_url = f"ws://localhost:{args.orchestrator_port}/ws"
    time.sleep(2) # Give it time to start

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

        # Start Narrator in a background thread
        def run_narrator():
            asyncio.run(NarratorAgent(game_api, llm, interval=10).run_loop())
        narrator_thread = threading.Thread(target=run_narrator, daemon=True)
        narrator_thread.start()
        print("Narrator agent started.")
    else:
        print("Narrator and RCON disabled (LAN Mode compatible).")

    # Start Agent Processes
    missions = [
        "Collect wood and build a shelter",
        "Explore the caves and find iron",
        "Farm food for the colony"
    ]

    for i in range(args.bots):
        bot_id = f"Bot{i+1}"
        mission = missions[i % len(missions)]

        print(f"Launching process for {bot_id}...")

        cmd = [python_executable, "-m", "agents.agent_process",
             "--bot-id", bot_id,
             "--mission", mission,
             "--provider", args.provider,
             "--orchestrator", orchestrator_url,
             "--mode", args.mode]

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
    reported_exits = set()
    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            for i, proc in enumerate(AGENT_PROCESSES):
                if proc.poll() is not None and i not in reported_exits:
                    print(f"Warning: Agent process {i} exited with code {proc.returncode}")
                    reported_exits.add(i)

            if len(reported_exits) == len(AGENT_PROCESSES):
                # All agents exited, but we keep running for the orchestrator/narrator unless the user stops.
                # Or maybe we should exit? Let's just keep running for now.
                pass
    except KeyboardInterrupt:
        cleanup_agents()

if __name__ == "__main__":
    main()
