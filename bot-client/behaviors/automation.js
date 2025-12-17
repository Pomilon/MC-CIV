const { goals } = require('mineflayer-pathfinder')
const Vec3 = require('vec3')

function setup(bot) {
    // No specific plugins needed beyond pathfinder/collectBlock, which are global
}

async function smeltItem(bot, itemName, fuelName, count = 1) {
    // 1. Check Inventory
    const item = bot.inventory.items().find(i => i.name === itemName)
    const fuel = bot.inventory.items().find(i => i.name === fuelName)
    
    if (!item) throw new Error(`Missing item to smelt: ${itemName}`)
    if (!fuel) throw new Error(`Missing fuel: ${fuelName}`)
    
    // 2. Find Furnace
    const furnaceBlock = bot.findBlock({ matching: bot.registry.blocksByName['furnace'].id, maxDistance: 32 })
    if (!furnaceBlock) throw new Error("No furnace nearby")
    
    // 3. Go to Furnace
    await bot.pathfinder.goto(new goals.GoalNear(furnaceBlock.position.x, furnaceBlock.position.y, furnaceBlock.position.z, 1))
    
    // 4. Open & Smelt
    const furnace = await bot.openFurnace(furnaceBlock)
    
    try {
        await furnace.putFuel(fuel.type, null, 1) // Put 1 fuel for now, loop if needed?
        await furnace.putInput(item.type, null, count)
        
        // Wait for output
        // Simple wait loop checking output slot
        let smelted = 0
        const timeout = Date.now() + (count * 10000) + 5000 // 10s per item approx?
        
        while (Date.now() < timeout && smelted < count) {
            await new Promise(r => setTimeout(r, 1000))
            if (furnace.outputItem && furnace.outputItem.count >= count) {
                break
            }
            // If input empty and output has something, take it?
            if (!furnace.inputItem && furnace.outputItem) break 
        }
        
        await furnace.takeOutput()
        return `Smelted_${count}_${itemName}`
        
    } catch (err) {
        throw new Error(`Smelt failed: ${err.message}`)
    } finally {
        furnace.close()
    }
}

async function depositToChest(bot, itemName, count = null) {
    // 1. Find Chest
    const chestBlock = bot.findBlock({ 
        matching: [bot.registry.blocksByName['chest'].id, bot.registry.blocksByName['trapped_chest'].id], 
        maxDistance: 32 
    })
    if (!chestBlock) throw new Error("No chest nearby")

    // 2. Go to Chest
    await bot.pathfinder.goto(new goals.GoalNear(chestBlock.position.x, chestBlock.position.y, chestBlock.position.z, 1))
    
    // 3. Open & Deposit
    const chest = await bot.openChest(chestBlock)
    try {
        if (itemName === 'all') {
            const items = bot.inventory.items()
            for (const item of items) {
                try {
                    await chest.deposit(item.type, null, item.count)
                } catch (e) { console.log("Deposit partial error:", e.message) }
            }
            return "Deposited_All"
        } else {
             const item = bot.inventory.items().find(i => i.name === itemName)
             if (!item) throw new Error("Item not in inventory")
             
             const qty = count || item.count
             await chest.deposit(item.type, null, qty)
             return `Deposited_${qty}_${itemName}`
        }
    } finally {
        chest.close()
    }
}

async function farmLoop(bot, mode, cropName, limit = 10) {
    // Determine crop block IDs
    let seedName = cropName // Default guess (e.g. wheat seeds?)
    if (cropName === 'wheat') seedName = 'wheat_seeds'
    if (cropName === 'carrots') seedName = 'carrot'
    if (cropName === 'potatoes') seedName = 'potato'
    if (cropName === 'beetroots') seedName = 'beetroot_seeds'
    
    const cropBlockName = (cropName === 'wheat_seeds' || cropName === 'seeds') ? 'wheat' : cropName
    const cropId = bot.registry.blocksByName[cropBlockName]?.id
    
    if (!cropId) throw new Error(`Unknown crop: ${cropName}`)
    
    let processed = 0
    let attempts = 0
    
    while (processed < limit && attempts < limit * 2) {
        attempts++
        
        if (mode === 'harvest' || mode === 'cycle') {
            // Find mature crop
            // Metadata 7 is usually mature for wheat/carrots/potatoes in modern versions
            const block = bot.findBlock({
                matching: blk => blk.type === cropId && blk.metadata === 7,
                maxDistance: 20
            })
            
            if (block) {
                await bot.pathfinder.goto(new goals.GoalNear(block.position.x, block.position.y, block.position.z, 1))
                await bot.dig(block)
                processed++
                
                if (mode === 'cycle') {
                    // Replant
                    // Wait a moment for drop pickup
                    await new Promise(r => setTimeout(r, 500))
                    
                    const seeds = bot.inventory.items().find(i => i.name === seedName)
                    if (seeds) {
                        await bot.equip(seeds, 'hand')
                        const farmLand = bot.blockAt(block.position.offset(0, -1, 0))
                        if (farmLand) {
                             await bot.placeBlock(farmLand, new Vec3(0, 1, 0))
                        }
                    }
                }
            } else {
                if (mode === 'harvest') break // No more mature crops
            }
        }
        
        // Plant mode logic could go here (searching for empty farmland)
        // ...
    }
    
    return `Farmed_${processed}_blocks`
}

module.exports = { setup, smeltItem, depositToChest, farmLoop }
