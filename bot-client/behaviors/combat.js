const { goals } = require('mineflayer-pathfinder')

function setup(bot) {
    bot.loadPlugin(require('mineflayer-pvp').plugin)
    bot.loadPlugin(require('mineflayer-armor-manager'))
}

async function engageTarget(bot, targetName) {
    return new Promise((resolve, reject) => {
        const entity = bot.nearestEntity(e => (e.username === targetName || e.mobType === targetName || e.name === targetName))
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
        }, 500)

        const cleanup = () => {
            clearInterval(checkInterval)
            bot.removeListener('stoppedAttacking', onStopped)
            bot.removeListener('entityGone', onEntityGone)
        }

        const onStopped = () => {
            if (!entity.isValid) {
                 cleanup()
                 resolve("TargetKilled")
            } else {
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

async function huntCreature(bot, creatureName, count = 1) {
    let defeated = 0
    let attempts = 0
    
    while (defeated < count && attempts < count * 3) {
        attempts++
        try {
            const result = await engageTarget(bot, creatureName)
            if (result === "TargetKilled") {
                defeated++
            } else if (result === "LowHealthRetreat") {
                return `HuntPaused_LowHealth_${defeated}`
            }
        } catch (err) {
            if (err === "TargetNotFound") {
                // For now, fail if not found immediately to avoid infinite wandering.
                if (defeated > 0) return `PartialHunt_${defeated}_NoMoreFound`
                throw new Error("TargetNotFound")
            }
            console.log("Hunt error:", err)
        }
        
        // Small pause between targets
        await new Promise(r => setTimeout(r, 1000))
    }
    
    return `Hunted_${defeated}_${creatureName}`
}

module.exports = { setup, engageTarget, huntCreature }