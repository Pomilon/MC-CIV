import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from agents.controller import AgentController
from agents.llm_core import MockLLM

class TestAgentController:
    @pytest.fixture
    def controller(self):
        llm = MockLLM()
        with patch('agents.controller.StorageManager') as MockStorage:
            # Mock load return values
            instance = MockStorage.return_value
            instance.load.return_value = ([], {}, [])
            
            ctrl = AgentController("Bot1", "Survive", llm)
            ctrl.websocket = AsyncMock()
            return ctrl

    @pytest.mark.asyncio
    async def test_connect(self, controller):
        ws = AsyncMock()
        await controller.connect(ws)
        assert controller.websocket == ws

    @pytest.mark.asyncio
    async def test_handle_observation(self, controller):
        controller.websocket = AsyncMock()
        
        observation = {
            "type": "observation",
            "data": {
                "name": "Bot1",
                "health": 20,
                "position": {"x": 100, "y": 64, "z": 100},
                "chat_history": [],
                "action_state": {"status": "idle"}
            }
        }
        
        await controller.handle_message(observation)
        
        # Expect send_command called because MockLLM returns an action
        assert controller.websocket.send_json.called
        assert controller.state == "EXECUTING"

    @pytest.mark.asyncio
    async def test_handle_action_update(self, controller):
        update = {
            "type": "action_update",
            "data": {
                "status": "completed",
                "endSignal": "Done"
            }
        }
        
        await controller.handle_message(update)
        assert controller.state == "IDLE"
