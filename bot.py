# ===== Alpha Market Intelligence v6.0 =====
# News + Finnhub + Translation + Anti-Spam System

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
WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "AMD",
    "META", "MSFT", "AMZN"
]

# ===== RSS =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ===== MEMORY =====
sent_hashes = set()
seen_titles = set()

# ===== LIMIT =====
MAX_NEWS_PER_CYCLE = 10

# ===== FILTER =====
IMPORTANT_WORDS = [
    "earnings", "eps", "revenue", "guidance",
    "acquisition", "merger", "buyout",
    "upgrade", "downgrade", "rating",
    "approval", "forecast"
]

# ===== TRANSLATION =====
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== HASH (ANTI DUPLICATE) =====
def is_new(title, link):
    text = title + link
    h = hashlib.md5(text.encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

# ===== SIMILARITY FILTER =====
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
    title = title.lower()

    if any(x in title for x in ["earnings", "eps", "revenue", "guidance"]):
        return "🟢 Earnings"
    elif any(x in title for x in ["acquisition", "merger", "buyout"]):
        return "🔵 M&A"
    elif any(x in title for x in ["upgrade", "downgrade", "rating", "price target"]):
        return "🟡 Analyst"
    elif any(x in title for x in ["fda", "approval"]):
        return "🟣 Approval"
    else:
        return "🔴 Macro"

# ===== SYMBOL =====
def extract_symbol(title):
    title = title.upper()
    for symbol in WATCHLIST:
        if symbol in title:
            return symbol
    return None

# ===== FINNHUB PRICE =====
async def get_stock_data(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as resp:
        return await resp.json()

# ===== FINNHUB MARKET NEWS =====
async def get_finnhub_market_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    async with session.get(url) as resp:
        data = await resp.json()

    return [
        {"title": item["headline"], "link": item["url"]}
        for item in data[:10]
    ]

# ===== FINNHUB COMPANY NEWS =====
async def get_company_news(session, symbol):
    today = datetime.utcnow().date()
    past = today - timedelta(days=2)

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={past}&to={today}&token={API_KEY}"

    async with session.get(url) as resp:
        data = await resp.json()

    return [
        {"title": item["headline"], "link": item["url"], "symbol": symbol}
        for item in data[:5]
    ]

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
async def send_news(bot, session, news):
    title = news["title"]
    link = news["link"]

    # 🧠 Anti-spam filters
    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    if not any(word in title.lower() for word in IMPORTANT_WORDS):
        return False

    category = categorize_news(title)
    translated = translate_text(title)

    symbol = news.get("symbol") or extract_symbol(title)

    stock_info = ""

    if symbol:
        try:
            data = await get_stock_data(session, symbol)
            price = data.get("c")
            change = data.get("dp")

            stock_info = f"""

📊 {symbol}
💰 Price: {price}$
📈 Change: {change}%
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
    print("🚀 Bot Running (No Spam Mode)...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                news_list = await get_all_news(session)

                news_sent = 0

                for news in news_list:
                    if news_sent >= MAX_NEWS_PER_CYCLE:
                        break

                    sent = await send_news(bot, session, news)

                    if sent:
                        news_sent += 1

                await asyncio.sleep(300)

            except Exception as e:
                print("Main error:", e)
                await asyncio.sleep(60)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())