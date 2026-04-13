import asyncio
import aiohttp
import os
from telegram import Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from openai import OpenAI

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_KEY = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=TOKEN)

# ===== AI =====
client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1"
)

async def ai_analyze(text):
    try:
        res = client.chat.completions.create(
            model="qwen/qwen3-next-80b-a3b-instruct:free",
            messages=[{"role": "user", "content": f"""
Decision: BUY or SELL or HOLD
Confidence: 0-100

{text}
"""}]
        )
        return res.choices[0].message.content
    except:
        return ""

# ===== COMPANY MAP =====
COMPANY_MAP = {
    "TESLA":"TSLA","APPLE":"AAPL","NVIDIA":"NVDA",
    "AMD":"AMD","META":"META","MICROSOFT":"MSFT",
    "AMAZON":"AMZN","GOOGLE":"GOOGL"
}

def get_symbol(text):
    t = text.upper()
    if t in COMPANY_MAP.values():
        return t
    for name, s in COMPANY_MAP.items():
        if name in t:
            return s
    return t

# ===== STOCK INFO =====
async def get_stock(symbol):
    async with aiohttp.ClientSession() as session:
        q = await (await session.get(
            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        )).json()

        if not q or q.get("c") is None:
            return "❌ السهم غير موجود"

        price = q.get("c")
        change = round(q.get("dp", 0), 2)
        arrow = "📈" if change >= 0 else "📉"

        ai = await ai_analyze(symbol)

        return f"""
📊 {symbol}

💰 {price}$ {arrow} {change}%

🤖 {ai}
"""

# ===== COMMANDS =====
async def stock_cmd(update, context):
    if not context.args:
        await update.message.reply_text("اكتب:\n/stock TSLA")
        return

    symbol = get_symbol(context.args[0])
    data = await get_stock(symbol)
    await update.message.reply_text(data)

# ===== ARABIC TEXT HANDLER =====
async def handle_text(update, context):
    text = update.message.text.lower()

    # سهم TSLA
    if text.startswith("سهم"):
        try:
            symbol = get_symbol(text.split(" ")[1])
            data = await get_stock(symbol)
            await update.message.reply_text(data)
        except:
            await update.message.reply_text("اكتب: سهم TSLA")

    # تحليل TSLA
    elif text.startswith("تحليل"):
        try:
            symbol = get_symbol(text.split(" ")[1])
            result = await ai_analyze(symbol)
            await update.message.reply_text(result)
        except:
            await update.message.reply_text("اكتب: تحليل TSLA")

# ===== NEWS (اختياري بسيط) =====
async def news_loop():
    while True:
        await asyncio.sleep(300)

# ===== RUN =====
async def run():
    app = Application.builder().token(TOKEN).build()

    # أوامر
    app.add_handler(CommandHandler("stock", stock_cmd))

    # عربي
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    await app.initialize()
    await app.start()

    await news_loop()

if __name__ == "__main__":
    asyncio.run(run())