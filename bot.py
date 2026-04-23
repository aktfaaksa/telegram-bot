# AlphaBot Pro v3.2.1 DEBUG

import os
import time
import requests
import feedparser

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = 6315087880

RSS_FEEDS = [
    "https://www.benzinga.com/feed",
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss"
]

def send_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text}
        )
    except Exception as e:
        print("SEND ERROR:", e)

def startup():
    send_message("🚨 DEBUG MODE STARTED")

def run():
    while True:
        all_news = []

        for url in RSS_FEEDS:
            feed = feedparser.parse(url)
            for e in feed.entries:
                all_news.append(e.title)

        print("TOTAL NEWS:", len(all_news))

        # 🚨 نرسل أول 5 أخبار مباشرة بدون أي فلترة
        for i, title in enumerate(all_news[:5]):
            msg = f"📰 TEST NEWS {i+1}\n\n{title}"
            send_message(msg)

        time.sleep(60)  # دقيقة

if __name__ == "__main__":
    startup()
    run()