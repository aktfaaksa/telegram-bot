# AlphaBot v4.3 LIVE NEWS (FULL)

import os
import time
import requests

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

# ===== إعدادات =====
CHECK_INTERVAL = 60       # كل دقيقة
MAX_NEWS = 10             # حد الإرسال
MAX_AGE = 1800            # 30 دقيقة فقط

seen = set()

# ===== إرسال =====
def send(msg):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": msg}
            )
        except:
            pass

# ===== جلب الأخبار =====
def fetch_news():
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        return requests.get(url).json()
    except:
        return []

# ===== تشغيل =====
def run():
    send("⚡ AlphaBot LIVE NEWS Started")

    while True:
        news = fetch_news()
        now = int(time.time())
        count = 0

        for n in news:
            title = n.get("headline", "")
            link = n.get("url", "")
            timestamp = n.get("datetime", 0)

            # ❌ بدون عنوان
            if not title:
                continue

            # ❌ تكرار
            if title in seen:
                continue

            # ⏱ فلترة الوقت (آخر 30 دقيقة)
            if now - timestamp > MAX_AGE:
                continue

            seen.add(title)

            msg = f"""
⚡ LIVE NEWS

📰 {title}

🔗 {link}
"""

            send(msg)

            count += 1
            if count >= MAX_NEWS:
                break

        time.sleep(CHECK_INTERVAL)

# ===== Start =====
if __name__ == "__main__":
    run()