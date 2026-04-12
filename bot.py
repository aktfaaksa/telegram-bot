import asyncio
import aiohttp
import hashlib
import os
import time
from telegram import Bot
from deep_translator import GoogleTranslator

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))

bot = Bot(token=TOKEN)

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

# =========================
# 🧠 أدوات
# =========================

def normalize_title(title):
    return " ".join(str(title).lower().split()[:6])

def news_id(title):
    return hashlib.md5(normalize_title(title).encode()).hexdigest()

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# =========================
# 🧠 تحليل الخبر
# =========================

def analyze(title):
    t = title.lower()

    positive = ["beat","strong","growth","surge","profit","record","ai"]
    negative = ["miss","loss","drop","crash","weak","fear","cut"]

    if any(w in t for w in positive):
        return "🚀 إيجابي"

    if any(w in t for w in negative):
        return "📉 سلبي"

    return None

# =========================
# 🎯 Impact Score (المهم)
# =========================

def impact_score(title, change):
    t = title.lower()
    score = 0

    strong_pos = ["earnings","beat","record","surge","guidance","ai","growth"]
    strong_neg = ["miss","loss","cut","downgrade","crash","warn"]

    if any(w in t for w in strong_pos):
        score += 2

    if any(w in t for w in strong_neg):
        score += 2

    if change is not None:
        if abs(change) >= 3:
            score += 3
        elif abs(change) >= 1.5:
            score += 2
        elif abs(change) >= 1:
            score += 1

    return score

# =========================
# 🌐 API
# =========================

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

# =========================
# 🚀 MAIN
# =========================

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

                    for n in news[:25]:
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

                        # ربط السهم
                        for s in WATCHLIST:
                            if s.lower() in title_lower:
                                symbol = s
                                break

                        if not symbol:
                            continue

                        change = await get_price(session, symbol)

                        if change is None:
                            continue

                        score = impact_score(title, change)

                        # 🎯 التوازن المثالي
                        if score >= 6:
                            strength = "🚀 قوي جدًا"
                        elif score >= 5:
                            strength = "🔥 قوي"
                        elif score >= 3:
                            strength = "🟡 متابعة"
                        else:
                            continue

                        action = "BUY" if change > 0 else "SELL"
                        arrow = "📈" if change > 0 else "📉"

                        msg = f"""🚨 MARKET SIGNAL

💼 {symbol} {arrow} {change}%

🧠 {label} | {strength}

🎯 Action: {action}

📰 {title}

🇸🇦 {translate(title)}

🔗 {url}"""

                        await bot.send_message(chat_id=CHAT_ID, text=msg)

                        sent_news.add(nid)

                        # 🧠 تنظيف الذاكرة
                        if len(sent_news) > 500:
                            sent_news = set(list(sent_news)[-250:])

                        await asyncio.sleep(1)

                await asyncio.sleep(15)

            except Exception as e:
                print("❌ Error:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())