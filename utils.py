from bot import bot


async def get_chat_admins(chat_id):
    return await bot.get_chat_administrators(chat_id)
