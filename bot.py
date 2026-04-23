# ===== Alpha Market Radar SMART 🚀 =====

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
SEC_HEADERS = {"User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com)"}

# ===== MEMORY =====
sent = set()

# ===== BLOCK =====
BLOCK = [
    "price target", "analyst", "rating", "upgrade", "downgrade",
    "opinion", "forecast", "outlook", "should you buy",
    "conference call", "transcript"
]

PRE_BLOCK = [
    "ahead of", "expected", "anticipation", "upcoming"
]

# ===== SMART KEYWORDS =====
KEYWORDS = [
    # Earnings
    "earnings", "quarterly", "results", "revenue",

    # Deals
    "acquires", "acquisition", "merger",
    "deal", "agreement", "partnership",

    # Pharma
    "phase", "trial", "clinical", "fda", "approval",

    # Market reaction
    "surges", "jumps", "soars", "growth"
]

# ===== DATE FILTER =====
def is_today(entry):
    try:
        t = entry.published_parsed
        news_time = datetime(*t[:6], tzinfo=timezone.utc)
        return news_time.date() == datetime.now(timezone.utc).date()
    except:
        return False

# ===== SMART FILTER =====
def is_valid(title):
    t = title.lower()

    if any(x in t for x in BLOCK):
        return False

    if any(x in t for x in PRE_BLOCK):
        return False

    score = sum(1 for k in KEYWORDS if k in t)

    return score >= 2  # 🔥 السر هنا

# ===== CLASSIFY =====
def classify(title):
    t = title.lower()

    if any(x in t for x in ["beats", "surges", "growth", "positive"]):
        return "🚀 إيجابي"

    if any(x in t for x in ["misses", "drops", "lawsuit"]):
        return "⚠️ سلبي"

    return "📊 عادي"

# ===== IMPACT =====
def impact(title):
    t = title.lower()

    if "phase 3" in t or "acquisition" in t:
        return "🔥🔥🔥 عالي"

    if "earnings" in t or "approval" in t:
        return "🔥🔥 قوي"

    return "🔥 متوسط"

# ===== TRANSLATE =====
def tr(text):
    if not USE_TRANSLATION:
        return ""
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return ""

# ===== SYMBOL =====
def symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== SEND =====
async def send(msg):
    for cid in CHAT_IDS:
        try:
            await bot.send_message(chat_id=cid, text=msg)
        except:
            pass

# ===== FETCH =====
async def fetch_rss():
    all_entries = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        all_entries.extend(feed.entries)
    return all_entries

def fetch_sec():
    return feedparser.parse(SEC_RSS, request_headers=SEC_HEADERS).entries[:20]

# ===== MAIN =====
async def run_cycle():
    print("📡 Running SMART...")

    count = 0

    # ===== SEC (8-K ONLY) =====
    for e in fetch_sec():

        if count >= MAX_NEWS:
            return

        if not is_today(e):
            continue

        if "8-k" not in e.title.lower():
            continue

        if e.link in sent:
            continue

        sent.add(e.link)

        msg = f"""🚨 SEC 8-K

📄 {e.title}
"""

        await send(msg)
        count += 1

    # ===== RSS =====
    for e in await fetch_rss():

        if count >= MAX_NEWS:
            return

        if not is_today(e):
            continue

        if e.link in sent:
            continue

        title = e.title

        if not is_valid(title):
            continue

        sym = symbol(title)
        if not sym:
            continue

        sent.add(e.link)

        msg = f"""📰 NEWS

🏷️ {sym}
{classify(title)}
{impact(title)}
📢 {title}"""

        ar = tr(title)
        if ar:
            msg += f"\n🇸🇦 {ar}"

        await send(msg)
        count += 1

    if count == 0:
        print("No smart news")

# ===== LOOP =====
async def main():
    print("🚀 SMART BOT STARTED")

    await send("🚀 SMART BOT LIVE\nReal Opportunities Only 🔥")

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