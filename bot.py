# ===== Alpha Market Radar TRADING MODE 🚀 =====

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

# ===== SOURCES =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reuters.com/markets/us/rss"
]

SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"
SEC_HEADERS = {"User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com)"}

# ===== MEMORY =====
sent = set()

# ===== BLOCK =====
BLOCK = [
    "price target", "analyst", "upgrade", "downgrade",
    "opinion", "should you buy",
    "conference call", "transcript"
]

GLOBAL_BLOCK = [
    "war", "conflict", "election", "president",
    "government", "icc"
]

# ===== IMPORTANT EVENTS =====
KEYWORDS = [
    # Earnings
    "earnings", "results", "revenue", "profit", "guidance",

    # M&A
    "acquires", "acquisition", "merger", "deal",

    # Risk events
    "bankruptcy", "chapter 11", "liquidation",
    "delisting", "delist", "warning",

    # Corporate actions
    "split", "stock split", "reverse split",
    "dividend",

    # Pharma
    "fda", "approval", "trial", "phase",

    # Big moves
    "surges", "plunges", "jumps", "drops"
]

# ===== DATE =====
def is_today(entry):
    try:
        t = entry.published_parsed
        dt = datetime(*t[:6], tzinfo=timezone.utc)
        return dt.date() == datetime.now(timezone.utc).date()
    except:
        return False

# ===== SYMBOL =====
def get_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== COMPANY CHECK =====
def has_company(title):
    return bool(get_symbol(title))

# ===== FILTER =====
def is_valid(title):
    t = title.lower()

    if any(x in t for x in BLOCK):
        return False

    if any(x in t for x in GLOBAL_BLOCK):
        return False

    if not has_company(title):
        return False

    return any(k in t for k in KEYWORDS)

# ===== CLASSIFY =====
def classify(title):
    t = title.lower()

    if any(x in t for x in ["surges", "beats", "growth", "profit"]):
        return "🚀 إيجابي"

    if any(x in t for x in ["plunges", "bankruptcy", "drops", "warning"]):
        return "⚠️ سلبي"

    return "📊 عادي"

# ===== IMPACT =====
def impact(title):
    t = title.lower()

    if any(x in t for x in ["bankruptcy", "chapter 11", "merger"]):
        return "🔥🔥🔥 عالي"

    if any(x in t for x in ["earnings", "approval"]):
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

# ===== SEND =====
async def send(msg):
    for cid in CHAT_IDS:
        try:
            await bot.send_message(chat_id=cid, text=msg)
        except:
            pass

# ===== FETCH =====
async def fetch_rss():
    data = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        data.extend(feed.entries)
    return data

def fetch_sec():
    return feedparser.parse(SEC_RSS, request_headers=SEC_HEADERS).entries[:20]

# ===== MAIN =====
async def run_cycle():
    print("📡 Running TRADING MODE...")

    count = 0

    # ===== SEC (8-K فقط) =====
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

        await send(f"""🚨 SEC 8-K

📄 {e.title}
""")

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

        sym = get_symbol(title)
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
        print("No trading news")

# ===== LOOP =====
async def main():
    await send("🚀 TRADING BOT LIVE\nEvery 5 min • Max 15 News 🎯")

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