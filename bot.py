# ===== Alpha Market Radar REAL-TIME 🚀 =====

import asyncio
import feedparser
import os
import re
from datetime import datetime, timezone
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

# ===== BLOCK SPAM =====
BLOCK_KEYWORDS = [
    "price target", "raises target", "cuts target",
    "analyst", "rating", "upgrade", "downgrade",
    "should you buy", "opinion",
    "conference call", "transcript",
    "market wrap", "stocks rise", "stocks fall",
    "forecast", "outlook", "expects"
]

# ===== PRE-EVENT BLOCK =====
PRE_EVENT_BLOCK = [
    "ahead of", "before", "anticipation",
    "expected", "set to", "upcoming"
]

# ===== EVENTS =====
STRONG_KEYWORDS = [
    "beats earnings", "misses earnings", "reports earnings",
    "acquires", "to acquire", "merger",
    "fda approval", "approved",
    "phase 3 results", "positive results",
    "successful trial"
]

MEDIUM_KEYWORDS = [
    "phase 2", "trial", "study",
    "deal", "partnership", "guidance"
]

# ===== DATE FILTER =====
def is_today(entry):
    try:
        published = entry.published_parsed
        news_time = datetime(*published[:6], tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return news_time.date() == now.date()
    except:
        return False

# ===== FILTER =====
def is_valid_news(title):
    t = title.lower()

    if any(x in t for x in PRE_EVENT_BLOCK):
        return False

    if any(x in t for x in BLOCK_KEYWORDS):
        return False

    if any(x in t for x in STRONG_KEYWORDS):
        return True

    if any(x in t for x in MEDIUM_KEYWORDS):
        return True

    return False

# ===== IMPACT =====
def get_impact(title):
    t = title.lower()

    if "phase 3" in t or "acquires" in t or "merger" in t:
        return "🔥🔥🔥 عالي"

    if "beats" in t or "approval" in t:
        return "🔥🔥 قوي"

    return "🔥 متوسط"

# ===== CLASSIFY =====
def classify_news(title):
    t = title.lower()

    if any(x in t for x in ["beats", "positive", "acquires", "approval"]):
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
    return match[0] if match else None

def extract_sec_symbol(title):
    match = re.findall(r'\((.*?)\)', title)
    return match[0] if match else None

# ===== SEND =====
async def send_msg(text):
    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except:
            pass

# ===== FETCH =====
async def fetch_rss():
    entries = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        entries.extend(feed.entries)
    return entries

def fetch_sec():
    feed = feedparser.parse(SEC_RSS, request_headers=SEC_HEADERS)
    return feed.entries[:20]

# ===== MAIN =====
async def run_cycle():
    print("📡 Running REAL-TIME mode...")

    total_sent = 0

    # ===== SEC =====
    for e in fetch_sec():

        if total_sent >= MAX_NEWS:
            return

        if not is_today(e):
            continue

        key = e.link
        if key in sent:
            continue

        title = e.title

        if not is_valid_news(title):
            continue

        symbol = extract_sec_symbol(title)
        if not symbol:
            continue

        sent.add(key)

        msg = f"""🚨 SEC

🏷️ {symbol}
{classify_news(title)}
{get_impact(title)}
📄 {title}
"""

        await send_msg(msg)
        total_sent += 1

    # ===== RSS =====
    for e in await fetch_rss():

        if total_sent >= MAX_NEWS:
            return

        if not is_today(e):
            continue

        key = e.link
        if key in sent:
            continue

        title = e.title

        if not is_valid_news(title):
            continue

        symbol = extract_symbol(title)
        if not symbol:
            continue

        sent.add(key)

        translated = tr(title)

        msg = f"""📰 NEWS

🏷️ {symbol}
{classify_news(title)}
{get_impact(title)}
📢 {title}"""

        if translated:
            msg += f"\n🇸🇦 {translated}"

        await send_msg(msg)
        total_sent += 1

    if total_sent == 0:
        print("No real-time news")

# ===== LOOP =====
async def main():
    print("🚀 Alpha Market Radar REAL-TIME")

    await send_msg("🚀 البوت شغال (REAL-TIME)\nOnly Today News ⚡")

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