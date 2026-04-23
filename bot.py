# ===== Alpha Market Radar PRO SEC AI 🚀 =====

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

SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/5.2 (your@email.com)"
}

sent = set()

# ===== ترجمة =====
def tr(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return ""

# ===== استخراج نص من 8-K =====
def read_8k(url):
    try:
        res = requests.get(url, headers=SEC_HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # ناخذ أول نص واضح
        text = soup.get_text(" ", strip=True)

        return text[:1500]  # أول 1500 حرف
    except:
        return ""

# ===== تحليل الحدث =====
def analyze(text):
    t = text.lower()

    if "bankruptcy" in t or "chapter 11" in t:
        return "⚠️ Bankruptcy"
    if "merger" in t or "acquisition" in t:
        return "🤝 Merger / Acquisition"
    if "earnings" in t or "results" in t:
        return "📊 Earnings"
    if "agreement" in t or "deal" in t:
        return "📢 Deal / Agreement"
    if "delist" in t:
        return "🚫 Delisting"

    return "📄 Other Filing"

# ===== استخراج الشركة =====
def get_company(title):
    try:
        return title.split(" - ")[1].split("(")[0].strip()
    except:
        return "Unknown"

# ===== إرسال =====
async def send(msg):
    for cid in CHAT_IDS:
        try:
            await bot.send_message(chat_id=cid, text=msg)
        except:
            pass

# ===== جلب SEC =====
def fetch_sec():
    return feedparser.parse(SEC_RSS, request_headers=SEC_HEADERS).entries[:20]

# ===== تشغيل =====
async def run_cycle():
    print("📡 Running SEC AI...")

    count = 0

    for e in fetch_sec():

        if count >= 15:
            return

        if e.link in sent:
            continue

        if "8-k" not in e.title.lower():
            continue

        sent.add(e.link)

        company = get_company(e.title)

        # 🔥 قراءة الملف
        content = read_8k(e.link)

        # 🔥 تحليل
        event = analyze(content)

        # 🔥 ترجمة
        ar_event = tr(event)
        ar_summary = tr(content[:200])

        msg = f"""🚨 SEC SMART

🏢 {company}
{event}
🇸🇦 {ar_event}

🧠 Summary:
{content[:200]}

🇸🇦 {ar_summary}

🔗 {e.link}
"""

        await send(msg)
        count += 1

# ===== LOOP =====
async def main():
    await send("🚀 SEC AI BOT LIVE\nReads + Understands + Translates 🔥")

    while True:
        try:
            await run_cycle()
            await asyncio.sleep(300)
        except Exception as e:
            print(e)
            await asyncio.sleep(60)

# ===== START =====
if __name__ == "__main__":
    asyncio.run(main())