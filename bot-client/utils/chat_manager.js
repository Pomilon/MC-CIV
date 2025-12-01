// Cooldowns for chat to prevent spam
const chatCooldowns = new Map()
const GLOBAL_CHAT_COOLDOWN = 2000 // 2 seconds

function canChat(bot) {
    const lastChat = chatCooldowns.get(bot.username) || 0
    return Date.now() - lastChat > GLOBAL_CHAT_COOLDOWN
}

function recordChat(bot) {
    chatCooldowns.set(bot.username, Date.now())
}

module.exports = { canChat, recordChat }
