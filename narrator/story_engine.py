import time
import logging
import random
import json
from infrastructure.game_state import GameStateAPI
from agents.llm_core import LLMProvider, MockLLM
from narrator.grammar import BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent

logger = logging.getLogger(__name__)

class StoryEngine:
    def __init__(self, game_state_api: GameStateAPI, llm: LLMProvider):
        self.api = game_state_api
        self.llm = llm
        self.history = []
        self.plot_points = [
            "Introduction: Welcome players to the server.",
            "Rising Action: A resource shortage or minor threat appears.",
            "Climax: A boss or major event occurs.",
            "Resolution: Peace is restored."
        ]
        self.current_plot_index = 0

    def check_global_state(self):
        try:
            players = self.api.get_online_players()
            if not players:
                # logger.info("No players online. Narrator waiting...")
                return

            day_time = self.api.get_time()
            current_plot = self.plot_points[self.current_plot_index]
            
            system_prompt = f"""
            You are the AI Narrator. Current Plot: {current_plot}
            Generate a 'Virtual Intervention' to advance the plot.
            Output a strictly formatted JSON action using the provided tools.
            """
            
            state_summary = f"Players: {players}, Time: {day_time}, Recent: {self.history[-3:]}"
            user_prompt = f"Game State: {state_summary}"
            
            narrator_tools = [BroadcastEvent, SpawnEvent, WeatherEvent, WaitEvent]
            
            # generate_response now handles dynamic tools
            response_args = self.llm.generate_response(system_prompt, user_prompt, tools=narrator_tools)
            
            # Infer action type if not explicitly returned (Gemini function name is lost in my simple dict return)
            # Actually, I should fix LLMProvider to return the function name.
            # But wait, my Pydantic models have `action: Literal["..."] = "..."`
            # So the args SHOULD contain the action key!
            
            self.execute_narrator_action(response_args)
            
        except Exception as e:
            logger.error(f"Narrator Error: {e}")

    def execute_narrator_action(self, action: dict):
        act_type = action.get("action")
        logger.info(f"Narrator Action: {act_type} -> {action}")
        
        if act_type == "BROADCAST":
            self.api.broadcast_message(action.get("message"))
            self.history.append(f"Narrator: {action.get('message')}")
            
        elif act_type == "SPAWN":
            entity = action.get("entity_type")
            loc = action.get("location")
            # Logic to parse location...
            self.api.spawn_entity(entity, 0, 70, 0) # simplified
            self.history.append(f"Spawned {entity}")
            
        elif act_type == "WEATHER":
            self.api.set_weather(action.get("type"))
            self.history.append(f"Weather: {action.get('type')}")
    
    def run_loop(self, interval=20):
        logger.info("Starting Narrator Loop")
        while True:
            self.check_global_state()
            time.sleep(interval)
