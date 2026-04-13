import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Application, CommandHandler
from deep_translator import GoogleTranslator
from openai import OpenAI

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_KEY = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=TOKEN)

# ===== AI =====
USE_AI = True

client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1"
)

async def ai_analyze(text):
    try:
        response = client.chat.completions.create(
            model="qwen/qwen3-next-80b-a3b-instruct:free",
            messages=[{"role": "user", "content": f"""
Analyze and return ONLY:

Decision: BUY or SELL or HOLD
Confidence: 0-100

{text}
"""}]
        )
        return response.choices[0].message.content
    except:
        return ""

# ===== COMPANY MAP =====
COMPANY_MAP = {
    "TESLA":"TSLA","APPLE":"AAPL","NVIDIA":"NVDA","AMD":"AMD",
    "META":"META","MICROSOFT":"MSFT","AMAZON":"AMZN",
    "NETFLIX":"NFLX","INTEL":"INTC","GOOGLE":"GOOGL"
}

# ===== COUNTRY =====
def classify_country(c):
    if c == "US": return "🇺🇸 أمريكية"
    if c == "CN": return "🇨🇳 صينية"
    if c == "GB": return "🇬🇧 بريطانية"
    return f"🌍 {c}"

# ===== SYMBOL =====
def get_symbol(text):
    t = text.upper()
    if t in COMPANY_MAP.values():
        return t
    for name, s in COMPANY_MAP.items():
        if name in t:
            return s
    return t

# ===== STOCK INFO =====
async def get_stock_full(symbol):
    async with aiohttp.ClientSession() as session:

        quote = await (await session.get(
            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        )).json()

        profile = await (await session.get(
            f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={API_KEY}"
        )).json()

        metric = await (await session.get(
            f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={API_KEY}"
        )).json()

        if not quote or quote.get("c") is None:
            return "❌ السهم غير موجود"

        price = quote.get("c")
        change = round(quote.get("dp", 0), 2)

        name = profile.get("name", "")
        country = classify_country(profile.get("country", "N/A"))
        sector = profile.get("finnhubIndustry", "N/A")
        shares = profile.get("shareOutstanding", "N/A")
        cap = profile.get("marketCapitalization", "N/A")

        m = metric.get("metric", {})
        eps = m.get("epsNormalizedAnnual", "N/A")
        pe = m.get("peNormalizedAnnual", "N/A")
        debt = m.get("totalDebt/totalEquityAnnual", "N/A")

        ai_text = ""
        if USE_AI:
            ai_text = await ai_analyze(symbol)

        return f"""
📊 {symbol} - {name}

🌍 {country}
🏭 {sector}

💰 {price}$ | {change}%

📦 Shares: {shares} B
💵 Market Cap: {cap} B$

📈 EPS: {eps}
📊 P/E: {pe}
🏦 Debt: {debt}

🤖 {ai_text}
"""

# ===== COMMANDS =====
async def stock_cmd(update, context):
    if not context.args:
        await update.message.reply_text("اكتب:\n/سهم TSLA")
        return

    symbol = get_symbol(context.args[0])
    data = await get_stock_full(symbol)
    await update.message.reply_text(data)

async def ai_cmd(update, context):
    if not context.args:
        return
    result = await ai_analyze(context.args[0])
    await update.message.reply_text(result)

async def help_cmd(update, context):
    await update.message.reply_text("""
📌 الأوامر:

/سهم TSLA → معلومات الشركة
/تحليل TSLA → تحليل AI
/مساعدة
""")

# ===== NEWS SYSTEM (بدون تغيير كبير) =====
sent = set()

async def get_news():
    async with aiohttp.ClientSession() as session:
        url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
        data = await (await session.get(url)).json()
        return data[:10]

async def send_news():
    while True:
        try:
            news = await get_news()

            for n in news:
                title = n.get("headline")
                link = n.get("url")

                if not title or title in sent:
                    continue

                sent.add(title)

                msg = f"📰 {title}\n🔗 {link}"

                for c in CHAT_IDS:
                    await bot.send_message(chat_id=c, text=msg)

            await asyncio.sleep(300)

        except:
            await asyncio.sleep(60)

# ===== RUN =====
async def run():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler(["سهم","stock"], stock_cmd))
    app.add_handler(CommandHandler(["تحليل","ai"], ai_cmd))
    app.add_handler(CommandHandler(["مساعدة","help"], help_cmd))

    await app.initialize()
    await app.start()

    await send_news()

if __name__ == "__main__":
    asyncio.run(run())