from telegram import Bot
import os
import asyncio

bot = Bot(token=os.getenv("BOT_TOKEN"))

async def test():
    chat_id = int(os.getenv("CHAT_ID"))
    print("CHAT_ID:", chat_id)

    await bot.send_message(chat_id=chat_id, text="🚀 TEST SUCCESS")

asyncio.run(test())