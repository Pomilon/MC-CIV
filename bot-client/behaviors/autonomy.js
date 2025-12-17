// bot-client/behaviors/autonomy.js

// Global Configuration State
let config = {
    self_defense: 'ignore', // 'fight', 'flee', 'ignore'
    auto_eat: true,
    auto_sleep: false,
    auto_collect: false,
    low_health_threshold: 6, // Hearts? Or health points (20 max). 6 = 3 hearts.
    low_health_action: 'flee', // 'flee', 'none'
    on_totem_pop: 'flee', // 'flee', 'none'
    auto_tool_swap: true,
    chat_interrupt: true
}

function setup(bot, actions) {
    // actions: { startAction, stopAction, isBusy, getActionType }
    
    // 0. Chat Listener (Interrupt on Talk)
    bot.on('chat', (username, message) => {
        if (!config.chat_interrupt) return
        if (username === bot.username) return
        if (actions.getActionType() === 'CHAT') return // Don't interrupt chatting with chat
        
        // We rely on index.js to filter noise usually, but here we listen to raw event.
        // We want to interrupt IF:
        // 1. Explicit mention
        // 2. Very close proximity (< 10 blocks)
        
        const isMention = message.toLowerCase().includes(bot.username.toLowerCase())
        let isClose = false
        const player = bot.players[username]
        if (player && player.entity) {
            const dist = player.entity.position.distanceTo(bot.entity.position)
            if (dist < 10) isClose = true
        }
        
        if (isMention || isClose) {
            // Check priority?
            // If fighting, maybe don't stop?
            const current = actions.getActionType()
            if (current === 'SET_COMBAT_MODE' || current === 'HUNT') {
                if (!isMention) return // Ignore ambient chat while fighting
            }
            
            console.log(`[Autonomy] Chat Interrupt from ${username}`)
            actions.stopAction(`Interrupt: Chat from ${username}`)
        }
    })

    // 1. Self Defense Listener (Attacked)
    bot.on('entityHurt', (entity) => {
        if (entity !== bot.entity) return
        if (config.self_defense === 'ignore') return
        
        // Prevent feedback loop if we are already fighting
        if (actions.getActionType() === 'SET_COMBAT_MODE' || actions.getActionType() === 'HUNT') return

        const attacker = bot.nearestEntity(e => e.type === 'hostile' && e.position.distanceTo(bot.entity.position) < 8)
        
        if (attacker) {
            console.log(`[Autonomy] Under Attack by ${attacker.name}! Mode: ${config.self_defense}`)
            
            if (config.self_defense === 'fight') {
                actions.stopAction("Interrupt: Self-Defense Fight")
                actions.startAction('SET_COMBAT_MODE', { mode: 'pvp', target: attacker.username || attacker.name || attacker.mobType })
            } else if (config.self_defense === 'flee') {
                actions.stopAction("Interrupt: Self-Defense Flee")
                actions.startAction('SET_EXPLORATION_MODE', { mode: 'wander' })
            }
        }
    })

    // 2. Low Health Monitor
    bot.on('health', () => {
        if (bot.health < config.low_health_threshold) {
             // Avoid spamming if already fleeing
             if (config.low_health_action === 'flee') {
                  const current = actions.getActionType()
                  // If we are already running or idle, maybe fine? 
                  // If we are building/mining, we MUST stop.
                  if (current !== 'SET_EXPLORATION_MODE' && current !== 'IDLE') {
                      console.log(`[Autonomy] Low Health (${bot.health})! Triggering Flee.`)
                      actions.stopAction("Interrupt: Low Health Flee")
                      actions.startAction('SET_EXPLORATION_MODE', { mode: 'wander' })
                  }
             }
        }
    })

    // 3. Totem Pop
    // 'entityStatus' fires for all entities. status 35 is totem pop.
    bot.on('entityStatus', (entity, status) => {
        if (entity !== bot.entity) return
        if (status === 35) {
             console.log("[Autonomy] Totem Popped!")
             if (config.on_totem_pop === 'flee') {
                 actions.stopAction("Interrupt: Totem Pop Panic")
                 actions.startAction('SET_EXPLORATION_MODE', { mode: 'wander' })
             }
             if (config.auto_tool_swap) {
                 const totem = bot.inventory.items().find(i => i.name === 'totem_of_undying')
                 if (totem) {
                     bot.equip(totem, 'off-hand').catch(e => {})
                 }
             }
        }
    })
    
    // 4. Auto Tool Swap (On Block Break)
    // If we break a block, check tool durability.
    bot.on('diggingCompleted', (block) => {
        if (!config.auto_tool_swap) return
        
        const held = bot.heldItem
        if (!held) return
    })

    // 5. Auto Sleep
    bot.on('time', () => {
        if (!config.auto_sleep) return
        if (bot.time.isDay) return
        if (actions.isBusy()) return 
        if (actions.getActionType() === 'SLEEP') return
        
        console.log("[Autonomy] Night time - attempting auto-sleep")
        actions.startAction('SLEEP', {})
    })
    
    // 6. Auto Collect
    setInterval(() => {
        if (!config.auto_collect) return
        if (actions.isBusy()) return
        
        const item = bot.nearestEntity(e => e.name === 'item' && bot.entity.position.distanceTo(e.position) < 10)
        if (item) {
             console.log("[Autonomy] Found item - auto collecting")
             actions.startAction('COLLECT_ITEM', { item_name: item.getDroppedItem()?.name || 'unknown', count: 1 })
        }
    }, 5000)
}

async function configure(bot, mode, setting) {
    console.log(`[Autonomy] Config Change: ${mode} = ${setting}`)
    
    if (mode === 'self_defense') {
        if (['fight', 'flee', 'ignore'].includes(setting)) config.self_defense = setting
        else throw new Error("Invalid setting. Use 'fight', 'flee', 'ignore'.")
        
    } else if (mode === 'low_health_action') {
        if (['flee', 'none'].includes(setting)) config.low_health_action = setting
        else throw new Error("Invalid setting. Use 'flee', 'none'.")
        
    } else if (mode === 'on_totem_pop') {
        if (['flee', 'none'].includes(setting)) config.on_totem_pop = setting
        else throw new Error("Invalid setting. Use 'flee', 'none'.")

    } else if (mode === 'low_health_threshold') {
        const val = parseInt(setting)
        if (isNaN(val)) throw new Error("Must be a number")
        config.low_health_threshold = val

    } else if (mode === 'auto_eat') {
        const val = (setting === 'true')
        config.auto_eat = val
        if (bot.autoEat) {
            if (val) bot.autoEat.enable()
            else bot.autoEat.disable()
        }
    } else if (mode === 'auto_sleep') {
        config.auto_sleep = (setting === 'true')
    } else if (mode === 'auto_collect') {
        config.auto_collect = (setting === 'true')
    } else if (mode === 'auto_tool_swap') {
        config.auto_tool_swap = (setting === 'true')
    } else if (mode === 'chat_interrupt') {
        config.chat_interrupt = (setting === 'true')
    } else {
        throw new Error(`Unknown mode: ${mode}`)
    }
    
    return `Configured_${mode}_to_${setting}`
}

function getConfig() {
    return config
}

module.exports = { setup, configure, getConfig }