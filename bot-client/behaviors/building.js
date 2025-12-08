const { goals } = require('mineflayer-pathfinder')
const Vec3 = require('vec3')

function setup(bot) {
    // No specific plugin for generic building, using raw placement logic
}

async function placeBlock(bot, blockName, position, referenceBlockName) {
    let targetPos = null
    let referenceBlock = null
    let faceVector = null

    // Check inventory
    const item = bot.inventory.items().find(i => i.name === blockName)
    if (!item) throw new Error(`Missing item: ${blockName}`)
    
    // Mode 1: Coordinates
    if (position) {
        targetPos = new Vec3(position.x, position.y, position.z)
        
        // Find reference block (simple logic: look for neighbor)
        const neighbors = [
            new Vec3(0, -1, 0), new Vec3(0, 1, 0),
            new Vec3(1, 0, 0), new Vec3(-1, 0, 0),
            new Vec3(0, 0, 1), new Vec3(0, 0, -1)
        ]
        
        for (const off of neighbors) {
            const checkPos = targetPos.plus(off)
            const block = bot.blockAt(checkPos)
            if (block && block.name !== 'air' && block.boundingBox === 'block') {
                 referenceBlock = block
                 faceVector = off.scaled(-1) // vector from ref to target
                 break
            }
        }
        if (!referenceBlock) throw new Error("No support block to place on")
        
    } 
    // Mode 2: Search Reference
    else if (referenceBlockName) {
         const refIds = bot.registry.blocksByName[referenceBlockName]?.id
         if (!refIds) throw new Error(`Unknown reference block: ${referenceBlockName}`)
         
         referenceBlock = bot.findBlock({ matching: refIds, maxDistance: 10 })
         if (!referenceBlock) throw new Error(`Reference block '${referenceBlockName}' not found nearby`)
         
         // Find a free face on this block
         const faces = [
            new Vec3(0, 1, 0), new Vec3(0, -1, 0),
            new Vec3(1, 0, 0), new Vec3(-1, 0, 0),
            new Vec3(0, 0, 1), new Vec3(0, 0, -1)
         ]
         
         for (const face of faces) {
             const checkPos = referenceBlock.position.plus(face)
             const blk = bot.blockAt(checkPos)
             if (blk && blk.name === 'air') {
                 faceVector = face
                 targetPos = checkPos // Not strictly needed for placeBlock call but good for debug
                 break
             }
         }
         
         if (!faceVector) throw new Error("No free space on reference block")
         
    } else {
        throw new Error("Must provide position or near_block")
    }

    await bot.equip(item, 'hand')
    
    // Go near
    try {
        // We go to the placement target (if calculated) or the reference block
        const goalPos = targetPos || referenceBlock.position
        await bot.pathfinder.goto(new goals.GoalPlaceBlock(goalPos, bot.world, { range: 4 }))
        
        // Place
        await bot.placeBlock(referenceBlock, faceVector)
        return "BlockPlaced"
    } catch (err) {
        throw new Error(`Placement failed: ${err.message}`)
    }
}

async function inspectZone(bot, corner1, corner2) {
    const c1 = new Vec3(corner1.x, corner1.y, corner1.z)
    const c2 = new Vec3(corner2.x, corner2.y, corner2.z)
    
    const minX = Math.min(c1.x, c2.x)
    const maxX = Math.max(c1.x, c2.x)
    const minY = Math.min(c1.y, c2.y)
    const maxY = Math.max(c1.y, c2.y)
    const minZ = Math.min(c1.z, c2.z)
    const maxZ = Math.max(c1.z, c2.z)
    
    const sizeX = maxX - minX + 1
    const sizeY = maxY - minY + 1
    const sizeZ = maxZ - minZ + 1
    
    const volume = sizeX * sizeY * sizeZ
    const MAX_VOLUME = 512
    
    if (volume > MAX_VOLUME) {
        throw new Error(`Zone too large (${volume} blocks). Max limit is ${MAX_VOLUME} (e.g. 8x8x8).`)
    }
    
    // Structure: layers[y][z][x]
    const layers = []
    
    for (let y = 0; y < sizeY; y++) {
        const layer = []
        for (let z = 0; z < sizeZ; z++) {
            const row = []
            for (let x = 0; x < sizeX; x++) {
                const pos = new Vec3(minX + x, minY + y, minZ + z)
                const b = bot.blockAt(pos)
                row.push(b ? b.name : 'unknown')
            }
            layer.push(row)
        }
        layers.push(layer)
    }
    
    return {
        origin: { x: minX, y: minY, z: minZ },
        size: { x: sizeX, y: sizeY, z: sizeZ },
        layers: layers
    }
}

async function buildStructure(bot, type, position) {
    const startPos = new Vec3(position.x, position.y, position.z)
    
    // Generic material check
    const materials = bot.inventory.items().filter(i => bot.registry.blocksByName[i.name])
    if (materials.length === 0) throw new Error('No blocks in inventory')
    
    // Helper to place at relative offset
    const placeAt = async (relX, relY, relZ) => {
        const target = startPos.offset(relX, relY, relZ)
        // Simple logic: assume we can place. Real logic needs placeBlock's robustness.
        // We will reuse placeBlock if possible, but we need to know WHICH block to use.
        // For now, use the first available material.
        const mat = bot.inventory.items().find(i => bot.registry.blocksByName[i.name])
        if (!mat) throw new Error("Ran out of blocks")
        
        // We call placeBlock internal logic or similar.
        // To be safe, let's just use placeBlock but we need to pass name.
        try {
            await placeBlock(bot, mat.name, target)
        } catch (e) {
            // Ignore "No support block" if we are just trying to fill air, 
            // but for a structure we should build in order.
            console.log(`Build skip at ${relX},${relY},${relZ}: ${e.message}`)
        }
    }
    
    try {
        if (type === 'wall') {
            for (let i = 0; i < 3; i++) await placeAt(0, i, 0)
            return "WallBuilt"
        } else if (type === 'floor') {
            for (let x = 0; x < 3; x++) 
                for (let z = 0; z < 3; z++) await placeAt(x, 0, z)
            return "FloorBuilt"
        } else if (type === 'tower') {
             for (let i = 0; i < 5; i++) await placeAt(0, i, 0)
             return "TowerBuilt"
        } else if (type === 'shelter') {
            // 3x3x3 hollow box
            // Floor
            for(let x=0; x<3; x++) for(let z=0; z<3; z++) await placeAt(x, 0, z)
            // Walls
            for(let y=1; y<3; y++) {
                for(let x=0; x<3; x++) {
                    await placeAt(x, y, 0)
                    await placeAt(x, y, 2)
                }
                 await placeAt(0, y, 1)
                 await placeAt(2, y, 1)
            }
            // Roof
            for(let x=0; x<3; x++) for(let z=0; z<3; z++) await placeAt(x, 3, z)
            return "ShelterBuilt"
        }
        
        throw new Error(`Unknown structure type: ${type}`)
    } catch (err) {
        throw err 
    }
}

module.exports = { setup, buildStructure, placeBlock, inspectZone }
