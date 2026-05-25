import argparse
import asyncio
import json
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from agents.agent import AgentController
from agents.llm_core import get_llm_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger("AgentProcess")

class AgentProcess:
    def __init__(self, bot_id, mission, provider="gemini", model_name=None, profile_path=None, orchestrator_url="ws://localhost:8000/ws", mode="mock"):
        self.bot_id = bot_id
        self.mission = mission
        self.provider = provider
        self.model_name = model_name
        self.profile_path = profile_path
        self.orchestrator_url = orchestrator_url
        self.mode = mode
        self.node_process = None

    async def start_node_bot(self):
        env = os.environ.copy()
        env["MC_USERNAME"] = self.bot_id
        env["MISSION"] = self.mission
        env["ORCHESTRATOR_URL"] = self.orchestrator_url
        env["MOCK_MODE"] = "true" if self.mode == "mock" else "false"

        logger.info(f"Spawning Node.js bot {self.bot_id} (Mode: {self.mode}) connecting to {self.orchestrator_url}...")

        self.node_process = await asyncio.create_subprocess_exec(
            "node", "index.js",
            cwd="bot-client",
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )

    async def run(self):
        # 1. Initialize Controller (Brain)
        logger.info(f"Initializing Brain for {self.bot_id}...")

        llm_kwargs = {}
        if self.model_name:
            llm_kwargs["model_name"] = self.model_name

        llm = get_llm_provider(self.provider, **llm_kwargs)

        profile = None
        if self.profile_path:
            try:
                with open(self.profile_path) as f:
                    profile = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load profile {self.profile_path}: {e}")

        controller = AgentController(
            self.bot_id,
            self.mission,
            llm,
            orchestrator_url=self.orchestrator_url,
            profile=profile,
        )

        # 2. Start Brain & Node Bot concurrently
        logger.info(f"Starting Brain & Body for {self.bot_id}...")

        brain_task = asyncio.create_task(controller.run())
        await asyncio.sleep(2) # Give brain a moment
        await self.start_node_bot()

        # 3. Wait for Node Bot to finish (or crash)
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
            brain_task.cancel()
            try:
                await brain_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--provider", default=os.environ.get("LLM_PROVIDER", "gemini"))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL"))
    parser.add_argument("--profile", default=None)
    parser.add_argument("--orchestrator", default="ws://localhost:8000/ws")
    parser.add_argument("--mode", default="mock")
    args = parser.parse_args()

    agent = AgentProcess(
        args.bot_id,
        args.mission,
        args.provider,
        args.model,
        args.profile,
        orchestrator_url=args.orchestrator,
        mode=args.mode
    )

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass
