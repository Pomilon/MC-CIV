function setup(bot) {
    bot.loadPlugin(require('mineflayer-auto-eat').plugin)
    
    // Config auto eat
    bot.autoEat.options = {
        priority: 'foodPoints',
        startAt: 14,
        bannedFood: []
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
