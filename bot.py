# AlphaBot Pro v3.3.2 MULTI USERS + SEC

import os
import time
import requests
import feedparser
import hashlib
from datetime import datetime, timezone

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🟢 رقمك من Railway
MAIN_CHAT_ID = int(os.getenv("CHAT_ID"))

# 🔵 الشخص الثاني (حط رقمه هنا)
SECOND_CHAT_ID = 6315087880

# 📢 كل المستقبلين
CHAT_IDS = [MAIN_CHAT_ID, SECOND_CHAT_ID]

# ===== إعدادات =====
CYCLE_TIME = 300
MAX_NEWS = 10

# ===== مصادر =====
RSS_FEEDS = [
    "https://www.benzinga.com/feed",
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

# ===== SEC =====
SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/3.3.2 (Financial Bot; aktfaaksa@gmail.com)"
}

SEC_KEYWORDS = [
    "bankruptcy","merger","acquisition","earnings",
    "results","agreement","deal","delist"
]

# ===== منع التكرار =====
seen = set()

def is_new(title):
    h = hashlib.md5(title.lower().encode()).hexdigest()
    if h in seen:
        return False
    seen.add(h)
    return True

# ===== الوقت =====
def is_recent(published, hours=3):
    if not published:
        return True
    t = datetime(*published[:6], tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() <= hours * 3600

# ===== إرسال =====
def send_message(text):
    for chat_id in CHAT_IDS:
        try:
            res = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
            print(f"SEND TO {chat_id}:", res.status_code)
        except Exception as e:
            print("ERROR:", e)

# ===== RSS =====
def fetch_news():
    data = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            data.append({
                "title": e.title,
                "link": e.link,
                "published": e.get("published_parsed"),
                "source": "NEWS"
            })
    return data

# ===== SEC =====
def fetch_sec():
    try:
        res = requests.get(SEC_RSS, headers=SEC_HEADERS)
        feed = feedparser.parse(res.text)

        data = []
        for e in feed.entries:
            title = e.title.lower()

            if not any(k in title for k in SEC_KEYWORDS):
                continue

            data.append({
                "title": e.title,
                "link": e.link,
                "published": e.get("published_parsed"),
                "source": "SEC"
            })

        return data
    except:
        return []

# ===== تشغيل =====
def run():
    send_message("🚀 AlphaBot v3.3.2 Started (Multi Users)")

    while True:
        news = fetch_news() + fetch_sec()
        count = 0

        for n in news:

            if not is_new(n["title"]):
                continue

            if not is_recent(n["published"], 3):
                continue

            tag = "🏛 SEC" if n["source"] == "SEC" else "📰 News"

            msg = f"""
{tag}

📰 {n['title']}

🔗 {n['link']}
"""

            send_message(msg)

            if n["source"] != "SEC":
                count += 1

            if count >= MAX_NEWS:
                break

        time.sleep(CYCLE_TIME)

# ===== Start =====
if __name__ == "__main__":
    run()