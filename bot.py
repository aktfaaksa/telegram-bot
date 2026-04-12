# ===== Alpha Market Intelligence v3.4 =====
# Clean Version - No Spam (Only Company News)

import asyncio
import aiohttp
import hashlib
import os
import time
from datetime import datetime
from telegram import Bot
from deep_translator import GoogleTranslator
import feedparser

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880,
]

# ====== شركات ======
WATCHLIST = [
    "NVDA","AAPL","MSFT","GOOGL","AMZN","META","TSLA",
    "AMD","AVGO","TSM","INTC",
    "JPM","GS","BAC",
    "XOM","CVX",
    "JNJ","PFE","MRK",
    "MCD","NKE","HD",
    "NFLX","CRM","UBER"
]

# ====== ذاكرة ======
sent_news = set()
last_news_sent = 0
last_index_sent = 0

# ====== أدوات ======
def normalize_title(title):
    return " ".join(str(title).lower().split()[:6])

def news_id(title):
    try:
        return hashlib.md5(normalize_title(title).encode()).hexdigest()
    except:
        return None

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# 🔥 كشف السهم بشكل ذكي
def detect_stock(title):
    t = str(title).lower()

    for s in WATCHLIST:
        name = s.lower()
        if f" {name} " in f" {t} ":
            return s
    return None

# ====== تحليل ======
def analyze(title):
    t = str(title).lower()

    if any(w in t for w in ["beat","strong","growth","surge","profit","record"]):
        return "🚀 إيجابي قوي"

    if any(w in t for w in ["miss","loss","drop","crash","weak"]):
        return "📉 سلبي قوي"

    return "📊 خبر مهم"

# ====== Finnhub ======
async def get_company_news(session, symbol):
    try:
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&token={API_KEY}"
        async with session.get(url) as r:
            data = await r.json()
            return data if isinstance(data, list) else []
    except:
        return []

# ====== السعر ======
async def get_price(session, symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        async with session.get(url) as r:
            d = await r.json()

            if isinstance(d, dict) and d.get("c") and d.get("pc"):
                return round(((d["c"] - d["pc"]) / d["pc"]) * 100, 2)
    except:
        pass
    return None

# ====== التشغيل ======
async def main():
    global last_news_sent, sent_news

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now_time = time.time()

                if now_time - last_news_sent > 180:
                    last_news_sent = now_time

                    for symbol in WATCHLIST[:10]:
                        news_list = await get_company_news(session, symbol)

                        for n in news_list[:1]:
                            if not isinstance(n, dict):
                                continue

                            title = n.get("headline")
                            url = n.get("url")

                            if not title or not url:
                                continue

                            # 🚨 فلترة سياسية
                            if any(word in title.lower() for word in [
                                "iran","israel","war","nato","politics","trump"
                            ]):
                                continue

                            nid = news_id(title)
                            if not nid or nid in sent_news:
                                continue

                            label = analyze(title)
                            change = await get_price(session, symbol)

                            price_text = ""
                            if change:
                                arrow = "📈" if change > 0 else "📉"
                                price_text = f"\n💼 {symbol} {arrow} {change}%\n"

                            ar = translate(title)

                            msg = f"""{label}
{price_text}
📰 {title}

🇸🇦 {ar}

🔗 {url}"""

                            for c in CHAT_IDS:
                                await bot.send_message(chat_id=c, text=msg)

                            sent_news.add(nid)

                            await asyncio.sleep(1)

                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
