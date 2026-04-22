# ===== Alpha Market Radar (SEC + RSS) 🚀 =====

import asyncio
import aiohttp
import feedparser
import os
import re
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=BOT_TOKEN)

# ===== RSS SOURCES =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reuters.com/markets/us/rss"
]

# ===== SEC =====
SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com)"
}

# ===== LIMIT =====
MAX_NEWS = 15

# ===== MEMORY =====
sent = set()

# ===== STRONG NEWS FILTER =====
STRONG_KEYWORDS = [
    "earnings", "reports", "beats", "misses",
    "merger", "acquisition", "acquires",
    "deal", "partnership",
    "approval", "fda",
    "guidance", "raises", "cuts",
    "trial", "phase 1", "phase 2", "phase 3",
    "clinical", "study", "results",
    "successful", "positive results"
]

# ===== FILTER =====
def is_strong_news(title):
    t = title.lower()

    if not any(word in t for word in STRONG_KEYWORDS):
        return False

    if any(x in t for x in ["transcript", "conference call", "preview"]):
        return False

    return True

# ===== CLASSIFY =====
def classify_news(title):
    t = title.lower()

    if any(x in t for x in ["beats", "surges", "rises", "gains", "acquires", "deal", "approval", "positive"]):
        return "🚀 إيجابي"

    if any(x in t for x in ["misses", "falls", "drops", "cuts", "lawsuit", "investigation"]):
        return "⚠️ سلبي"

    return "📊 عادي"

# ===== TRANSLATION =====
def tr(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== SYMBOL EXTRACTION =====
def extract_symbol(text):
    match = re.findall(r'\(([A-Z]{1,5})\)', text)
    if match:
        return match[0]
    return "N/A"

def extract_sec_symbol(title):
    match = re.findall(r'\((.*?)\)', title)
    if match:
        return match[0]
    return "SEC"

# ===== SEND =====
async def send_msg(text):
    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except:
            pass

# ===== FETCH RSS =====
async def fetch_rss():
    entries = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        entries.extend(feed.entries)

    return entries

# ===== FETCH SEC =====
def fetch_sec():
    feed = feedparser.parse(SEC_RSS)
    return feed.entries[:20]

# ===== MAIN =====
async def run_cycle():
    print("📡 Running...")

    total_sent = 0

    # ===== SEC FIRST =====
    sec_entries = fetch_sec()

    for e in sec_entries:
        if total_sent >= MAX_NEWS:
            return

        key = e.link
        if key in sent:
            continue

        title = e.title

        if not is_strong_news(title):
            continue

        sent.add(key)

        symbol = extract_sec_symbol(title)
        news_type = classify_news(title)

        msg = f"""🚨 SEC

🏷️ {symbol}
{news_type}
📄 {title}
"""

        await send_msg(msg)
        total_sent += 1

    # ===== RSS =====
    rss_entries = await fetch_rss()

    for e in rss_entries:
        if total_sent >= MAX_NEWS:
            return

        key = e.link
        if key in sent:
            continue

        title = e.title

        if not is_strong_news(title):
            continue

        sent.add(key)

        symbol = extract_symbol(title)
        news_type = classify_news(title)
        translated = tr(title)

        msg = f"""📰 NEWS

🏷️ {symbol}
{news_type}
📢 {title}
🇸🇦 {translated}
"""

        await send_msg(msg)
        total_sent += 1

# ===== LOOP =====
async def main():
    print("🚀 Alpha Market Radar Started")

    await send_msg("✅ Bot Started - Strong News Only")

    while True:
        try:
            await run_cycle()
            await asyncio.sleep(300)  # 5 دقائق
        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(60)

# ===== START =====
if __name__ == "__main__":
    asyncio.run(main())