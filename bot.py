# ===== Alpha Market Intelligence v8.0 =====
# Smart Trading News Only (No Noise)

import asyncio
import aiohttp
import feedparser
import hashlib
import os
from datetime import datetime, timedelta
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [
    CHAT_ID_MAIN,
    6315087880,
]

bot = Bot(token=TOKEN)

# ===== WATCHLIST =====
WATCHLIST = ["AAPL", "TSLA", "NVDA", "AMD", "META", "MSFT", "AMZN", "NFLX", "INTC", "BAC"]

# ===== COMPANY MAP =====
COMPANY_MAP = {
    "TESLA": "TSLA",
    "APPLE": "AAPL",
    "NVIDIA": "NVDA",
    "ADVANCED MICRO DEVICES": "AMD",
    "AMD": "AMD",
    "META": "META",
    "MICROSOFT": "MSFT",
    "AMAZON": "AMZN",
    "NETFLIX": "NFLX",
    "INTEL": "INTC",
    "BANK OF AMERICA": "BAC",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "GOLDMAN SACHS": "GS"
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

IMPORTANT_WORDS = [
    "earnings", "eps", "revenue", "guidance",
    "acquisition", "merger", "buyout",
    "upgrade", "downgrade", "rating",
    "approval", "forecast", "beats", "misses"
]

WEAK_NEWS = [
    "season", "outlook", "preview", "what to expect",
    "kicks off", "entering", "expected to"
]

# ===== TRANSLATION =====
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== ANTI DUP =====
def is_new(title, link):
    h = hashlib.md5((title + link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def normalize_title(title):
    return title.lower()[:60]

def is_unique(title):
    short = normalize_title(title)
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

# ===== CATEGORY =====
def categorize_news(title):
    t = title.lower()

    if any(x in t for x in ["beats", "misses", "reports earnings", "eps"]):
        return "🟢 Earnings Report"

    elif "earnings" in t:
        return "🟡 Earnings (General)"

    elif any(x in t for x in ["acquisition", "merger", "buyout"]):
        return "🔵 M&A"

    elif any(x in t for x in ["upgrade", "downgrade", "rating"]):
        return "🟣 Analyst"

    else:
        return "🔴 Macro"

# ===== SYMBOL DETECTION =====
def extract_symbol(title):
    t = title.upper()

    for symbol in WATCHLIST:
        if symbol in t:
            return symbol

    for name, symbol in COMPANY_MAP.items():
        if name in t:
            return symbol

    return None

# ===== FINNHUB =====
async def get_stock_data(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as resp:
        return await resp.json()

async def get_finnhub_market_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    async with session.get(url) as resp:
        data = await resp.json()

    news = []
    for item in data[:10]:
        link = item.get("url")
        if not link or "finnhub.io/api" in link:
            continue

        news.append({
            "title": item["headline"],
            "link": link
        })

    return news

async def get_company_news(session, symbol):
    today = datetime.utcnow().date()
    past = today - timedelta(days=2)

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={past}&to={today}&token={API_KEY}"

    async with session.get(url) as resp:
        data = await resp.json()

    news = []
    for item in data[:5]:
        link = item.get("url")
        if not link or "finnhub.io/api" in link:
            continue

        news.append({
            "title": item["headline"],
            "link": link,
            "symbol": symbol
        })

    return news

# ===== RSS =====
def get_rss_news():
    news = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            news.append({
                "title": entry.title,
                "link": entry.link
            })
    return news

# ===== COLLECT =====
async def get_all_news(session):
    all_news = []

    all_news.extend(get_rss_news())
    all_news.extend(await get_finnhub_market_news(session))

    for symbol in WATCHLIST:
        all_news.extend(await get_company_news(session, symbol))

    return all_news

# ===== SEND =====
async def send_news(bot, session, news, sent_symbols):
    title = news["title"]
    link = news["link"]

    # Anti-spam
    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    if not any(word in title.lower() for word in IMPORTANT_WORDS):
        return False

    if any(w in title.lower() for w in WEAK_NEWS):
        return False

    symbol = news.get("symbol") or extract_symbol(title)

    # 🔥 أهم شرط: لازم سهم
    if not symbol:
        return False

    if symbol in sent_symbols:
        return False

    sent_symbols.add(symbol)

    category = categorize_news(title)
    translated = translate_text(title)

    stock_info = ""

    try:
        data = await get_stock_data(session, symbol)
        price = data.get("c")
        change = data.get("dp")

        stock_info = f"""

📊 {symbol}
💰 Price: {price}$
📈 Change: {round(change,2)}%
"""
    except:
        pass

    message = f"""
{category}

📰 {title}

🇸🇦 {translated}
{stock_info}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                disable_web_page_preview=False
            )
        except Exception as e:
            print("Send error:", e)

    return True

# ===== MAIN =====
async def main():
    print("🚀 Bot Running v8 (Pro Filter Mode)...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                news_list = await get_all_news(session)

                news_sent = 0
                sent_symbols = set()

                for news in news_list:
                    if news_sent >= MAX_NEWS_PER_CYCLE:
                        break

                    sent = await send_news(bot, session, news, sent_symbols)

                    if sent:
                        news_sent += 1

                await asyncio.sleep(300)

            except Exception as e:
                print("Main error:", e)
                await asyncio.sleep(60)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())