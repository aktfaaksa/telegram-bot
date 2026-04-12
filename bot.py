# ===== Alpha Market Intelligence v10.0 =====
# Smart Impact + Accurate Symbol Detection

import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
from datetime import datetime, timedelta
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [CHAT_ID_MAIN, 6315087880]

bot = Bot(token=TOKEN)

# ===== WATCHLIST =====
WATCHLIST = ["AAPL","TSLA","NVDA","AMD","META","MSFT","AMZN","NFLX","INTC","BAC","GOOGL","GS"]

# ===== COMPANY MAP =====
COMPANY_MAP = {
    "TESLA":"TSLA","APPLE":"AAPL","NVIDIA":"NVDA","AMD":"AMD",
    "META":"META","MICROSOFT":"MSFT","AMAZON":"AMZN",
    "NETFLIX":"NFLX","INTEL":"INTC","BANK OF AMERICA":"BAC",
    "GOOGLE":"GOOGL","ALPHABET":"GOOGL","GOLDMAN SACHS":"GS"
}

# ===== RSS =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ===== MEMORY =====
sent_hashes = set()
seen_titles = set()

# ===== SETTINGS =====
MAX_NEWS_PER_CYCLE = 10

# ===== IMPACT =====
HIGH_IMPACT = [
    "beats","misses","raises guidance","cuts forecast",
    "acquisition","merger","buyout"
]

MEDIUM_IMPACT = [
    "upgrade","downgrade",
    "fda","approval","clinical",
    "contract","deal","partnership"
]

LOW_IMPACT = [
    "buyback","dividend",
    "insider buying","insider selling"
]

# ===== TRANSLATION =====
def clean_text(text):
    return text.replace("’", "'").replace("“", "").replace("”", "")

def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(clean_text(text))
    except:
        return text

# ===== ANTI SPAM =====
def is_new(title, link):
    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def is_unique(title):
    short = title.lower()[:60]
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

# ===== IMPACT DETECTION =====
def get_impact(title):
    t = title.lower()

    if any(x in t for x in HIGH_IMPACT):
        return "🔥 HIGH"
    elif any(x in t for x in MEDIUM_IMPACT):
        return "⚡ MEDIUM"
    elif any(x in t for x in LOW_IMPACT):
        return "⚪ LOW"
    else:
        return None

# ===== SYMBOL DETECTION (FIXED) =====
def extract_symbol(title):
    t = title.upper()

    # 1️⃣ ticker داخل أقواس (CRWV)
    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    # 2️⃣ ticker مباشر
    for s in WATCHLIST:
        if s in t:
            return s

    # 3️⃣ اسم شركة
    for name, s in COMPANY_MAP.items():
        if name in t:
            return s

    return None

# ===== FINNHUB =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

async def get_market_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    async with session.get(url) as r:
        data = await r.json()

    out = []
    for n in data[:10]:
        link = n.get("url")
        if not link or "finnhub" in link:
            continue
        out.append({"title": n["headline"], "link": link})
    return out

async def get_company_news(session, symbol):
    today = datetime.utcnow().date()
    past = today - timedelta(days=2)

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={past}&to={today}&token={API_KEY}"

    async with session.get(url) as r:
        data = await r.json()

    out = []
    for n in data[:5]:
        link = n.get("url")
        if not link or "finnhub" in link:
            continue
        out.append({"title": n["headline"], "link": link})
    return out

def get_rss():
    out = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            out.append({"title": e.title, "link": e.link})
    return out

# ===== COLLECT =====
async def get_all(session):
    data = []
    data.extend(get_rss())
    data.extend(await get_market_news(session))

    for s in WATCHLIST:
        data.extend(await get_company_news(session, s))

    return data

# ===== SEND =====
async def send(bot, session, news, sent_symbols):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    impact = get_impact(title)
    if not impact:
        return False

    # 🔥 استخراج السهم (مصَحّح)
    symbol = extract_symbol(title)

    if not symbol:
        return False

    # منع تكرار نفس السهم
    if symbol in sent_symbols:
        return False

    sent_symbols.add(symbol)

    # تجاهل LOW
    if impact == "⚪ LOW":
        return False

    translated = translate_text(title)

    stock_info = ""
    try:
        d = await get_stock(session, symbol)
        stock_info = f"""

📊 {symbol}
💰 Price: {d.get('c')}$
📈 Change: {round(d.get('dp',0),2)}%
"""
    except:
        pass

    message = f"""
{impact}

📰 *{title}*

🇸🇦 _{translated}_

{stock_info}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            print("Send error:", e)

    return True

# ===== MAIN =====
async def main():
    print("🚀 Bot v10 Running (Accurate Mode)...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                news = await get_all(session)

                sent_symbols = set()
                count = 0

                for n in news:
                    if count >= MAX_NEWS_PER_CYCLE:
                        break

                    sent = await send(bot, session, n, sent_symbols)

                    if sent:
                        count += 1

                await asyncio.sleep(300)

            except Exception as e:
                print("Error:", e)
                await asyncio.sleep(60)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())