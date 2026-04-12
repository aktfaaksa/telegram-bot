# ===== Alpha Market Intelligence (Stable Working Version) =====

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

CHAT_ID = int(os.getenv("CHAT_ID"))

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

    if any(w in t for w in ["beat","strong","growth","surge","profit","record","ai"]):
        return "🚀 إيجابي"

    if any(w in t for w in ["miss","loss","drop","crash","weak"]):
        return "📉 سلبي"

    return None

async def get_news(session):
    try:
        url = f"https://finnhub.io/api/v1/news?category=business&token={API_KEY}"
        async with session.get(url) as r:
            data = await r.json()
            return data if isinstance(data, list) else []
    except:
        return []

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

    print("🚀 BOT STARTED")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = time.time()

                if now - last_run > 120:
                    last_run = now

                    news = await get_news(session)
                    print("📰 News:", len(news))

                    for n in news[:20]:
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
                        symbol = None

                        # ===== الطريقة المرنة (مثل v4) =====
                        for s in WATCHLIST:
                            if s.lower() in title_lower:
                                symbol = s
                                break

                        # fallback
                        if not symbol:
                            words = title.split()
                            for w in words:
                                if w.isupper() and len(w) <= 5:
                                    symbol = w
                                    break

                        if not symbol:
                            continue

                        change = await get_price(session, symbol)

                        # خففنا الشرط عشان يرسل
                        if change is None:
                            continue

                        arrow = "📈" if change > 0 else "📉"

                        msg = f"""🚨 Signal

💼 {symbol} {arrow} {change}%

🧠 {label}

📰 {title}

🇸🇦 {translate(title)}

🔗 {url}"""

                        print(f"🚀 Sending {symbol}")

                        await bot.send_message(chat_id=CHAT_ID, text=msg)

                        sent_news.add(nid)

                        await asyncio.sleep(1)

                await asyncio.sleep(15)

            except Exception as e:
                print("❌ Error:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())