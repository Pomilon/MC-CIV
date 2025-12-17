const { goals } = require('mineflayer-pathfinder')
const Vec3 = require('vec3')

// Runtime memory of visited chunks (reset on restart)
const visitedChunks = new Set()

function getChunkKey(pos) {
    const cx = Math.floor(pos.x / 16)
    const cz = Math.floor(pos.z / 16)
    return `${cx},${cz}`
}

function markVisited(bot) {
    const key = getChunkKey(bot.entity.position)
    visitedChunks.add(key)
}

function setup(bot) {
    bot.on('move', () => {
        markVisited(bot)
    })
}

async function wander(bot) {
    // Just keep random for "just move anywhere" fallback.
    return new Promise((resolve, reject) => {
        const p = bot.entity.position
        const x = p.x + (Math.random() - 0.5) * 40
        const z = p.z + (Math.random() - 0.5) * 40
        
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
                resolve("WanderPathFailed") 
            }
        }

        bot.on('goal_reached', onGoalReached)
        bot.on('path_update', onPathUpdate)
    })
}

async function exploreMap(bot, radius = 64) {
    const p = bot.entity.position
    const startCx = Math.floor(p.x / 16)
    const startCz = Math.floor(p.z / 16)
    const range = Math.ceil(radius / 16)
    
    // Spiral search for nearest unvisited chunk
    let targetChunk = null
    
    // Simple spiral
    let x = 0, z = 0, dx = 0, dz = -1
    const maxSteps = (range * 2 + 1) * (range * 2 + 1)
    
    for (let i = 0; i < maxSteps; i++) {
        const key = `${startCx + x},${startCz + z}`
        if (!visitedChunks.has(key)) {
            targetChunk = { x: startCx + x, z: startCz + z }
            break
        }
        
        if (x === z || (x < 0 && x === -z) || (x > 0 && x === 1 - z)) {
            const t = dx; dx = -dz; dz = t;
        }
        x += dx; z += dz;
    }
    
    if (!targetChunk) {
        return await wander(bot)
    }
    
    // Navigate to center of target chunk
    const tx = targetChunk.x * 16 + 8
    const tz = targetChunk.z * 16 + 8

    return new Promise((resolve, reject) => {
        // Use GoalXZ if possible, else guess Y (bot.entity.position.y)
        const goal = new goals.GoalNear(tx, p.y, tz, 2) // Basic GoalNear adapts Y usually
        
        bot.pathfinder.setGoal(goal)
        
        const cleanup = () => {
            bot.removeListener('goal_reached', onGoalReached)
            bot.removeListener('path_update', onPathUpdate)
            bot.removeListener('stuck', onStuck)
        }

        const onGoalReached = () => {
            cleanup()
            resolve(`Explored_Chunk_${targetChunk.x}_${targetChunk.z}`)
        }

        const onPathUpdate = (r) => {
            if (r.status === 'noPath') {
                // Mark as visited (or unreachable) so we don't try again immediately
                visitedChunks.add(`${targetChunk.x},${targetChunk.z}`)
                cleanup()
                resolve("ChunkUnreachable_TryNext")
            }
        }
        
        const onStuck = () => {
             visitedChunks.add(`${targetChunk.x},${targetChunk.z}`)
             cleanup()
             resolve("Stuck_TryNext")
        }

        bot.on('goal_reached', onGoalReached)
        bot.on('path_update', onPathUpdate)
        bot.on('stuck', onStuck)
    })
}

async function findBiome(bot, biomeName, timeoutSecs = 60) {
    
    const startTime = Date.now()
    const endTime = startTime + timeoutSecs * 1000
    
    while (Date.now() < endTime) {
        const p = bot.entity.position
        const block = bot.blockAt(p)
        
        if (block && block.biome && block.biome.name) {
             if (block.biome.name.toLowerCase().includes(biomeName.toLowerCase())) {
                 return `FoundBiome_${block.biome.name}`
             }
        }
        
        // Explore map logic to cover ground
        await exploreMap(bot, 32)
        // exploreMap returns when it reaches a chunk. We check biome then.
    }
    
    return "BiomeNotFound_TimeOut"
}

async function follow(bot, targetName) {
    return new Promise((resolve, reject) => {
        const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName || e.name === targetName))
        if (!entity) return reject("TargetNotFound")
        
        const goal = new goals.GoalFollow(entity, 3)
        bot.pathfinder.setGoal(goal, true) 

        const cleanup = () => {
             bot.removeListener('goal_reached', onGoalReached)
        }

        const onGoalReached = () => {
            cleanup()
            resolve("ReachedTarget")
        }
        
        bot.on('goal_reached', onGoalReached)
    })
}

module.exports = { setup, wander, follow, exploreMap, findBiome }