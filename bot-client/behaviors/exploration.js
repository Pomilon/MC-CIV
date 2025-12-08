const { goals } = require('mineflayer-pathfinder')

function setup(bot) {
    // No explicit setup needed for discrete actions
}

async function wander(bot) {
    return new Promise((resolve, reject) => {
        const p = bot.entity.position
        const x = p.x + (Math.random() - 0.5) * 30
        const z = p.z + (Math.random() - 0.5) * 30
        
        // We use GoalNear to get close to the random spot
        const goal = new goals.GoalNear(x, p.y, z, 2)
        
        bot.pathfinder.setGoal(goal)
        
        const cleanup = () => {
            bot.removeListener('goal_reached', onGoalReached)
            bot.removeListener('path_update', onPathUpdate)
        }

        const onGoalReached = () => {
            cleanup()
            resolve("WanderStepComplete")
        }

        const onPathUpdate = (r) => {
            if (r.status === 'noPath') {
                cleanup()
                // It's okay if we can't path to a random spot, just say we tried
                resolve("WanderPathFailed") 
            }
        }

        bot.on('goal_reached', onGoalReached)
        bot.on('path_update', onPathUpdate)
    })
}

async function follow(bot, targetName) {
    return new Promise((resolve, reject) => {
        const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName))
        if (!entity) return reject("TargetNotFound")
        
        // Move to within 3 blocks
        const goal = new goals.GoalFollow(entity, 3)
        bot.pathfinder.setGoal(goal, true) // dynamic = true

        const cleanup = () => {
             bot.removeListener('goal_reached', onGoalReached)
             // We generally don't get 'goal_reached' for dynamic follow unless we stop?
             // Actually mineflayer-pathfinder emits goal_reached when within range.
        }

        const onGoalReached = () => {
            cleanup()
            resolve("ReachedTarget")
        }
        
        bot.on('goal_reached', onGoalReached)
        
        // Timeout? If target keeps moving, we never resolve?
        // For discrete actions, maybe we shouldn't use dynamic follow.
        // We should use GoalNear(entity.pos).
    })
}

module.exports = { setup, wander, follow }
