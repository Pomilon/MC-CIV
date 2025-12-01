// bot-client/index.js update for Exploration
const mineflayer = require('mineflayer')
const { pathfinder, movements, goals } = require('mineflayer-pathfinder')
const { GoalNear, GoalBlock } = goals
const collectBlock = require('mineflayer-collectblock').plugin
const express = require('express')
const bodyParser = require('body-parser')
const { canChat, recordChat } = require('./utils/chat_manager')
const Vec3 = require('vec3')

// Import behaviors
const combatBehavior = require('./behaviors/combat')
const buildingBehavior = require('./behaviors/building')
const survivalBehavior = require('./behaviors/survival')
const explorationBehavior = require('./behaviors/exploration')

const app = express()
app.use(bodyParser.json())

const PORT = process.env.PORT || 3000

const botOptions = {
  host: process.env.MC_HOST || 'localhost',
  port: parseInt(process.env.MC_PORT) || 25565,
  username: process.env.MC_USERNAME || 'Bot1',
  auth: 'offline'
}

let bot
let chatHistory = []
let mission = process.env.MISSION || "Survive and Explore"

// State tracking
let behaviorState = {
    combatMode: 'none',
    survivalPreset: 'neutral',
    explorationMode: 'stop',
    currentActivity: 'idle'
}

function initBot() {
  console.log(`Starting bot ${botOptions.username}...`)
  bot = mineflayer.createBot(botOptions)

  bot.loadPlugin(pathfinder)
  bot.loadPlugin(collectBlock)
  
  // Setup behaviors
  combatBehavior.setup(bot)
  buildingBehavior.setup(bot)
  survivalBehavior.setup(bot)
  explorationBehavior.setup(bot)

  bot.on('spawn', () => {
    console.log('Bot spawned')
  })

  bot.on('chat', (username, message) => {
    if (username === bot.username) return
    const player = bot.players[username]
    if (player && player.entity && bot.entity.position.distanceTo(player.entity.position) < 20) {
        chatHistory.push({ username, message, time: Date.now() })
        if (chatHistory.length > 50) chatHistory.shift()
    }
  })
  
  bot.on('kicked', console.log)
  bot.on('error', console.log)
  bot.on('end', () => {
      console.log('Bot disconnected. Reconnecting in 5s...')
      setTimeout(initBot, 5000)
  })
}

initBot()

function getBlockByName(name) {
  try {
    const blockIds = bot.registry.blocksByName[name].id
    return bot.findBlock({ matching: blockIds, maxDistance: 32 })
  } catch (e) { return null }
}

// --- API Endpoints ---

app.get('/observe', (req, res) => {
  if (!bot || !bot.entity) {
    return res.status(503).json({ error: 'Bot not ready' })
  }

  const nearbyBlocks = bot.findBlocks({
      matching: (blk) => {
          return blk.name !== 'air' && blk.name !== 'grass_block' && blk.name !== 'dirt' && blk.name !== 'stone'
      }, 
      maxDistance: 8, 
      count: 20
  }).map(pos => bot.blockAt(pos).name)

  const uniqueBlocks = [...new Set(nearbyBlocks)]

  const observation = {
    name: bot.username,
    health: bot.health,
    food: bot.food,
    position: bot.entity.position,
    inventory: bot.inventory.items().map(item => ({ name: item.name, count: item.count })),
    nearby_entities: Object.values(bot.entities)
      .filter(e => e.id !== bot.entity.id && bot.entity.position.distanceTo(e.position) < 15)
      .map(e => ({ type: e.type, name: e.username || e.mobType, position: e.position })),
    nearby_blocks: uniqueBlocks,
    chat_history: chatHistory.slice(-5),
    time: bot.time.timeOfDay,
    mission: mission,
    behavior_state: behaviorState 
  }
  res.json(observation)
})

app.post('/act', async (req, res) => {
  const { action, ...params } = req.body
  console.log(`[${bot.username}] Executing:`, action, params)

  if (!bot || !bot.entity) {
    return res.status(503).json({ error: 'Bot not ready' })
  }

  try {
    let result = { status: 'success' }
    
    // Explicitly disabling conflict behaviors if entering a new directive
    // Ideally this logic should be centralized
    
    switch (action) {
      // --- Core Actions ---
      case 'CHAT':
        if (canChat(bot)) {
            bot.chat(params.message)
            recordChat(bot)
            chatHistory.push({ username: bot.username, message: params.message, time: Date.now() })
        } else {
            result = { status: 'skipped', reason: 'cooldown' }
        }
        break
      
      case 'MOVE':
        const target = params.target
        const defaultMove = new movements(bot)
        bot.pathfinder.setMovements(defaultMove)
        
        // Reset modes
        combatBehavior.setCombatMode(bot, 'none')
        behaviorState.combatMode = 'none'
        explorationBehavior.setExplorationMode(bot, 'stop')
        behaviorState.explorationMode = 'stop'

        const coords = target.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
        if (coords) {
             const x = parseInt(coords[1])
             const y = parseInt(coords[2])
             const z = parseInt(coords[3])
             bot.pathfinder.setGoal(new goals.GoalNear(x, y, z, 1))
        } else {
            const player = bot.players[target]
            if (player && player.entity) {
              const p = player.entity.position
              bot.pathfinder.setGoal(new goals.GoalNear(p.x, p.y, p.z, 1))
            } else {
                 const block = getBlockByName(target)
                 if (block) {
                     bot.pathfinder.setGoal(new goals.GoalNear(block.position.x, block.position.y, block.position.z, 1))
                 } else {
                     result = { status: 'failed', reason: 'target not found' }
                 }
            }
        }
        break
      
      case 'MINE':
         const blockName = params.block_name
         const block = getBlockByName(blockName)
         if (block) {
             bot.collectBlock.collect(block, err => { if (err) console.log(err) })
         } else {
             result = { status: 'failed', reason: 'block not found' }
         }
         break

      case 'CRAFT':
          const itemName = params.item_name
          const recipe = bot.recipesFor(bot.registry.itemsByName[itemName].id, null, 1, null)[0]
          if (recipe) {
              bot.craft(recipe, 1, null, (err) => { if (err) console.log("Crafting failed", err) })
          } else {
              result = { status: 'failed', reason: 'no recipe or resources' }
          }
          break

      case 'EQUIP':
          const equipItem = params.item_name
          const slot = params.slot || 'hand'
          const itemToEquip = bot.inventory.items().find(i => i.name === equipItem)
          if (itemToEquip) {
              bot.equip(itemToEquip, slot, (err) => { if(err) console.log("Equip failed", err) })
          } else {
             result = { status: 'failed', reason: 'item not in inventory' }
          }
          break
      
      case 'IDLE':
          bot.pathfinder.setGoal(null)
          combatBehavior.setCombatMode(bot, 'none')
          explorationBehavior.setExplorationMode(bot, 'stop')
          break

      // --- High Level Directives ---
      
      case 'SET_COMBAT_MODE':
          const combatRes = combatBehavior.setCombatMode(bot, params.mode, params.target)
          behaviorState.combatMode = params.mode
          if (params.mode === 'pvp') behaviorState.explorationMode = 'stop' # Conflict resolution
          result = combatRes
          break

      case 'SET_SURVIVAL':
          const survRes = combatBehavior.setSurvivalPreset(bot, params.preset)
          behaviorState.survivalPreset = params.preset
          result = survRes
          break

      case 'BUILD':
          // Parse location
          let buildPos = bot.entity.position
          if (params.location) {
              const bCoords = params.location.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
              if (bCoords) {
                  buildPos = new Vec3(parseInt(bCoords[1]), parseInt(bCoords[2]), parseInt(bCoords[3]))
              }
          }
          const buildRes = await buildingBehavior.buildStructure(bot, params.structure_type, buildPos)
          result = buildRes
          break

      case 'INVENTORY':
          const invRes = await survivalBehavior.manageInventory(bot, params.task)
          result = invRes
          break
          
      case 'SET_EXPLORATION_MODE':
          const exploreRes = explorationBehavior.setExplorationMode(bot, params.mode, params.target)
          behaviorState.explorationMode = params.mode
          if (params.mode !== 'stop') behaviorState.combatMode = 'none' # Conflict resolution
          result = exploreRes
          break

      default:
        console.log(`Unknown action: ${action}`)
        result = { status: 'error', reason: 'unknown action' }
    }
    res.json(result)
  } catch (error) {
    console.error("Action failed", error)
    res.status(500).json({ error: error.message })
  }
})

app.listen(PORT, () => {
  console.log(`Bot Client API listening on port ${PORT}`)
})
