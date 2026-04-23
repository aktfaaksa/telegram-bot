# ===== Alpha Market Radar PRO FINAL 🚀 =====

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
SEC_HEADERS = {
    "User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com)"
}

# ===== MEMORY =====
sent = set()

# ===== DATE FIX (🔥 مهم) =====
def is_recent(entry):
    try:
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        if not t:
            return True

        news_time = datetime(*t[:6], tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        diff = (now - news_time).total_seconds() / 60
        return diff <= 180  # آخر 3 ساعات
    except:
        return True

# ===== SYMBOL =====
def get_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== CLASSIFY =====
def classify(title):
    t = title.lower()

    if any(x in t for x in ["beat", "growth", "profit", "surge"]):
        return "🚀 إيجابي"

    if any(x in t for x in ["miss", "drop", "bankruptcy", "warning"]):
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

# ===== FILTER =====
def is_valid(title):
    t = title.lower()

    if any(x in t for x in [
        "price target", "analyst", "upgrade", "downgrade",
        "opinion", "should you buy"
    ]):
        return False

    if not any(k in t for k in [
        "earnings", "revenue", "profit",
        "acquire", "merger", "deal",
        "bankruptcy", "split", "dividend",
        "trial", "fda", "approval",
        "guidance", "results"
    ]):
        return False

    return True

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

def extract_company(title):
    parts = title.split(" - ")
    return parts[0] if parts else "Unknown"

def guess_symbol(company):
    words = company.split()
    if words:
        sym = words[0].upper()
        if len(sym) <= 5:
            return sym
    return "N/A"

# ===== تحليل 8-K بسيط 🔥 =====
def analyze_8k(title):
    t = title.lower()

    if "bankruptcy" in t:
        return "⚠️ إفلاس محتمل"
    if "merger" in t or "acquisition" in t:
        return "🤝 اندماج / استحواذ"
    if "earnings" in t:
        return "📊 نتائج مالية"
    if "delist" in t:
        return "🚫 شطب محتمل"

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
    data = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        data.extend(feed.entries)
    return data

# ===== MAIN =====
async def run_cycle():
    print("📡 Running PRO FINAL...")

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

        company = extract_company(e.title)
        symbol = guess_symbol(company)

        msg = f"""🚨 SEC 8-K

🏷️ {symbol}
🏢 {company}
{analyze_8k(e.title)}

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

        if not is_recent(e):
            continue

        title = e.title

        if not is_valid(title):
            continue

        sym = get_symbol(title) or "N/A"

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
        print("⚠️ No news this cycle")

# ===== LOOP =====
async def main():
    await send("🚀 PRO BOT LIVE\nSEC + RSS + Smart Analysis 🔥")

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