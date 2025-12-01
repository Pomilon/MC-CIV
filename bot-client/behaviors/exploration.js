const { goals } = require('mineflayer-pathfinder')

let explorationMode = 'stop' // 'wander', 'follow', 'stop'
let targetEntity = null

function setup(bot) {
    // Loop for continuous exploration behavior
    bot.on('physicsTick', () => {
        if (bot.pathfinder.isMoving()) return
        
        if (explorationMode === 'wander') {
            // Pick a random spot nearby
            const p = bot.entity.position
            const x = p.x + (Math.random() - 0.5) * 20
            const z = p.z + (Math.random() - 0.5) * 20
            const y = p.y // Simplify height
            
            bot.pathfinder.setGoal(new goals.GoalNear(x, y, z, 1))
        } else if (explorationMode === 'follow' && targetEntity) {
            // Update goal if target moved significantly or we stopped
            if (!bot.pathfinder.isMoving()) {
                 bot.pathfinder.setGoal(new goals.GoalFollow(targetEntity, 3), true)
            }
        }
    })
}

function setExplorationMode(bot, mode, targetName) {
    explorationMode = mode
    
    if (mode === 'follow') {
        const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName))
        if (entity) {
            targetEntity = entity
            return { status: 'success', message: `Following ${targetName}` }
        } else {
            explorationMode = 'stop'
            return { status: 'failed', reason: 'Target not found' }
        }
    } else if (mode === 'wander') {
        return { status: 'success', message: 'Exploration mode: Wander' }
    } else {
        bot.pathfinder.setGoal(null)
        return { status: 'success', message: 'Exploration stopped' }
    }
}

module.exports = { setup, setExplorationMode }
