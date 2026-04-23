# AlphaBot Pro v3.2.2 DEBUG SEND FIX

import os
import time
import requests
import feedparser

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = 6315087880  # تأكد هذا رقمك الصح

RSS_FEEDS = [
    "https://www.benzinga.com/feed",
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss"
]

# ===== إرسال =====
def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        res = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text
        })

        print("STATUS:", res.status_code)
        print("RESPONSE:", res.text)

    except Exception as e:
        print("SEND ERROR:", e)

# ===== تشغيل =====
def startup():
    send_message("🔥 TEST START - AlphaBot")

# ===== جلب الأخبار =====
def fetch_news():
    all_news = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            all_news.append(entry.title)

    return all_news

# ===== تشغيل رئيسي =====
def run():
    while True:
        news = fetch_news()

        print("TOTAL NEWS:", len(news))

        # إرسال أول 5 أخبار فقط
        for i, title in enumerate(news[:5]):
            msg = f"📰 TEST NEWS {i+1}\n\n{title}"
            send_message(msg)

        time.sleep(60)

# ===== البداية =====
if __name__ == "__main__":
    startup()
    run()