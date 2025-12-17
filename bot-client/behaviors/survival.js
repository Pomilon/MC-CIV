const { goals } = require('mineflayer-pathfinder')
const Vec3 = require('vec3')

function setup(bot) {
    // Auto Eat should be loaded in index.js
    
    // Config auto eat
    if (bot.autoEat) {
        bot.autoEat.options = {
            priority: 'foodPoints',
            startAt: 14,
            bannedFood: []
        }
    } else {
        console.error("WARNING: bot.autoEat is undefined. Plugin might not be loaded in index.js")
    }
    
    // Auto Sleep logic
    bot.on('time', async () => {
        if (bot.time.isDay) return
        // Optional auto-sleep logic could remain, but we want manual control too.
    })
    
    bot.on('wake', () => {
        // bot.chat("Good morning!") // Optional
    })
}

async function manageInventory(bot, task) {
    if (task === 'equip_best') {
        return "EquippedBest"
    } else if (task === 'sort') {
        return "InventorySorted"
    } else if (task === 'discard_junk') {
        const junk = ['dirt', 'cobblestone', 'gravel', 'andesite', 'diorite', 'granite']
        let tossed = 0
        for (const item of bot.inventory.items()) {
            if (junk.includes(item.name)) {
                try {
                    await bot.toss(item.type, null, item.count)
                    tossed += item.count
                } catch (err) {
                    console.log("Error tossing", err)
                }
            }
        }
        return `Discarded_${tossed}_Items`
    }
    throw new Error(`Unknown inventory task: ${task}`)
}

async function breakBlock(bot, blockName, position) {
    let block
    
    if (position) {
        // Mode 1: Coordinates
        const vec = new Vec3(position.x, position.y, position.z)
        block = bot.blockAt(vec)
        
        if (!block || block.name === 'air') throw new Error("TargetIsAir")
        if (block.name === 'bedrock') throw new Error("CannotBreakBedrock")
        
        // Optional: If blockName is also provided, verify it matches
        if (blockName && block.name !== blockName) {
            console.log(`Warning: Target block is ${block.name}, expected ${blockName}. Breaking anyway.`)
        }
    } else {
        // Mode 2: Search
        if (!blockName) throw new Error("BlockNameRequiredForSearch")
        const blockIds = bot.registry.blocksByName[blockName].id
        block = bot.findBlock({ matching: blockIds, maxDistance: 32 })
        if (!block) throw new Error("BlockNotFound")
    }
    
    await bot.collectBlock.collect(block)
    return "BlockBroken"
}

async function gatherResource(bot, resourceName, count = 1) {
    const blockType = bot.registry.blocksByName[resourceName]
    if (!blockType) throw new Error(`Unknown block type: ${resourceName}`)

    let collected = 0
    let attempts = 0
    let consecutiveFailures = 0
    const MAX_ATTEMPTS = count + 5 // Tighter limit

    while (collected < count && attempts < MAX_ATTEMPTS) {
        attempts++
        
        const block = bot.findBlock({ 
            matching: blockType.id, 
            maxDistance: 64 
        })
        
        if (!block) {
            if (collected > 0) return `PartialGather_${collected}_of_${count}_NoMoreFound`
            throw new Error("ResourceNotFound")
        }

        try {
            // Add timeout to specific collect action
            await Promise.race([
                bot.collectBlock.collect(block),
                new Promise((_, r) => setTimeout(() => r(new Error("Collect Timeout")), 20000))
            ])
            
            collected++ 
            consecutiveFailures = 0
        } catch (err) {
            console.log(`Gather error (${attempts}):`, err.message)
            consecutiveFailures++
            if (consecutiveFailures >= 3) {
                 return `GatherFailed_TooManyErrors_Collected_${collected}`
            }
        }
    }
    
    if (collected < count) return `PartialGather_${collected}_of_${count}`
    return `Gathered_${collected}_${resourceName}`
}

async function findAndCollect(bot, itemName, count = 1) {
    // Collect dropped items
    let collected = 0
    let attempts = 0
    
    while (collected < count && attempts < 20) {
        attempts++
        
        const entity = bot.nearestEntity(e => 
            e.name === 'item' && 
            e.metadata && 
             e.getDroppedItem && e.getDroppedItem().name === itemName
        )
        
        // Better approach:
        const itemEntity = Object.values(bot.entities).find(e => 
            e.name === 'item' && 
            (e.getDroppedItem()?.name === itemName)
        )

        if (!itemEntity) {
             if (collected > 0) return `PartialCollect_${collected}`
             throw new Error("ItemNotFound")
        }

        const p = itemEntity.position
        await bot.pathfinder.goto(new goals.GoalNear(p.x, p.y, p.z, 1))
        
        // Wait a bit for pickup
        await new Promise(r => setTimeout(r, 500))
        
        // Check if entity is gone (validating pickup)
        if (!bot.entities[itemEntity.id]) {
            collected++
        }
    }
    
    return `Collected_${collected}_${itemName}`
}

async function throwItem(bot, itemName, count = 1) {
    const item = bot.inventory.items().find(i => i.name === itemName)
    if (!item) throw new Error("ItemNotInInventory")
    
    await bot.toss(item.type, null, count)
    return "ItemThrown"
}

async function useItem(bot, itemName) {
    const item = bot.inventory.items().find(i => i.name === itemName)
    if (!item) throw new Error("ItemNotInInventory")
    
    await bot.equip(item, 'hand')
    await bot.consume()
    return "ItemUsed"
}

async function mountEntity(bot, targetName) {
    const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName || e.name === targetName))
    if (!entity) throw new Error("EntityNotFound")
    
    bot.mount(entity)
    return "Mounted"
}

async function dismountEntity(bot) {
    bot.dismount()
    return "Dismounted"
}

async function sleep(bot) {
    const bed = bot.findBlock({ matching: blk => bot.isABed(blk), maxDistance: 32 })
    if (!bed) throw new Error("NoBedNearby")
    
    try {
        await bot.sleep(bed)
        return "Sleeping"
    } catch (err) {
        throw new Error(`SleepFailed: ${err.message}`)
    }
}

async function wake(bot) {
    try {
        await bot.wake()
        return "WokeUp"
    } catch (err) {
        throw new Error(`WakeFailed: ${err.message}`)
    }
}

module.exports = { 
    setup, 
    manageInventory, 
    breakBlock, 
    gatherResource,
    findAndCollect,
    throwItem, 
    useItem, 
    mountEntity, 
    dismountEntity, 
    sleep, 
    wake 
}