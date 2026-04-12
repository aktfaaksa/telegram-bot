# ===== Alpha Market Intelligence v4+ (Smart Mode) =====

import asyncio
import aiohttp
import hashlib
import os
import time
from telegram import Bot
from deep_translator import GoogleTranslator

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880,
]

WATCHLIST = [
    "NVDA","AAPL","MSFT","GOOGL","AMZN","META","TSLA",
    "AMD","AVGO","TSM","INTC",
    "JPM","GS","BAC",
    "XOM","CVX",
    "JNJ","PFE","MRK",
    "MCD","NKE","HD",
    "NFLX","CRM","UBER"
]

sent_news = set()
last_run = 0

# ===== تحسين التحليل =====
POSITIVE = ["beat","strong","growth","surge","profit","record","upgrade","ai","demand","expansion"]
NEGATIVE = ["miss","loss","drop","crash","weak","downgrade","cut","decline","lawsuit"]

def smart_analyze(title):
    t = title.lower()
    score = 0

    for w in POSITIVE:
        if w in t:
            score += 2

    for w in NEGATIVE:
        if w in t:
            score -= 2

    # القرار
    if score >= 3:
        return "BUY 🚀", min(90, 50 + score * 10)

    if score <= -3:
        return "SELL 📉", min(90, 50 + abs(score) * 10)

    return "WATCH 👀", 50


# ===== أدوات =====
def normalize_title(title):
    return " ".join(str(title).lower().split()[:6])

def news_id(title):
    return hashlib.md5(normalize_title(title).encode()).hexdigest()

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== API =====
async def get_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    async with session.get(url) as r:
        data = await r.json()
        return data if isinstance(data, list) else []

async def get_price(session, symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        async with session.get(url) as r:
            d = await r.json()
            if d.get("c") and d.get("pc"):
                return round(((d["c"] - d["pc"]) / d["pc"]) * 100, 2)
    except:
        pass
    return None

# ===== التشغيل =====
async def main():
    global last_run, sent_news

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = time.time()

                if now - last_run > 120:
                    last_run = now

                    news = await get_news(session)

                    for n in news[:10]:
                        if not isinstance(n, dict):
                            continue

                        title = n.get("headline")
                        url = n.get("url")

                        if not title or not url:
                            continue

                        nid = news_id(title)
                        if nid in sent_news:
                            continue

                        decision, confidence = smart_analyze(title)

                        if decision == "WATCH 👀":
                            continue

                        title_lower = title.lower()

                        for symbol in WATCHLIST:
                            if symbol.lower() in title_lower:
                                change = await get_price(session, symbol)

                                if change and abs(change) >= 2:
                                    arrow = "📈" if change > 0 else "📉"

                                    msg = f"""🚨 Smart Signal

💼 {symbol} {arrow} {change}%

🧠 Decision: {decision}
🎯 Confidence: {confidence}%

📰 {title}

🇸🇦 {translate(title)}

🔗 {url}"""

                                    for c in CHAT_IDS:
                                        await bot.send_message(chat_id=c, text=msg)

                                    sent_news.add(nid)
                                    break

                        await asyncio.sleep(1)

                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())