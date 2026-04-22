# ===== Alpha Market Radar FINAL 🚀 =====

import asyncio
import feedparser
import os
import re
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=BOT_TOKEN)

# ===== SETTINGS =====
MAX_NEWS = 15
USE_TRANSLATION = True

# ===== RSS =====
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

# ===== MEMORY =====
sent = set()

# ===== BLOCK (REMOVE SPAM) =====
BLOCK_KEYWORDS = [
    "price target", "raises target", "cuts target",
    "analyst", "should you buy", "opinion",
    "earnings call", "conference call",
    "transcript", "preview",
    "market wrap", "stocks rise", "stocks fall"
]

# ===== STRONG NEWS =====
STRONG_KEYWORDS = [
    "reports earnings", "beats earnings", "misses earnings",
    "merger", "acquisition", "acquires",
    "announces deal", "partnership",
    "fda approval", "approved",
    "phase 2 results", "phase 3 results",
    "positive results", "successful trial"
]

# ===== FILTER =====
def is_strong_news(title):
    t = title.lower()

    if any(x in t for x in BLOCK_KEYWORDS):
        return False

    if any(word in t for word in STRONG_KEYWORDS):
        return True

    return False

# ===== CLASSIFY =====
def classify_news(title):
    t = title.lower()

    if any(x in t for x in ["beats", "positive", "acquires", "approval", "surges"]):
        return "🚀 إيجابي"

    if any(x in t for x in ["misses", "drops", "cuts", "lawsuit"]):
        return "⚠️ سلبي"

    return "📊 عادي"

# ===== TRANSLATION =====
def tr(text):
    if not USE_TRANSLATION:
        return ""

    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return ""

# ===== SYMBOL =====
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
    feed = feedparser.parse(SEC_RSS, request_headers=SEC_HEADERS)
    return feed.entries[:20]

# ===== MAIN =====
async def run_cycle():
    print("📡 Running...")

    total_sent = 0

    # ===== SEC =====
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
📢 {title}"""

        if translated:
            msg += f"\n🇸🇦 {translated}"

        await send_msg(msg)
        total_sent += 1

# ===== LOOP =====
async def main():
    print("🚀 Alpha Market Radar FINAL")

    await send_msg("🚀 البوت شغال\nSEC + RSS\nStrong News Only 🎯")

    while True:
        try:
            await run_cycle()
            await asyncio.sleep(300)
        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(60)

# ===== START =====
if __name__ == "__main__":
    asyncio.run(main())