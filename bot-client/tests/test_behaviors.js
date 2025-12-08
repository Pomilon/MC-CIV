// bot-client/tests/test_behaviors.js
const assert = require('assert')
const MockBot = require('./mock_bot')
const survivalBehavior = require('../behaviors/survival')
const buildingBehavior = require('../behaviors/building')
const explorationBehavior = require('../behaviors/exploration')

async function runTests() {
    console.log("Running Node.js Behavior Tests...")
    const bot = new MockBot()

    // --- Survival Tests ---
    console.log("Testing Survival: Break Block...")
    try {
        const res = await survivalBehavior.breakBlock(bot, 'dirt', null)
        assert.strictEqual(res, "BlockBroken")
    } catch (e) {
        console.error("Break Block Failed:", e)
        process.exit(1)
    }

    console.log("Testing Survival: Throw Item...")
    try {
        const res = await survivalBehavior.throwItem(bot, 'dirt', 1)
        assert.strictEqual(res, "ItemThrown")
    } catch (e) {
        console.error("Throw Item Failed:", e)
        process.exit(1)
    }

    // --- Building Tests ---
    console.log("Testing Building: Inspect Zone...")
    try {
        const c1 = { x: 100, y: 64, z: 100 }
        const c2 = { x: 101, y: 65, z: 101 } // 2x2x2 = 8 blocks
        
        const data = await buildingBehavior.inspectZone(bot, c1, c2)
        
        assert.strictEqual(data.size.x, 2)
        assert.strictEqual(data.size.y, 2)
        assert.strictEqual(data.layers.length, 2) // Y layers
        assert.strictEqual(data.layers[0][0][0], 'dirt') // 100, 64, 100
        assert.strictEqual(data.layers[1][0][0], 'air')  // 100, 65, 100
        
        console.log("Inspect Zone Passed.")
    } catch (e) {
        console.error("Inspect Zone Failed:", e)
        process.exit(1)
    }

    console.log("Testing Building: Place Block (Coords)...")
    try {
        const res = await buildingBehavior.placeBlock(bot, 'dirt', {x:100, y:65, z:100}, null)
        assert.strictEqual(res, "BlockPlaced")
    } catch (e) {
        console.error("Place Block Failed:", e)
        process.exit(1)
    }

    console.log("All Node.js Tests Passed!")
}

runTests()
