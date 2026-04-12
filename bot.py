# ===== Alpha Market Intelligence ULTRA (Balanced Mode) =====

import asyncio
import aiohttp
import hashlib
import os
import time
import re
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== إعدادات =====
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

NAME_MAP = {
    "apple": "AAPL","microsoft": "MSFT","nvidia": "NVDA",
    "amazon": "AMZN","tesla": "TSLA","google": "GOOGL",
    "meta": "META","netflix": "NFLX","uber": "UBER",
    "intel": "INTC","amd": "AMD","exxon": "XOM",
    "chevron": "CVX","goldman": "GS","nike": "NKE"
}

SECTORS = {
    "TECH": ["ai","chip","cloud","data","software"],
    "ENERGY": ["oil","gas","energy","crude","opec"],
    "MINING": ["gold","copper","lithium","silver"],
    "REAL_ESTATE": ["real estate","housing","reit"],
    "FINANCE": ["bank","fed","interest","inflation"],
}

BLOCK_WORDS = [
    "couple","relationship","psychologist",
    "lifestyle","dating","family","health"
]

sent_news = set()
last_run = 0
last_sent_symbol = {}

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

# ===== تحليل =====
def is_irrelevant(title):
    t = title.lower()
    return any(w in t for w in BLOCK_WORDS)

def detect_sector(title):
    t = title.lower()
    for sector, words in SECTORS.items():
        if any(w in t for w in words):
            return sector
    return "GENERAL"

def score_news(title):
    t = title.lower()
    score = 0

    strong = ["earnings","beat","miss","upgrade","downgrade","surge","crash"]
    medium = ["growth","revenue","profit","forecast","deal","demand","ai"]

    for w in strong:
        if w in t:
            score += 3

    for w in medium:
        if w in t:
            score += 2

    return score

def find_symbol(title):
    title_lower = title.lower()

    for name, sym in NAME_MAP.items():
        if name in title_lower:
            return sym

    words = re.findall(r'\b[A-Z]{2,5}\b', title)
    for w in words:
        if w in WATCHLIST:
            return w

    return None

# ===== API =====
async def get_news(session):
    try:
        url = f"https://finnhub.io/api/v1/news?category=business&token={API_KEY}"
        async with session.get(url) as r:
            data = await r.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        print("❌ News error:", e)
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

# ===== التشغيل =====
async def main():
    global last_run, sent_news, last_sent_symbol

    print("🚀 BOT STARTED")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = time.time()

                if now - last_run > 180:
                    last_run = now

                    news = await get_news(session)
                    print("📰 News count:", len(news))

                    for n in news[:25]:
                        title = n.get("headline")
                        url = n.get("url")

                        if not title or not url:
                            continue

                        if is_irrelevant(title):
                            continue

                        nid = news_id(title)
                        if nid in sent_news:
                            continue

                        symbol = find_symbol(title)
                        if not symbol:
                            continue

                        now_time = time.time()
                        if symbol in last_sent_symbol:
                            if now_time - last_sent_symbol[symbol] < 600:
                                continue

                        score = score_news(title)

                        # 🔥 التعديل هنا
                        if score < 1:
                            continue

                        change = await get_price(session, symbol)

                        # 🔥 التعديل هنا (خففنا الشرط)
                        if change is None:
                            continue

                        sector = detect_sector(title)

                        print(f"DEBUG: {symbol} | score={score} | change={change}")

                        last_sent_symbol[symbol] = now_time
                        sent_news.add(nid)

                        arrow = "📈" if change > 0 else "📉"

                        msg = f"""🚨 ULTRA Signal

🏭 Sector: {sector}
💼 {symbol} {arrow} {change}%

🧠 Score: {score}/10

📰 {title}

🇸🇦 {translate(title)}

🔗 {url}"""

                        for c in CHAT_IDS:
                            await bot.send_message(chat_id=c, text=msg)

                        await asyncio.sleep(1)

                await asyncio.sleep(20)

            except Exception as e:
                print("❌ Error:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())