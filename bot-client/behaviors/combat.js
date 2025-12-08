const { goals } = require('mineflayer-pathfinder')

function setup(bot) {
    bot.loadPlugin(require('mineflayer-pvp').plugin)
    bot.loadPlugin(require('mineflayer-armor-manager'))
}

async function engageTarget(bot, targetName) {
    return new Promise((resolve, reject) => {
        const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName))
        if (!entity) {
            return reject("TargetNotFound")
        }

        console.log(`Engaging ${targetName}...`)
        bot.pvp.attack(entity)

        // Safety check loop
        const checkInterval = setInterval(() => {
            if (bot.health < 5) {
                bot.pvp.stop()
                cleanup()
                resolve("LowHealthRetreat")
            }
            if (bot.entity.position.distanceTo(entity.position) > 20) {
                 // Too far, maybe gave up?
            }
        }, 500)

        const cleanup = () => {
            clearInterval(checkInterval)
            bot.removeListener('stoppedAttacking', onStopped)
            bot.removeListener('entityGone', onEntityGone)
        }

        const onStopped = () => {
            // Mineflayer-pvp emits this when target is dead or unreachable
            // But sometimes it emits it when just cooling down? 
            // Actually mineflayer-pvp 'stoppedAttacking' usually means finish.
            // Let's verify if target is valid.
            if (!entity.isValid) {
                 cleanup()
                 resolve("TargetKilled")
            } else {
                // If stopped but entity valid, maybe lost path?
                cleanup()
                resolve("AttackStopped")
            }
        }

        const onEntityGone = (e) => {
            if (e === entity) {
                cleanup()
                resolve("TargetKilled")
            }
        }

        bot.on('stoppedAttacking', onStopped)
        bot.on('entityGone', onEntityGone)
    })
}

module.exports = { setup, engageTarget }
