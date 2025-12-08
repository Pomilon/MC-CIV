import unittest
from pydantic import TypeAdapter, ValidationError
from agents.grammar import (
    AgentAction, MoveAction, AttackAction, BuildStructure, 
    PlaceBlock, BreakBlock, InspectZone, ThrowItem, UseItem,
    MountEntity, Sleep, StopAction
)

class TestV2Grammar(unittest.TestCase):
    def setUp(self):
        self.adapter = TypeAdapter(AgentAction)

    def test_core_actions(self):
        # Move
        obj = self.adapter.validate_python({"action": "MOVE", "target": "100 64 100"})
        self.assertIsInstance(obj, MoveAction)
        
        # Stop
        obj = self.adapter.validate_python({"action": "STOP", "reason": "danger"})
        self.assertIsInstance(obj, StopAction)

    def test_new_interactions(self):
        # Break Block (Search)
        obj = self.adapter.validate_python({"action": "BREAK_BLOCK", "block_name": "diamond_ore"})
        self.assertIsInstance(obj, BreakBlock)
        self.assertIsNone(obj.position)

        # Break Block (Coords)
        obj = self.adapter.validate_python({"action": "BREAK_BLOCK", "position": "10 60 10"})
        self.assertIsInstance(obj, BreakBlock)
        
        # Place Block (Coords)
        obj = self.adapter.validate_python({
            "action": "PLACE_BLOCK", 
            "block_name": "torch", 
            "position": "10 61 10"
        })
        self.assertIsInstance(obj, PlaceBlock)

        # Place Block (Near)
        obj = self.adapter.validate_python({
            "action": "PLACE_BLOCK", 
            "block_name": "torch", 
            "near_block": "crafting_table"
        })
        self.assertIsInstance(obj, PlaceBlock)
        
        # Inspect Zone
        obj = self.adapter.validate_python({
            "action": "INSPECT_ZONE",
            "corner1": "0 60 0",
            "corner2": "5 65 5"
        })
        self.assertIsInstance(obj, InspectZone)

    def test_items_entities(self):
        # Throw
        obj = self.adapter.validate_python({"action": "THROW_ITEM", "item_name": "dirt", "count": 64})
        self.assertIsInstance(obj, ThrowItem)
        
        # Use
        obj = self.adapter.validate_python({"action": "USE_ITEM", "item_name": "potion"})
        self.assertIsInstance(obj, UseItem)
        
        # Mount
        obj = self.adapter.validate_python({"action": "MOUNT", "target": "horse"})
        self.assertIsInstance(obj, MountEntity)
        
        # Sleep
        obj = self.adapter.validate_python({"action": "SLEEP", "reason": "night"})
        self.assertIsInstance(obj, Sleep)

    def test_invalid_actions(self):
        # Invalid Action Name
        with self.assertRaises(ValidationError):
            self.adapter.validate_python({"action": "DANCE_PARTY"})

if __name__ == '__main__':
    unittest.main()
