# AlphaBot v4.4 SMART MARKET FEED

import os, time, requests, feedparser, hashlib
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

RSS = [
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

BLOCK = ["crypto","coin","token","celebrity","sports"]

STOCK_WORDS = ["earnings","revenue","shares","stock","plunge","surge","guidance"]
MARKET_WORDS = ["oil","fed","inflation","rates","war","iran","dollar","yield"]

seen = set()

def send(msg):
    for c in CHAT_IDS:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": c, "text": msg}
        )

def is_new(t):
    h = hashlib.md5(t.encode()).hexdigest()
    if h in seen:
        return False
    seen.add(h)
    return True

def recent(p):
    if not p: return True
    t = datetime(*p[:6], tzinfo=timezone.utc)
    return (datetime.now(timezone.utc)-t).seconds < 7200

def fetch():
    data = []
    for u in RSS:
        f = feedparser.parse(u)
        for e in f.entries:
            data.append(e)
    return data

def run():
    send("🚀 AlphaBot v4.4 MARKET Started")

    while True:
        news = fetch()
        count = 0

        for n in news:
            title = n.title.lower()

            if any(w in title for w in BLOCK):
                continue

            if not is_new(n.title):
                continue

            if not recent(n.get("published_parsed")):
                continue

            # 🟢 STOCK NEWS
            if any(w in title for w in STOCK_WORDS):
                tag = "📊 STOCK"

            # 🔵 MARKET NEWS
            elif any(w in title for w in MARKET_WORDS):
                tag = "🌍 MARKET"

            else:
                continue

            msg = f"""
{tag}

📰 {n.title}

🔗 {n.link}
"""
            send(msg)

            count += 1
            if count >= 15:
                break

        time.sleep(120)

if __name__ == "__main__":
    run()