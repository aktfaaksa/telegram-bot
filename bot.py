import asyncio
import os
from telegram import Bot

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)

# 👇 نفس الأشخاص
CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880
]

# ====== اختبار ======
async def main():
    msg = "✅ البوت شغال 100% 🚀"

    for c in CHAT_IDS:
        try:
            await bot.send_message(chat_id=c, text=msg)
            print(f"Sent to {c}")
        except Exception as e:
            print(f"Error sending to {c}:", e)

if __name__ == "__main__":
    asyncio.run(main())