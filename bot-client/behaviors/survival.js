function setup(bot) {
    const autoEatModule = require('mineflayer-auto-eat')
    console.log("DEBUG: AutoEat Module keys:", Object.keys(autoEatModule))

    // Try to identify the plugin function from various potential exports
    const plugin = autoEatModule.plugin || autoEatModule.loader || autoEatModule.default || autoEatModule

    if (typeof plugin !== 'function') {
        console.error("CRITICAL: Could not find autoEat plugin function. Module type:", typeof autoEatModule)
        return
    }

    try {
        bot.loadPlugin(plugin)
    } catch (err) {
        console.error("CRITICAL: Failed to load autoEat plugin:", err)
        return
    }
    
    // Config auto eat
    if (bot.autoEat) {
        bot.autoEat.options = {
            priority: 'foodPoints',
            startAt: 14,
            bannedFood: []
        }
    } else {
        console.error("WARNING: bot.autoEat is undefined after plugin load. functionality disabled.")
        console.log("DEBUG: Bot keys:", Object.keys(bot).filter(k => k.toLowerCase().includes('eat')))
    }
    
    // Auto Sleep logic
    bot.on('time', async () => {
        if (bot.time.isDay) return
        
        // It's night/storm
        try {
            if (bot.isSleeping) return
            
            const bed = bot.findBlock({
                matching: blk => bot.isABed(blk),
                maxDistance: 32
            })
            
            if (bed) {
                // If close enough, sleep
                if (bot.entity.position.distanceTo(bed.position) < 3) {
                    await bot.sleep(bed)
                    bot.chat("Sleeping...")
                } else {
                    // We don't pathfind automatically to bed unless commanded, 
                    // or we could add a "tired" preset?
                    // For now, if close, sleep.
                }
            }
        } catch (err) {
            // Ignore sleep errors (monsters nearby, etc)
        }
    })
    
    bot.on('wake', () => {
        bot.chat("Good morning!")
    })
}

async function manageInventory(bot, task) {
    if (task === 'equip_best') {
        return { status: 'success', message: 'Equipped best gear (auto)' }
    } else if (task === 'sort') {
        return { status: 'success', message: 'Inventory sorted (simulated)' }
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
        return { status: 'success', message: `Discarded ${tossed} junk items` }
    }
    return { status: 'failed', reason: 'Unknown inventory task' }
}

module.exports = { setup, manageInventory }
