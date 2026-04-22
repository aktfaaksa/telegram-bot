# ===== Alpha Market Radar BALANCED 🚀 =====

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

# ===== BLOCK (نمنع السبام) =====
BLOCK_KEYWORDS = [
    "price target", "analyst", "opinion",
    "should you buy", "forecast", "outlook",
    "conference call", "transcript",
    "market wrap", "stocks rise", "stocks fall"
]

# ===== NEWS LEVELS =====
STRONG_KEYWORDS = [
    "beats earnings", "misses earnings",
    "acquires", "to acquire", "merger",
    "fda approval", "approved",
    "phase 3 results", "positive results"
]

MEDIUM_KEYWORDS = [
    "reports earnings", "guidance",
    "phase 2", "trial", "study",
    "deal", "partnership",
    "raises", "cuts"
]

# ===== FILTER =====
def is_valid_news(title):
    t = title.lower()

    # ❌ حذف السبام
    if any(x in t for x in BLOCK_KEYWORDS):
        return False

    # ✅ خبر قوي
    if any(x in t for x in STRONG_KEYWORDS):
        return True

    # ✅ خبر متوسط
    if any(x in t for x in MEDIUM_KEYWORDS):
        return True

    return False

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
    if match:
        return match[0]
    return None

def extract_sec_symbol(title):
    match = re.findall(r'\((.*?)\)', title)
    if match:
        return match[0]
    return None

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
    print("📡 Running balanced mode...")

    total_sent = 0

    # ===== SEC =====
    for e in fetch_sec():

        if total_sent >= MAX_NEWS:
            return

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
📄 {title}
"""

        await send_msg(msg)
        total_sent += 1

    # ===== RSS =====
    for e in await fetch_rss():

        if total_sent >= MAX_NEWS:
            return

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
📢 {title}"""

        if translated:
            msg += f"\n🇸🇦 {translated}"

        await send_msg(msg)
        total_sent += 1

    if total_sent == 0:
        print("No valid news this cycle")

# ===== LOOP =====
async def main():
    print("🚀 Alpha Market Radar BALANCED")

    await send_msg("🚀 البوت شغال (Balanced Mode)\nSEC + RSS\nNo Spam + More Opportunities 📊")

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