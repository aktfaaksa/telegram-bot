# ===== Alpha Market Intelligence v3.0 =====
# Market + Multi News + Company Tracking + Price Link

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

# ====== شركات قوية ======
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
market_open_sent = False
market_close_sent = False

# ====== أدوات ======
def normalize_title(title):
    return " ".join(title.lower().split()[:6])

def news_id(title):
    return hashlib.md5(normalize_title(title).encode()).hexdigest()

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def detect_stock(title):
    t = title.lower()
    for s in WATCHLIST:
        if s.lower() in t:
            return s
    return None

# ====== تحليل ======
def analyze(title):
    t = title.lower()
    score = 0

    if any(w in t for w in ["beat","strong","growth","surge","profit"]):
        score += 3
    if any(w in t for w in ["miss","loss","drop","crash"]):
        score -= 3

    if score >= 3:
        return "🚀 إيجابي قوي"
    elif score > 0:
        return "📈 إيجابي"
    elif score <= -3:
        return "📉 سلبي قوي"
    elif score < 0:
        return "⚠️ سلبي"
    else:
        return "⚖️ عادي"

# ====== Finnhub ======
async def get_general_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    try:
        async with session.get(url) as r:
            return await r.json()
    except:
        return []

async def get_company_news(session, symbol):
    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&token={API_KEY}"
    try:
        async with session.get(url) as r:
            return await r.json()
    except:
        return []

# ====== RSS ======
def get_rss(url):
    try:
        feed = feedparser.parse(url)
        return feed.entries[:5]
    except:
        return []

# ====== السوق ======
def is_market_open():
    now = datetime.now()
    if now.weekday() > 4:
        return False

    minutes = now.hour * 60 + now.minute
    return 990 <= minutes <= 1380

def is_market_just_open():
    now = datetime.now()
    return now.hour == 16 and now.minute == 30

def is_market_close():
    now = datetime.now()
    return now.hour == 23 and now.minute == 0

# ====== السعر ======
async def get_price(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    try:
        async with session.get(url) as r:
            d = await r.json()
            if d.get("c") and d.get("pc"):
                change = round(((d["c"] - d["pc"]) / d["pc"]) * 100, 2)
                return change
    except:
        pass
    return None

# ====== التشغيل ======
async def main():
    global last_news_sent, last_index_sent
    global market_open_sent, market_close_sent

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = datetime.now()
                now_time = time.time()

                # ===== افتتاح =====
                if is_market_just_open() and not market_open_sent:
                    for c in CHAT_IDS:
                        await bot.send_message(chat_id=c, text="🟢 افتتاح السوق الأمريكي")
                    market_open_sent = True

                # ===== إغلاق =====
                if is_market_close() and not market_close_sent:
                    for c in CHAT_IDS:
                        await bot.send_message(chat_id=c, text="🔴 إغلاق السوق الأمريكي")
                    market_close_sent = True

                if now.hour == 1:
                    market_open_sent = False
                    market_close_sent = False

                # ===== مؤشرات =====
                if is_market_open() and (now_time - last_index_sent > 3600):
                    last_index_sent = now_time

                    spy = await get_price(session,"SPY")
                    qqq = await get_price(session,"QQQ")
                    dia = await get_price(session,"DIA")

                    msg = f"""📊 مؤشرات السوق

💻 ناسداك: {qqq if qqq else '—'}%
📈 S&P500: {spy if spy else '—'}%
🏛️ داو جونز: {dia if dia else '—'}%"""

                    for c in CHAT_IDS:
                        await bot.send_message(chat_id=c, text=msg)

                # ===== الأخبار =====
                if now_time - last_news_sent > 300:
                    last_news_sent = now_time

                    news = []

                    # Finnhub عام
                    for n in await get_general_news(session):
                        news.append((n.get("headline"), n.get("url")))

                    # RSS
                    for n in get_rss("https://www.cnbc.com/id/100003114/device/rss/rss.html"):
                        news.append((n.title, n.link))

                    for n in get_rss("https://feeds.reuters.com/reuters/businessNews"):
                        news.append((n.title, n.link))

                    # شركات
                    for symbol in WATCHLIST[:10]:
                        company_news = await get_company_news(session, symbol)
                        for n in company_news[:2]:
                            news.append((n.get("headline"), n.get("url")))

                    # معالجة
                    for title, url in news:
                        if not title or not url:
                            continue

                        nid = news_id(title)
                        if nid in sent_news:
                            continue

                        label = analyze(title)
                        stock = detect_stock(title)

                        price_text = ""
                        if stock:
                            change = await get_price(session, stock)
                            if change:
                                arrow = "📈" if change > 0 else "📉"
                                price_text = f"\n💼 {stock} {arrow} {change}%\n"

                        ar = translate(title)

                        msg = f"""{label}
{price_text}
📰 {title}

🇸🇦 {ar}

🔗 {url}"""

                        for c in CHAT_IDS:
                            await bot.send_message(chat_id=c, text=msg)

                        sent_news.add(nid)

                        if len(sent_news) > 500:
                            sent_news.pop()

                        await asyncio.sleep(1)

                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())

