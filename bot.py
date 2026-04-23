# ===== Alpha Market Radar FINAL PRO ULTRA 🚀 =====

import asyncio
import feedparser
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

# ===== SETTINGS =====
MAX_NEWS = 15

# ===== SOURCES =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reuters.com/markets/us/rss"
]

SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com) Python Requests"
}

sent = set()

# ===== TRANSLATION =====
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

# ===== SEC HELPERS =====
def get_company(title):
    try:
        return title.split(" - ")[1].split("(")[0].strip()
    except:
        return "Unknown"

# ===== 🔥 SEC FIX النهائي =====
def read_8k(url):
    try:
        res = requests.get(url, headers=SEC_HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")

            if len(cols) >= 4:
                doc_name = cols[1].text.strip().lower()
                doc_type = cols[3].text.strip().lower()

                # 🔥 نختار فقط التقرير الحقيقي
                if "8-k" in doc_type and not any(x in doc_name for x in ["xml", "xbrl"]):
                    link = cols[2].find("a")

                    if link:
                        href = link.get("href")
                        real_url = "https://www.sec.gov" + href

                        res2 = requests.get(real_url, headers=SEC_HEADERS, timeout=10)
                        soup2 = BeautifulSoup(res2.text, "html.parser")

                        text = soup2.get_text(" ", strip=True)

                        # تنظيف النص
                        text = text.replace("XBRL Viewer", "")
                        text = text.replace("Please enable JavaScript", "")

                        return text[:2000]

        return ""

    except Exception as e:
        print("SEC read error:", e)
        return ""

# ===== ANALYSIS =====
def analyze(text):
    t = text.lower()

    if "bankruptcy" in t or "chapter 11" in t:
        return "⚠️ Bankruptcy"
    if "merger" in t or "acquisition" in t:
        return "🤝 Merger / Acquisition"
    if "earnings" in t or "results" in t:
        return "📊 Earnings"
    if "agreement" in t or "deal" in t:
        return "📢 Deal"
    if "delist" in t:
        return "🚫 Delisting"

    return "📄 Other"

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
    print("📡 Running FINAL PRO ULTRA...")

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

        content = read_8k(e.link)
        event = analyze(content)

        msg = f"""🚨 SEC SMART

🏢 {company}
{event}

🧠 Summary:
{content[:200]}

🇸🇦 {tr(content[:200])}

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
{classify(title)}
{impact(title)}
📢 {title}

🇸🇦 {tr(title)}
"""

        await send(msg)
        count += 1

    if count == 0:
        print("No news")

# ===== LOOP =====
async def main():
    await send("🚀 FINAL PRO ULTRA BOT LIVE\nSEC Fully Fixed + Real Parsing 🔥")

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