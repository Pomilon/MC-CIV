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

async function buildStructure(bot, shape, material, dimensions, location) {
    // 1. Parse Dimensions
    const dims = dimensions.match(/(\d+)\s+(\d+)\s+(\d+)/)
    if (!dims) throw new Error("Invalid dimensions format. Use 'W H D'")
    const width = parseInt(dims[1]) 
    const height = parseInt(dims[2])
    const depth = parseInt(dims[3])

    // 2. Determine Start Position (Corner)
    let startPos
    if (location) {
        const coords = location.match(/(-?\d+)\s+(-?\d+)\s+(-?\d+)/)
        if (coords) {
            startPos = new Vec3(parseInt(coords[1]), parseInt(coords[2]), parseInt(coords[3]))
        }
    }
    // Default: 2 blocks in front of bot to prevent self-entrapment
    if (!startPos) {
        const viewDir = bot.entity.yaw 
        // Simple 4-way direction
        const dir = Math.round(viewDir / (Math.PI / 2)) & 3
        const offsets = [
            new Vec3(0, 0, 1),  // South
            new Vec3(-1, 0, 0), // West
            new Vec3(0, 0, -1), // North
            new Vec3(1, 0, 0)   // East
        ]
        // Offset by 2 blocks + align to grid
        startPos = bot.entity.position.floor().plus(offsets[dir].scaled(2))
    }

    // 3. Verify Material
    const blockItem = bot.inventory.items().find(i => i.name === material)
    if (!blockItem) throw new Error(`Material ${material} not in inventory`)

    // 4. Generate Blueprint
    const blueprint = []
    
    if (shape === 'box') {
        for(let x=0; x<width; x++)
            for(let y=0; y<height; y++)
                for(let z=0; z<depth; z++)
                    blueprint.push(new Vec3(x, y, z))
    } else if (shape === 'hollow_box') {
        for(let x=0; x<width; x++)
            for(let y=0; y<height; y++)
                for(let z=0; z<depth; z++) {
                    if (x===0 || x===width-1 || y===0 || y===height-1 || z===0 || z===depth-1)
                        blueprint.push(new Vec3(x, y, z))
                }
    } else if (shape === 'floor') {
        for(let x=0; x<width; x++)
            for(let z=0; z<depth; z++)
                blueprint.push(new Vec3(x, 0, z))
    } else if (shape === 'wall') {
        if (depth > width) {
             for(let z=0; z<depth; z++)
                for(let y=0; y<height; y++)
                    blueprint.push(new Vec3(0, y, z))
        } else {
             for(let x=0; x<width; x++)
                for(let y=0; y<height; y++)
                    blueprint.push(new Vec3(x, y, 0))
        }
    } else if (shape === 'tower') {
         for(let y=0; y<height; y++) {
             for(let x=0; x<width; x++) {
                 blueprint.push(new Vec3(x, y, 0))
                 blueprint.push(new Vec3(x, y, depth-1))
             }
             for(let z=1; z<depth-1; z++) {
                 blueprint.push(new Vec3(0, y, z))
                 blueprint.push(new Vec3(width-1, y, z))
             }
         }
    } else if (shape === 'stairs') {
        for(let i=0; i<height; i++) {
            for(let x=0; x<width; x++) {
                blueprint.push(new Vec3(x, i, i))
            }
        }
    } else if (shape === 'pyramid') {
        let currentSize = width
        let y = 0
        while (currentSize > 0) {
            for (let x = 0; x < currentSize; x++) {
                for (let z = 0; z < currentSize; z++) {
                    blueprint.push(new Vec3(x + y, y, z + y))
                }
            }
            currentSize -= 2
            y++
        }
    } else {
        throw new Error(`Unknown shape: ${shape}`)
    }

    // 5. Execute Build
    let placed = 0
    let skipped = 0
    
    blueprint.sort((a, b) => a.y - b.y || a.z - b.z || a.x - b.x)

    for (const offset of blueprint) {
        const targetPos = startPos.plus(offset)
        const currentBlock = bot.blockAt(targetPos)
        
        // A. Handle Obstruction
        if (currentBlock && currentBlock.name !== 'air' && currentBlock.name !== 'water' && currentBlock.name !== 'lava') {
            if (currentBlock.name === material) {
                // Already placed
                skipped++
                continue
            }
            // Obstructed by something else -> Dig it
            if (currentBlock.diggable && currentBlock.name !== 'bedrock') {
                try {
                     if (bot.entity.position.distanceTo(targetPos) > 4.5) {
                        await bot.pathfinder.goto(new goals.GoalNear(targetPos.x, targetPos.y, targetPos.z, 3))
                     }
                     await bot.dig(currentBlock)
                } catch (e) {
                    console.log(`Failed to clear obstruction at ${targetPos}: ${e.message}`)
                    continue // Skip placement if can't clear
                }
            } else {
                continue // Can't dig (bedrock etc)
            }
        }

        // B. Handle Self-Obstruction (Bot Standing in block)
        const botBox = bot.entity.boundingBox
        const targetBox = new Vec3(1, 1, 1).offset(targetPos.x, targetPos.y, targetPos.z)
        // Simple distance check usually enough for "standing in"
        const dist = bot.entity.position.distanceTo(targetPos.offset(0.5, 0.5, 0.5))
        if (dist < 1.5) {
             // Move away
             try {
                 // Try to move 2 blocks away from target
                 // Or just move to startPos (if outside)
                 await bot.pathfinder.goto(new goals.GoalNear(startPos.x, startPos.y, startPos.z, 2))
             } catch(e) {}
        }

        // C. Check Materials
        const currentItem = bot.inventory.items().find(i => i.name === material)
        if (!currentItem) return `PartialBuild_${placed}_RanOutOfMaterials`
        
        // D. Equip
        if (bot.heldItem?.name !== material) {
            await bot.equip(currentItem, 'hand')
        }

        // E. Find Placement Reference
        let refBlock = null
        let faceVec = null
        
        const neighbors = [
            new Vec3(0, -1, 0), new Vec3(0, 1, 0),
            new Vec3(1, 0, 0), new Vec3(-1, 0, 0),
            new Vec3(0, 0, 1), new Vec3(0, 0, -1)
        ]

        for (const n of neighbors) {
            const nPos = targetPos.plus(n)
            const b = bot.blockAt(nPos)
            if (b && b.boundingBox === 'block') { // solid block
                refBlock = b
                faceVec = n.scaled(-1)
                break
            }
        }

        if (refBlock) {
            try {
                // Move close enough to REF block
                if (bot.entity.position.distanceTo(refBlock.position) > 4.5) {
                    await bot.pathfinder.goto(new goals.GoalPlaceBlock(targetPos, bot.world, { range: 4 }))
                }
                
                // Double check target is still clear (in case bot moved back in)
                const checkB = bot.blockAt(targetPos)
                if (checkB.name !== 'air' && checkB.name !== 'water') {
                     await bot.dig(checkB)
                }

                await bot.placeBlock(refBlock, faceVec)
                placed++
                await new Promise(r => setTimeout(r, 100))
            } catch (err) {
                console.log(`Build error at ${targetPos}: ${err.message}`)
            }
        } else {
            console.log(`No support for block at ${targetPos}`)
            skipped++
        }
    }
    
    return `Built_${shape}_${placed}_blocks`
}

async function clearArea(bot, corner1, corner2) {
    const c1 = new Vec3(corner1.x, corner1.y, corner1.z)
    const c2 = new Vec3(corner2.x, corner2.y, corner2.z)
    
    const minX = Math.min(c1.x, c2.x)
    const maxX = Math.max(c1.x, c2.x)
    const minY = Math.min(c1.y, c2.y)
    const maxY = Math.max(c1.y, c2.y)
    const minZ = Math.min(c1.z, c2.z)
    const maxZ = Math.max(c1.z, c2.z)
    
    // Safety Limit
    const volume = (maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1)
    if (volume > 1000) throw new Error("Area too large to clear (>1000 blocks)")

    let cleared = 0
    // Iterate top-down to prevent floating blocks?
    for (let y = maxY; y >= minY; y--) {
        for (let x = minX; x <= maxX; x++) {
            for (let z = minZ; z <= maxZ; z++) {
                const targetPos = new Vec3(x, y, z)
                const block = bot.blockAt(targetPos)
                
                if (block && block.name !== 'air' && block.name !== 'bedrock') {
                    // Move closer if needed
                    if (bot.entity.position.distanceTo(targetPos) > 4.5) {
                        await bot.pathfinder.goto(new goals.GoalNear(x, y, z, 3))
                    }
                    try {
                        await bot.dig(block)
                        cleared++
                    } catch (e) {
                         console.log("Clear dig error:", e.message)
                    }
                }
            }
        }
    }
    return `Cleared_${cleared}_blocks`
}

module.exports = { setup, buildStructure, placeBlock, inspectZone, clearArea }