# AlphaBot Pro v4.0 AI TRADING SYSTEM

import os
import time
import requests
import feedparser
import hashlib
import re
from datetime import datetime, timezone

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

MAIN_CHAT_ID = int(os.getenv("CHAT_ID"))
SECOND_CHAT_ID = 6315087880

CHAT_IDS = [MAIN_CHAT_ID, SECOND_CHAT_ID]

CYCLE_TIME = 300
MAX_NEWS = 10

# ===== مصادر =====
RSS_FEEDS = [
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

# ===== فلترة =====
BLOCK = ["crypto","coin","token","prediction","video","trailer","opinion"]
MACRO = ["oil","dollar","gold","bond","iran","war","inflation","rates","fed"]
IMPORTANT = ["earnings","revenue","profit","merger","acquisition","guidance","shares","stock","drop","plunge","surge","jump"]

seen = set()

# ===== Utils =====
def is_new(title):
    h = hashlib.md5(title.lower().encode()).hexdigest()
    if h in seen:
        return False
    seen.add(h)
    return True

def is_recent(published, hours=3):
    if not published:
        return True
    t = datetime(*published[:6], tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() <= hours * 3600

# ===== Telegram =====
def send(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": msg}
            )
        except:
            pass

# ===== AI =====
def ai(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""

# ===== استخراج ticker =====
def get_stock(title):
    prompt = f"""
Extract stock ticker and company from news.
Return JSON:
{{"ticker":"...", "company":"..."}}

{title}
"""
    try:
        res = ai(prompt)
        data = eval(res)
        return data.get("ticker"), data.get("company")
    except:
        return None, None

# ===== تحليل =====
def analyze(title):
    prompt = f"""
حلل الخبر:

- ملخص عربي
- قرار: شراء / بيع / محايد
- سبب القرار
- قوة الخبر من 1 إلى 10

{title}
"""
    return ai(prompt)

def extract_score(text):
    m = re.search(r'(\d+)', text)
    if m:
        return min(int(m.group(1)), 10)
    return 5

def get_signal(text):
    if "شراء" in text:
        return "🟢 BUY"
    elif "بيع" in text:
        return "🔴 SELL"
    return "⚪ NEUTRAL"

# ===== السعر =====
def get_price(ticker):
    if not ticker:
        return None
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        return requests.get(url).json().get("c")
    except:
        return None

# ===== جلب =====
def fetch():
    data = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            data.append({
                "title": e.title,
                "link": e.link,
                "published": e.get("published_parsed")
            })
    return data

# ===== تشغيل =====
def run():
    send("🚀 AlphaBot v4.0 AI Started")

    while True:
        news = fetch()
        count = 0

        for n in news:
            title = n["title"].lower()

            if any(w in title for w in BLOCK):
                continue

            if not any(w in title for w in IMPORTANT):
                continue

            if not is_new(n["title"]):
                continue

            if not is_recent(n["published"]):
                continue

            # 🚫 Macro بدون إشارات
            is_macro = any(w in title for w in MACRO)

            ticker, company = get_stock(n["title"])

            analysis = analyze(n["title"])
            score = extract_score(analysis)
            signal = get_signal(analysis)

            price = get_price(ticker)

            if is_macro:
                signal = "🌍 MACRO"

            msg = f"""
📊 Alpha Signal

🏢 {company or "Unknown"}
💲 {ticker or "N/A"}
💰 {price if price else "N/A"}

📢 {signal}
⭐ Strength: {score}/10

{analysis}

🔗 {n['link']}
"""

            send(msg)

            count += 1
            if count >= MAX_NEWS:
                break

        time.sleep(CYCLE_TIME)

# ===== Start =====
if __name__ == "__main__":
    run()