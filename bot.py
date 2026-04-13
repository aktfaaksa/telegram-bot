# ===== Alpha Market Intelligence v12.3 =====
# Ultra Pro Trading News Engine

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
MAX_NEWS_PER_CYCLE = 15

# ===== IMPACT =====
HIGH_IMPACT = [
    "beats earnings","misses earnings","raises guidance","cuts forecast",
    "acquisition","merger","buyout","bankruptcy",
    "contract","wins contract","deal secured"
]

MEDIUM_IMPACT = [
    "upgrade","downgrade","price target","partnership"
]

MACRO_IMPACT = [
    "fed","interest rate","inflation","cpi","ppi",
    "jobs","unemployment","gdp","recession",
    "treasury","yield",
    "dow","nasdaq","s&p","stock market today",
    "oil","blockade","iran","pipeline","gold"
]

TECH_IMPACT = [
    "ai","artificial intelligence","chip","semiconductor","nvidia"
]

# ===== FILTERS =====
IGNORE_ANALYSIS = [
    "what","why","how","will","could","should","did",
    "outlook","forecast","expect","analysis",
    "says","warns"
]

IGNORE_WEAK = [
    "how to","mistakes","millionaire","rules","tax",
    "mortgage","personal finance","credit card",
    "saving","retirement","etf","vs"
]

IGNORE_OPINION = [
    "best","top stocks","to invest","buy now",
    "screaming buy","should you","is it time"
]

IGNORE_ADMIN = [
    "appoint","appoints","names","named",
    "hire","hiring","executive","board","adviser"
]

IGNORE_USELESS = [
    "optimistic","steady","roadblocks",
    "good life","growth initiatives","analysts say"
]

# ===== TRANSLATION =====
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== ANTI SPAM =====
def is_new(title, link):
    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def normalize(title):
    t = re.sub(r'[^a-z0-9 ]', '', title.lower())
    return t[:60]

def is_unique(title):
    short = normalize(title)
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

# ===== IMPACT LOGIC =====
def get_impact(title):
    t = title.lower()

    if any(x in t for x in HIGH_IMPACT):
        return "🔥 HIGH"

    elif any(x in t for x in MACRO_IMPACT):
        # فقط القوي يعتبر MACRO
        if any(x in t for x in ["oil","iran","treasury","gold","blockade"]):
            return "🌍 MACRO"
        else:
            return "⚡ MEDIUM"

    elif any(x in t for x in TECH_IMPACT):
        return "⚡ MEDIUM"

    elif any(x in t for x in MEDIUM_IMPACT):
        return "⚡ MEDIUM"

    else:
        return "🟡 GENERAL"

# ===== SYMBOL =====
def extract_symbol(title):
    t = title.upper()

    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    for name, s in COMPANY_MAP.items():
        if name in t:
            return s

    for s in WATCHLIST:
        if re.search(rf'\b{s}\b', t):
            return s

    return None

# ===== API =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

async def get_market_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    async with session.get(url) as r:
        data = await r.json()

    out = []
    for n in data[:20]:
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
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    title_lower = title.lower()

    # ===== FILTERS =====
    if "finnhub" in link:
        return False

    if any(x in title_lower for x in IGNORE_ANALYSIS):
        return False

    if any(x in title_lower for x in IGNORE_WEAK):
        return False

    if any(x in title_lower for x in IGNORE_OPINION):
        return False

    if any(x in title_lower for x in IGNORE_ADMIN):
        return False

    if any(x in title_lower for x in IGNORE_USELESS):
        return False

    # ===== IMPACT =====
    impact = get_impact(title)

    symbol = extract_symbol(title)
    if not symbol:
        symbol = "MARKET"

    if symbol == "MARKET" and impact == "🟡 GENERAL":
        return False

    translated = translate_text(title)

    stock_info = ""
    if symbol != "MARKET":
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
            await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except:
            pass

    return True

# ===== MAIN =====
async def main():
    print("🚀 Bot v12.3 Running (Ultra Pro Mode)...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                news = await get_all(session)

                count = 0
                for n in news:
                    if count >= MAX_NEWS_PER_CYCLE:
                        break

                    if await send(bot, session, n):
                        count += 1

                await asyncio.sleep(300)

            except Exception as e:
                print("Error:", e)
                await asyncio.sleep(60)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())