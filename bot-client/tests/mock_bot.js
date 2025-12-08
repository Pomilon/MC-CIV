// bot-client/tests/mock_bot.js
const EventEmitter = require('events')

class MockBot extends EventEmitter {
    constructor() {
        super()
        this.username = "MockBot"
        this.entity = { position: { x: 100, y: 64, z: 100 } }
        this.inventory = {
            items: () => [
                { name: 'dirt', count: 64, type: 1 },
                { name: 'torch', count: 10, type: 2 }
            ]
        }
        this.registry = {
            blocksByName: {
                'dirt': { id: 1 },
                'stone': { id: 2 },
                'air': { id: 0 },
                'crafting_table': { id: 50 }
            },
            itemsByName: {
                'dirt': { id: 1 }
            }
        }
        
        // Mock Plugins
        this.pathfinder = {
            setGoal: (g) => { this.currentGoal = g; this.emit('goal_reached') },
            goto: async (g) => { this.currentGoal = g; return Promise.resolve() },
            stop: () => {}
        }
        this.collectBlock = {
            collect: async (b) => { this.collected = b; return Promise.resolve() }
        }
        this.pvp = {
            attack: (e) => {},
            stop: () => {}
        }
        
        // Mock World
        this.world = {
            getBlock: (pos) => this.blockAt(pos)
        }
        this.blockAt = (pos) => {
            // Simple mock: ground is dirt, air above
            if (pos.y < 64) return { name: 'stone', position: pos, boundingBox: 'block', shapes: [[0,0,0,1,1,1]] }
            if (pos.y === 64) return { name: 'dirt', position: pos, boundingBox: 'block', shapes: [[0,0,0,1,1,1]] }
            return { name: 'air', position: pos, boundingBox: 'empty', shapes: [] }
        }
        this.findBlock = ({ matching, maxDistance }) => {
            // Simply return a dummy block if matching isn't air
            return { name: 'dirt', position: { x: 105, y: 64, z: 105 } }
        }
        this.nearestEntity = () => null
        this.equip = async () => Promise.resolve()
        this.placeBlock = async (ref, face) => Promise.resolve()
        this.toss = async () => Promise.resolve()
        this.consume = async () => Promise.resolve()
        this.activateBlock = async () => Promise.resolve()
    }
}

module.exports = MockBot
