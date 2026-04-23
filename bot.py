# AlphaBot Pro v3.6.0 SMART TRADING FEED

import os
import time
import requests
import feedparser
import hashlib
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MAIN_CHAT_ID = int(os.getenv("CHAT_ID"))
SECOND_CHAT_ID = 6315087880

CHAT_IDS = [MAIN_CHAT_ID, SECOND_CHAT_ID]

CYCLE_TIME = 300
MAX_NEWS = 15

RSS_FEEDS = [
    "https://www.benzinga.com/feed",
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/3.6 (Financial Bot; aktfaaksa@gmail.com)"
}

SEC_KEYWORDS = [
    "bankruptcy","merger","acquisition","earnings",
    "results","agreement","deal","delist"
]

BLOCK_KEYWORDS = [
    "price prediction","crypto","coin","token",
    "forecast","video","trailer","watch",
    "cramer","opinion"
]

MACRO_BLOCK = [
    "bond","macro","economy","global","fund","loan","pension"
]

IMPORTANT_KEYWORDS = [
    "earnings","revenue","profit","merger",
    "acquisition","bankruptcy","guidance",
    "results","deal","shares","stock","drop","plunge","surge"
]

seen = set()

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

def send_message(text):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
        except:
            pass

def translate(text):
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"ترجم الخبر للعربية باختصار:\n{text}"
                }]
            }
        )
        return res.json()["choices"][0]["message"]["content"]
    except:
        return ""

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

def run():
    send_message("🚀 AlphaBot v3.6 Started")

    while True:
        news = fetch_news() + fetch_sec()
        count = 0

        for n in news:

            title = n["title"].lower()

            if "video" in n["link"]:
                continue

            if any(word in title for word in BLOCK_KEYWORDS):
                continue

            if any(word in title for word in MACRO_BLOCK):
                continue

            if n["source"] != "SEC":
                if not any(word in title for word in IMPORTANT_KEYWORDS):
                    continue

            if not is_new(n["title"]):
                continue

            if not is_recent(n["published"], 3):
                continue

            # 🔥 تصنيف ذكي
            if "plunge" in title or "drop" in title:
                tag = "🔻 SELL SIGNAL"
            elif "surge" in title or "jump" in title:
                tag = "🚀 BUY SIGNAL"
            elif "earnings" in title:
                tag = "🔥 Earnings"
            elif "merger" in title or "acquisition" in title:
                tag = "🚨 Deal"
            elif n["source"] == "SEC":
                tag = "🏛 SEC"
            else:
                tag = "📰 News"

            translated = translate(n["title"])

            msg = f"""
{tag}

📰 {n['title']}
🌍 {translated}

🔗 {n['link']}
"""

            send_message(msg)

            if n["source"] != "SEC":
                count += 1

            if count >= MAX_NEWS:
                break

        time.sleep(CYCLE_TIME)

if __name__ == "__main__":
    run()