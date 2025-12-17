// bot-client/index.js - Robust Async Task System
const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const collectBlock = require('mineflayer-collectblock').plugin
const autoEatModule = require('mineflayer-auto-eat')
const autoEat = autoEatModule.plugin || autoEatModule.default || autoEatModule

const express = require('express')
const bodyParser = require('body-parser')
const { canChat, recordChat } = require('./utils/chat_manager')
const Vec3 = require('vec3')

// Import behaviors
const combatBehavior = require('./behaviors/combat')
const buildingBehavior = require('./behaviors/building')
const survivalBehavior = require('./behaviors/survival')
const explorationBehavior = require('./behaviors/exploration')
const automationBehavior = require('./behaviors/automation')
const autonomyBehavior = require('./behaviors/autonomy')

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

// --- State Management ---
let actionState = {
    id: null,
    type: 'IDLE',
    status: 'idle', // idle, running, completed, failed
    data: null,
    error: null,
    endSignal: null, // "TargetDead", "Arrived", "InventoryFull", etc.
    startTime: 0
}

function updateState(status, signal = null, error = null, data = null) {
    actionState.status = status
    if (signal) actionState.endSignal = signal
    if (error) actionState.error = error
    if (data) actionState.data = data
}

function startAction(type, data) {
    if (actionState.status === 'running') {
        stopCurrentAction("Interrupted by new command")
    }

    const id = Date.now().toString()
    actionState = {
        id: id,
        type: type,
        status: 'running',
        data: data, // Input data
        error: null,
        endSignal: null,
        startTime: Date.now()
    }
    return id
}

function stopCurrentAction(reason) {
    if (bot && bot.pathfinder) bot.pathfinder.stop()
    if (bot && bot.pvp) bot.pvp.stop()
    // Add other stops
    updateState('failed', 'Interrupted', reason)
}

function cleanupBot() {
    if (!bot) return
    console.log("Cleaning up bot instance...")
    
    // Remove all listeners to prevent memory leaks
    bot.removeAllListeners()
    
    // Explicitly stop pathfinding/pvp if possible to clear intervals
    if (bot.pathfinder) bot.pathfinder.stop()
    if (bot.pvp) bot.pvp.stop()
    
    bot = null
}

// --- Helper Interface for Autonomy ---
const actionInterface = {
    startAction: (type, data) => {
        console.log(`[InternalAction] Starting ${type}`, data)
        startAction(type, data)
    },
    stopAction: (reason) => {
        stopCurrentAction(reason)
    },
    isBusy: () => {
        return actionState.status === 'running'
    },
    getActionType: () => {
         return actionState.type
    }
}

function initBot() {
  if (bot) cleanupBot()
  
  console.log(`Starting bot ${botOptions.username}...`)
  try {
      bot = mineflayer.createBot(botOptions)
  } catch (err) {
      console.error("Failed to create bot:", err)
      setTimeout(initBot, 10000)
      return
  }

  // Load plugins
  bot.loadPlugin(pathfinder)
  bot.loadPlugin(collectBlock)
  
  if (typeof autoEat === 'function') {
      bot.loadPlugin(autoEat)
  }
  
  // Setup behaviors
  combatBehavior.setup(bot)
  buildingBehavior.setup(bot)
  survivalBehavior.setup(bot)
  explorationBehavior.setup(bot)
  autonomyBehavior.setup(bot, actionInterface)

  bot.on('spawn', () => {
    console.log('Bot spawned')
    const defaultMove = new Movements(bot)
    bot.pathfinder.setMovements(defaultMove)

    if (actionState.status === 'running') {
        updateState('failed', 'BotRestarted', 'Connection reset during action')
    }
  })

  bot.on('chat', (username, message) => {
    if (username === bot.username) return
    
    const player = bot.players[username]
    const isNearby = player && player.entity && bot.entity.position.distanceTo(player.entity.position) < 20
    const isMention = message.toLowerCase().includes(bot.username.toLowerCase())
    
    if (isNearby || isMention) {
        chatHistory.push({ username, message, time: Date.now(), nearby: isNearby, mention: isMention })
        if (chatHistory.length > 50) chatHistory.shift()
    }
  })
  
  // Error & Reconnection Handling
  const handleDisconnect = (reason) => {
      console.log(`Bot disconnected/kicked: ${reason}. Reconnecting in 5s...`)
      if (actionState.status === 'running') {
          updateState('failed', 'Disconnected', reason || 'Connection lost')
      }
      if (bot) cleanupBot() 
      setTimeout(initBot, 5000)
  }

  bot.on('kicked', (reason) => handleDisconnect(`Kicked: ${reason}`))
  bot.on('error', (err) => handleDisconnect(`Error: ${err.message}`))
  bot.on('end', (reason) => handleDisconnect(`End: ${reason}`))
}

initBot()

function getBlockByName(name) {
  try {
    const blockIds = bot.registry.blocksByName[name].id
    return bot.findBlock({ matching: blockIds, maxDistance: 32 })
  } catch (e) { return null }
}

// --- Action Executors ---
// Each executor returns a Promise that resolves when done or rejects on failure.

async function executeMove(target) {
    return new Promise((resolve, reject) => {
        const defaultMove = new Movements(bot)
        defaultMove.allow1by1towers = false // Prevent pillar jumping if not needed
        bot.pathfinder.setMovements(defaultMove)

        let goal = null
        const coords = target.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
        
        if (coords) {
             const x = parseInt(coords[1])
             const y = parseInt(coords[2])
             const z = parseInt(coords[3])
             goal = new goals.GoalNear(x, y, z, 1)
        } else {
            const player = bot.players[target]
            if (player && player.entity) {
                goal = new goals.GoalNear(player.entity.position.x, player.entity.position.y, player.entity.position.z, 1)
            } else {
                 const block = getBlockByName(target)
                 if (block) {
                     goal = new goals.GoalNear(block.position.x, block.position.y, block.position.z, 1)
                 }
            }
        }

        if (!goal) return reject("Target not found")

        bot.pathfinder.setGoal(goal)
        
        let stuckCount = 0
        
        const cleanup = () => {
            bot.removeListener('goal_reached', onGoalReached)
            bot.removeListener('path_update', onPathUpdate)
            bot.removeListener('stuck', onStuck)
        }

        const onGoalReached = () => {
            cleanup()
            resolve("Arrived")
        }

        const onPathUpdate = (r) => {
            if (r.status === 'noPath') {
                cleanup()
                reject("No Path Found")
            }
        }
        
        const onStuck = async () => {
            stuckCount++
            console.log(`[Move] Bot stuck! Attempt ${stuckCount}/3`)
            
            if (stuckCount > 3) {
                cleanup()
                reject("Bot stuck and cannot free itself")
                return
            }
            
            // Recovery: Stop, Jump Randomly, Retry
            bot.pathfinder.stop()
            bot.setControlState('jump', true)
            bot.setControlState('forward', true)
            if (Math.random() > 0.5) bot.setControlState('left', true)
            else bot.setControlState('right', true)
            
            setTimeout(() => {
                bot.clearControlStates()
                // Retry pathing
                bot.pathfinder.setGoal(goal)
            }, 1000)
        }

        bot.on('goal_reached', onGoalReached)
        bot.on('path_update', onPathUpdate)
        bot.on('stuck', onStuck)
    })
}

async function executeMine(blockName, count = 1) {
    const block = getBlockByName(blockName)
    if (!block) throw new Error("Block not found")
    
    return new Promise((resolve, reject) => {
        const defaultMove = new Movements(bot)
        bot.pathfinder.setMovements(defaultMove)

        bot.collectBlock.collect(block, { 
             chestLocations: [], 
             itemFilter: () => true
         }, err => { 
             if (err) reject(err.message)
             else resolve("BlockMined")
         })
    })
}

function withTimeout(promise, ms, label = "Operation") {
    return Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} Timed Out after ${ms}ms`)), ms))
    ])
}

async function executeCraft(itemName, count = 1) {
    const item = bot.registry.itemsByName[itemName]
    if(!item) throw new Error("Unknown item")
    
    // Find recipe
    const recipes = bot.recipesFor(item.id, null, 1, null)
    if (!recipes || recipes.length === 0) throw new Error("No recipe or resources found")
    
    const recipe = recipes[0]
    
    return withTimeout(new Promise((resolve, reject) => {
        const qty = Math.floor(count)
        try {
            bot.craft(recipe, qty, null, (err) => { 
                if (err) {
                    // Normalize error to string to avoid circular json issues if any
                    reject(new Error(err.message || err))
                } else {
                    resolve(`Crafted_${qty}_${itemName}`)
                }
            })
        } catch (e) {
            reject(new Error(`Crafting Synchronous Error: ${e.message}`))
        }
    }), 5000 + (count * 100), "Crafting")
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
      .map(e => ({ type: e.type, name: e.username || e.displayName || e.mobType, position: e.position })),
    nearby_blocks: uniqueBlocks,
    chat_history: chatHistory.slice(-5),
    time: bot.time.timeOfDay,
    mission: mission,
    action_state: actionState,
    autonomy_config: autonomyBehavior.getConfig()
  }
  res.json(observation)
})

app.post('/act', async (req, res) => {
  const { action, ...params } = req.body
  console.log(`[${bot.username}] Recv:`, action, params)

  if (!bot || !bot.entity) {
    return res.status(503).json({ error: 'Bot not ready' })
  }

  const actionId = startAction(action, params)
  res.json({ status: 'started', action_id: actionId })

  try {
      let resultSignal = "Done"

      switch (action) {
        case 'CONFIGURE':
            resultSignal = await autonomyBehavior.configure(bot, params.mode, params.setting)
            break

        case 'CHAT':
            if (canChat(bot)) {
                bot.chat(params.message)
                recordChat(bot)
                chatHistory.push({ username: bot.username, message: params.message, time: Date.now() })
                resultSignal = "MessageSent"
            } else {
                throw new Error("ChatCooldown")
            }
            break
        
        case 'MOVE':
            resultSignal = await executeMove(params.target)
            break
        
        case 'MINE':
            resultSignal = await executeMine(params.block_name, params.count)
            break

        case 'GATHER':
            resultSignal = await survivalBehavior.gatherResource(bot, params.resource, params.count)
            break

        case 'HUNT':
            resultSignal = await combatBehavior.huntCreature(bot, params.creature_name, params.count)
            break

        case 'COLLECT_ITEM':
            resultSignal = await survivalBehavior.findAndCollect(bot, params.item_name, params.count)
            break
        
        case 'CRAFT':
            resultSignal = await executeCraft(params.item_name, params.count)
            break
        
        case 'EQUIP':
            const itemToEquip = bot.inventory.items().find(i => i.name === params.item_name)
            if (!itemToEquip) throw new Error("ItemNotInInventory")
            await bot.equip(itemToEquip, params.slot || 'hand')
            resultSignal = "Equipped"
            break
        
        case 'IDLE':
            stopCurrentAction("IdleRequested")
            resultSignal = "Idling"
            break

        case 'STOP':
            stopCurrentAction("StopCommand")
            resultSignal = "Stopped"
            break
        
        case 'SET_COMBAT_MODE':
            if (params.mode === 'pvp') {
                if (!params.target) throw new Error("TargetRequiredForPvP")
                resultSignal = await combatBehavior.engageTarget(bot, params.target)
            } else {
                if (bot.pvp) bot.pvp.stop()
                resultSignal = "CombatStopped"
            }
            break

        case 'BUILD':
            resultSignal = await buildingBehavior.buildStructure(
                bot, 
                params.shape, 
                params.material, 
                params.dimensions, 
                params.location
            )
            break

        case 'PLACE_BLOCK':
            let placePos = null
            if (params.position) {
                 const pCoords = params.position.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
                 if (pCoords) {
                     placePos = new Vec3(parseInt(pCoords[1]), parseInt(pCoords[2]), parseInt(pCoords[3]))
                 }
            }
            resultSignal = await buildingBehavior.placeBlock(bot, params.block_name, placePos, params.near_block)
            break

        case 'INSPECT_ZONE':
             const c1 = params.corner1.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
             const c2 = params.corner2.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
             if (!c1 || !c2) throw new Error("Invalid Coordinates")
             
             const v1 = new Vec3(parseInt(c1[1]), parseInt(c1[2]), parseInt(c1[3]))
             const v2 = new Vec3(parseInt(c2[1]), parseInt(c2[2]), parseInt(c2[3]))
             
             const blocks = await buildingBehavior.inspectZone(bot, v1, v2)
             resultSignal = "ZoneInspected"
             updateState('completed', resultSignal, null, blocks)
             return 
             
        case 'SMELT':
            resultSignal = await automationBehavior.smeltItem(bot, params.item_name, params.fuel_name, params.count)
            break
            
        case 'DEPOSIT':
            resultSignal = await automationBehavior.depositToChest(bot, params.item_name, params.count)
            break
            
        case 'FARM':
            resultSignal = await automationBehavior.farmLoop(bot, params.mode, params.crop_name, params.count)
            break
            
        case 'CLEAR_AREA':
             const cc1 = params.corner1.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
             const cc2 = params.corner2.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
             if (!cc1 || !cc2) throw new Error("Invalid Coordinates")
             
             const cv1 = new Vec3(parseInt(cc1[1]), parseInt(cc1[2]), parseInt(cc1[3]))
             const cv2 = new Vec3(parseInt(cc2[1]), parseInt(cc2[2]), parseInt(cc2[3]))
             
             resultSignal = await buildingBehavior.clearArea(bot, cv1, cv2)
             break

        case 'INVENTORY':
            resultSignal = await survivalBehavior.manageInventory(bot, params.task)
            break
            
        case 'INTERACT':
            const iBlock = getBlockByName(params.target_block)
            if (!iBlock) throw new Error("BlockNotFound")
            await bot.activateBlock(iBlock)
            resultSignal = "Interacted"
            break

        case 'BREAK_BLOCK':
            let breakPos = null
            if (params.position) {
                 const bCoords = params.position.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
                 if (bCoords) {
                     breakPos = new Vec3(parseInt(bCoords[1]), parseInt(bCoords[2]), parseInt(bCoords[3]))
                 }
            }
            resultSignal = await survivalBehavior.breakBlock(bot, params.block_name, breakPos)
            break

        case 'THROW_ITEM':
            resultSignal = await survivalBehavior.throwItem(bot, params.item_name, params.count)
            break

        case 'USE_ITEM':
            resultSignal = await survivalBehavior.useItem(bot, params.item_name)
            break

        case 'MOUNT':
            resultSignal = await survivalBehavior.mountEntity(bot, params.target)
            break

        case 'DISMOUNT':
            resultSignal = await survivalBehavior.dismountEntity(bot)
            break
            
        case 'SLEEP':
            resultSignal = await survivalBehavior.sleep(bot)
            break
            
        case 'WAKE':
            resultSignal = await survivalBehavior.wake(bot)
            break

        case 'SET_EXPLORATION_MODE':
            if (params.mode === 'wander') {
                resultSignal = await explorationBehavior.wander(bot)
            } else if (params.mode === 'map') {
                resultSignal = await explorationBehavior.exploreMap(bot)
            } else if (params.mode === 'find_biome') {
                 if (!params.target) throw new Error("Target biome required")
                 resultSignal = await explorationBehavior.findBiome(bot, params.target)
            } else if (params.mode === 'follow') {
                if (!params.target) throw new Error("TargetRequiredForFollow")
                resultSignal = await explorationBehavior.follow(bot, params.target)
            } else if (params.mode === 'stop') {
                stopCurrentAction("StopExploration")
                resultSignal = "ExplorationStopped"
            } else {
                throw new Error("Unknown exploration mode")
            }
            break

        default:
            throw new Error(`Unknown action: ${action}`)
      }
      
      updateState('completed', resultSignal)
  } catch (err) {
      console.error("Action Error:", err)
      updateState('failed', null, err.message || err)
  }
})

app.listen(PORT, () => {
  console.log(`Bot Client API listening on port ${PORT}`)
})