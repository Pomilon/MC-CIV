import unittest
from agents.grammar import (
    MoveAction, SetCombatMode, SetSurvivalPreset, BuildStructure, ManageInventory
)

class TestNewGrammar(unittest.TestCase):
    def test_high_level_actions(self):
        # Combat Mode
        cmd = SetCombatMode(mode="pvp", target="Zombie")
        self.assertEqual(cmd.action, "SET_COMBAT_MODE")
        self.assertEqual(cmd.mode, "pvp")
        self.assertEqual(cmd.target, "Zombie")

        # Survival Preset
        surv = SetSurvivalPreset(preset="cowardly")
        self.assertEqual(surv.action, "SET_SURVIVAL")
        self.assertEqual(surv.preset, "cowardly")

        # Build
        build = BuildStructure(structure_type="wall", location="10 64 10")
        self.assertEqual(build.action, "BUILD")
        self.assertEqual(build.structure_type, "wall")

        # Inventory
        inv = ManageInventory(task="equip_best")
        self.assertEqual(inv.action, "INVENTORY")
        self.assertEqual(inv.task, "equip_best")

if __name__ == '__main__':
    unittest.main()
