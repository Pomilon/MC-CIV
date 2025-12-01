const { goals } = require('mineflayer-pathfinder')

let combatMode = 'none' // 'pvp', 'none'
let survivalPreset = 'neutral' // 'brave', 'cowardly', 'neutral'
let targetEntity = null

function setup(bot) {
    bot.loadPlugin(require('mineflayer-pvp').plugin)
    bot.loadPlugin(require('mineflayer-armor-manager'))
    
    // Auto defense loop
    bot.on('physicsTick', () => {
        if (combatMode === 'pvp' && targetEntity) {
            // PVP Plugin handles attack, we just ensure we are looking/moving
            if (!bot.pvp.target) {
                bot.pvp.attack(targetEntity)
            }
        }
        
        if (survivalPreset === 'cowardly') {
            const nearestHostile = bot.nearestEntity(e => e.type === 'hostile' && e.position.distanceTo(bot.entity.position) < 10)
            if (nearestHostile) {
                // Run away
                bot.pvp.stop() // Stop fighting if we were
                const inverseGoal = new goals.GoalInvert(new goals.GoalFollow(nearestHostile, 5))
                bot.pathfinder.setGoal(inverseGoal)
            }
        } else if (survivalPreset === 'brave') {
            // Auto attack hostiles if not already busy
            if (!bot.pvp.target && combatMode !== 'pvp') {
                const nearestHostile = bot.nearestEntity(e => e.type === 'hostile' && e.position.distanceTo(bot.entity.position) < 8)
                if (nearestHostile) {
                     bot.pvp.attack(nearestHostile)
                }
            }
        }
    })
    
    // Log PvP events
    bot.on('startedAttacking', () => console.log("Started attacking"))
    bot.on('stoppedAttacking', () => console.log("Stopped attacking"))
}

function setCombatMode(bot, mode, targetName) {
    combatMode = mode
    
    if (mode === 'pvp') {
        const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName))
        if (entity) {
            targetEntity = entity
            bot.pvp.attack(entity)
            return { status: 'success', message: `Attacking ${targetName}` }
        } else {
            return { status: 'failed', reason: 'Target not found' }
        }
    } else {
        bot.pvp.stop()
        targetEntity = null
        bot.pathfinder.setGoal(null)
        return { status: 'success', message: 'Combat stopped' }
    }
}

function setSurvivalPreset(bot, preset) {
    if (['brave', 'cowardly', 'neutral'].includes(preset)) {
        survivalPreset = preset
        return { status: 'success', message: `Survival preset set to ${preset}` }
    }
    return { status: 'failed', reason: 'Invalid preset' }
}

module.exports = { setup, setCombatMode, setSurvivalPreset }
