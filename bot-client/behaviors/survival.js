const { goals } = require('mineflayer-pathfinder')

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

module.exports = { setup, manageInventory, breakBlock, throwItem, useItem, mountEntity, dismountEntity, sleep, wake }
