# ===== Alpha Market Intelligence v4.0 =====
# Trading Signals + Watchlist + External Opportunities

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

def normalize_title(title):
    return " ".join(str(title).lower().split()[:6])

def news_id(title):
    return hashlib.md5(normalize_title(title).encode()).hexdigest()

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def analyze(title):
    t = title.lower()

    if any(w in t for w in ["beat","strong","growth","surge","profit","record"]):
        return "🚀 إيجابي قوي"

    if any(w in t for w in ["miss","loss","drop","crash","weak"]):
        return "📉 سلبي قوي"

    return None

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

async def main():
    global last_run, sent_news

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = time.time()

                if now - last_run > 120:
                    last_run = now

                    news = await get_news(session)

                    for n in news[:15]:
                        if not isinstance(n, dict):
                            continue

                        title = n.get("headline")
                        url = n.get("url")

                        if not title or not url:
                            continue

                        nid = news_id(title)
                        if nid in sent_news:
                            continue

                        label = analyze(title)
                        if not label:
                            continue

                        title_lower = title.lower()

                        # 🟢 داخل WATCHLIST
                        for symbol in WATCHLIST:
                            if symbol.lower() in title_lower:
                                change = await get_price(session, symbol)

                                if change and abs(change) >= 2:
                                    arrow = "📈" if change > 0 else "📉"
                                    msg = f"""🚨 فرصة تداول

💼 {symbol} {arrow} {change}%

📰 {title}

🇸🇦 {translate(title)}

🔗 {url}"""

                                    for c in CHAT_IDS:
                                        await bot.send_message(chat_id=c, text=msg)

                                    sent_news.add(nid)
                                    break

                        # 🟡 خارج WATCHLIST
                        else:
                            words = title.split()
                            for word in words:
                                if word.isupper() and len(word) <= 5:
                                    change = await get_price(session, word)

                                    if change and abs(change) >= 5:
                                        arrow = "📈" if change > 0 else "📉"
                                        msg = f"""🚨 فرصة جديدة 🔥

💼 {word} {arrow} {change}%

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
