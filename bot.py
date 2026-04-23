# ===== Alpha Market Radar STABLE PRO 🚀 =====

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

MAX_NEWS = 15

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reuters.com/markets/us/rss"
]

SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com)"
}

sent = set()

# ===== ترجمة =====
def tr(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return ""

# ===== DATE =====
def is_today(entry):
    try:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if not t:
            return True
        dt = datetime(*t[:6], tzinfo=timezone.utc)
        return dt.date() == datetime.now(timezone.utc).date()
    except:
        return True

# ===== SYMBOL =====
def get_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== SEC ANALYSIS (ذكي) =====
def analyze_sec(title):
    t = title.lower()

    if "bankruptcy" in t:
        return "⚠️ إفلاس"
    if "merger" in t or "acquisition" in t:
        return "🤝 اندماج"
    if "earnings" in t:
        return "📊 نتائج"
    if "agreement" in t:
        return "📢 اتفاقية"

    return "📄 إفصاح"

# ===== استخراج الشركة =====
def get_company(title):
    try:
        return title.split(" - ")[1].split("(")[0].strip()
    except:
        return "Unknown"

# ===== RSS FILTER =====
def is_valid(title):
    t = title.lower()

    if any(x in t for x in [
        "analyst", "price target", "upgrade", "downgrade",
        "opinion", "strategist",
        "war", "iran", "israel", "gaza",
        "election", "president"
    ]):
        return False

    if not any(k in t for k in [
        "earnings", "revenue", "profit",
        "acquire", "merger", "deal",
        "bankruptcy", "split", "dividend",
        "fda", "approval"
    ]):
        return False

    return True

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
    print("📡 Running STABLE PRO...")

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

        company = get_company(e.title)
        event = analyze_sec(e.title)

        msg = f"""🚨 SEC

🏢 {company}
{event}

📄 {e.title}
🇸🇦 {tr(e.title)}

🔗 {e.link}
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
📢 {title}
🇸🇦 {tr(title)}
"""

        await send(msg)
        count += 1

# ===== LOOP =====
async def main():
    await send("🚀 STABLE PRO BOT LIVE\nClean + SEC Reliable 🎯")

    while True:
        try:
            await run_cycle()
            await asyncio.sleep(300)
        except:
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())