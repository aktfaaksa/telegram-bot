# ===== Alpha Market Radar FINAL STABLE 🚀 =====

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

sent = set()

# ===== DATE (اليوم فقط) =====
def is_today(entry):
    try:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if not t:
            return False
        dt = datetime(*t[:6], tzinfo=timezone.utc)
        return dt.date() == datetime.now(timezone.utc).date()
    except:
        return False

# ===== SYMBOL =====
def get_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== FILTER =====
def is_valid(title):
    t = title.lower()

    # منع التحليل والسياسة
    if any(x in t for x in [
        "analyst", "price target", "upgrade", "downgrade",
        "opinion", "strategist", "government",
        "war", "iran", "israel", "gaza",
        "election", "president"
    ]):
        return False

    # لازم حدث مالي
    if not any(k in t for k in [
        "earnings", "revenue", "profit",
        "acquire", "merger", "deal",
        "bankruptcy", "chapter 11",
        "split", "dividend",
        "fda", "approval",
        "guidance", "results"
    ]):
        return False

    return True

# ===== CLASSIFY =====
def classify(title):
    t = title.lower()
    if any(x in t for x in ["beat", "growth", "profit"]):
        return "🚀 إيجابي"
    if any(x in t for x in ["drop", "bankruptcy", "warning"]):
        return "⚠️ سلبي"
    return "📊 عادي"

# ===== IMPACT =====
def impact(title):
    t = title.lower()
    if any(x in t for x in ["bankruptcy", "merger"]):
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

# ===== SEC HELPERS =====
def fetch_sec():
    return feedparser.parse(SEC_RSS, request_headers=SEC_HEADERS).entries[:30]

def parse_company(title):
    # مثال: 8-K - COMPANY NAME (000xxxx)
    try:
        return title.split(" - ")[1].split("(")[0].strip()
    except:
        return "Unknown"

def analyze_8k(title):
    t = title.lower()

    if "bankruptcy" in t:
        return "⚠️ إفلاس"
    if "merger" in t or "acquisition" in t:
        return "🤝 اندماج"
    if "earnings" in t:
        return "📊 نتائج مالية"
    if "delist" in t:
        return "🚫 شطب"

    return "📄 حدث مهم"

# ===== SEND =====
async def send(msg):
    for cid in CHAT_IDS:
        try:
            await bot.send_message(chat_id=cid, text=msg)
        except:
            pass

# ===== FETCH RSS =====
async def fetch_rss():
    all_entries = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        all_entries.extend(feed.entries)
    return all_entries

# ===== MAIN =====
async def run_cycle():
    print("📡 Running FINAL STABLE...")

    count = 0

    # ===== SEC =====
    for e in fetch_sec():

        if count >= MAX_NEWS:
            return

        if e.link in sent:
            continue

        if "8-k" not in e.title.lower():
            continue

        sent.add(e.link)

        company = parse_company(e.title)
        event = analyze_8k(e.title)

        msg = f"""🚨 SEC

🏢 {company}
{event}

📄 {e.title}
"""

        await send(msg)
        count += 1

    # ===== RSS =====
    for e in await fetch_rss():

        if count >= MAX_NEWS:
            return

        if e.link in sent:
            continue

        if not is_today(e):
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
        print("No valid news")

# ===== LOOP =====
async def main():
    await send("🚀 BOT LIVE (FINAL STABLE)\nClean + SEC Smart + Real-Time 🔥")

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