import unittest

from pydantic import TypeAdapter, ValidationError

from agents.grammar import (
    BREAK_BLOCK,
    INSPECT_ZONE,
    MOUNT,
    MOVE,
    PLACE_BLOCK,
    SLEEP,
    STOP,
    THROW_ITEM,
    USE_ITEM,
    AgentAction,
)


class TestV2Grammar(unittest.TestCase):
    def setUp(self):
        self.adapter = TypeAdapter(AgentAction)

    def test_core_actions(self):
        obj = self.adapter.validate_python({"action": "MOVE", "target": "100 64 100"})
        self.assertIsInstance(obj, MOVE)

        obj = self.adapter.validate_python({"action": "STOP", "reason": "danger"})
        self.assertIsInstance(obj, STOP)

    def test_new_interactions(self):
        obj = self.adapter.validate_python({"action": "BREAK_BLOCK", "block_name": "diamond_ore"})
        self.assertIsInstance(obj, BREAK_BLOCK)
        self.assertIsNone(obj.position)

        obj = self.adapter.validate_python({"action": "BREAK_BLOCK", "position": "10 60 10"})
        self.assertIsInstance(obj, BREAK_BLOCK)

        obj = self.adapter.validate_python({
            "action": "PLACE_BLOCK",
            "block_name": "torch",
            "position": "10 61 10"
        })
        self.assertIsInstance(obj, PLACE_BLOCK)

        obj = self.adapter.validate_python({
            "action": "PLACE_BLOCK",
            "block_name": "torch",
            "near_block": "crafting_table"
        })
        self.assertIsInstance(obj, PLACE_BLOCK)

        obj = self.adapter.validate_python({
            "action": "INSPECT_ZONE",
            "corner1": "0 60 0",
            "corner2": "5 65 5"
        })
        self.assertIsInstance(obj, INSPECT_ZONE)

    def test_items_entities(self):
        obj = self.adapter.validate_python({"action": "THROW_ITEM", "item_name": "dirt", "count": 64})
        self.assertIsInstance(obj, THROW_ITEM)

        obj = self.adapter.validate_python({"action": "USE_ITEM", "item_name": "potion"})
        self.assertIsInstance(obj, USE_ITEM)

        obj = self.adapter.validate_python({"action": "MOUNT", "target": "horse"})
        self.assertIsInstance(obj, MOUNT)

        obj = self.adapter.validate_python({"action": "SLEEP", "reason": "night"})
        self.assertIsInstance(obj, SLEEP)

    def test_invalid_actions(self):
        with self.assertRaises(ValidationError):
            self.adapter.validate_python({"action": "DANCE_PARTY"})


if __name__ == '__main__':
    unittest.main()
