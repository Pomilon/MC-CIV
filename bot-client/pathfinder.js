const { Movements } = require('mineflayer-pathfinder');

function setupMovements(bot) {
  const move = new Movements(bot);
  move.allow1by1towers = true;
  move.allowParkour = true;
  move.allowSprinting = true;
  move.canDig = true;
  move.digCost = 1;
  move.placeCost = 1;

  const extraBlocks = ['oak_planks', 'spruce_planks', 'birch_planks', 'stone', 'cobblestone', 'dirt', 'oak_log', 'spruce_log', 'stone_bricks'];
  for (const name of extraBlocks) {
    if (bot.registry.itemsByName[name]) {
      move.scafoldingBlocks.push(bot.registry.itemsByName[name].id);
    }
  }

  return move;
}

function applyToBot(bot) {
  bot.pathfinder.setMovements(setupMovements(bot));
  bot.pathfinder.thinkTimeout = 15000;
}

module.exports = { setupMovements, applyToBot };
