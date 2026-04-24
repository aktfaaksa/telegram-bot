# AlphaBot Pro v4.5 SMART TRANSLATION

import os, time, requests, feedparser, hashlib
from datetime import datetime, timezone

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

# ===== RSS =====
RSS = [
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

# ===== فلترة =====
BLOCK = ["crypto","coin","token","video","trailer"]
STOCK_WORDS = ["earnings","revenue","shares","stock","plunge","surge","guidance"]
MARKET_WORDS = ["oil","fed","inflation","rates","war","iran","dollar","yield"]

seen = set()

# ===== إرسال =====
def send(msg):
    for c in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": c, "text": msg}
            )
        except:
            pass

# ===== منع التكرار =====
def is_new(t):
    h = hashlib.md5(t.encode()).hexdigest()
    if h in seen:
        return False
    seen.add(h)
    return True

# ===== الوقت =====
def recent(p):
    if not p: return True
    t = datetime(*p[:6], tzinfo=timezone.utc)
    return (datetime.now(timezone.utc)-t).seconds < 7200

# ===== ترجمة =====
def translate(text):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"ترجم هذا الخبر للعربية في سطر واحد فقط:\n{text}"
                }]
            }
        )
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""

# ===== جلب =====
def fetch():
    data = []
    for u in RSS:
        f = feedparser.parse(u)
        for e in f.entries:
            data.append(e)
    return data

# ===== تشغيل =====
def run():
    send("🚀 AlphaBot v4.5 SMART Started")

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

            # ===== تصنيف =====
            if any(w in title for w in STOCK_WORDS):
                tag = "📊 STOCK"
                translated = translate(n.title)

            elif any(w in title for w in MARKET_WORDS):
                tag = "🌍 MARKET"
                translated = ""  # بدون ترجمة لتوفير السرعة

            else:
                continue

            msg = f"""
{tag}

📰 {n.title}
{f"🌍 {translated}" if translated else ""}

🔗 {n.link}
"""
            send(msg)

            count += 1
            if count >= 15:
                break

        time.sleep(120)

if __name__ == "__main__":
    run()