
# ===== Alpha News Engine v2.1 =====
# Market Indices (Market Hours) + News 24/7

import asyncio
import aiohttp
import hashlib
import os
import time
from datetime import datetime
from telegram import Bot
from deep_translator import GoogleTranslator

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880,
]

sent_news = set()

last_index_sent = 0
last_news_sent = 0

market_open_sent = False
market_close_sent = False

# ====== أدوات ======
def news_id(title):
    return hashlib.md5(title.lower().encode()).hexdigest()

def smart_translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ====== وقت السوق ======
def is_market_open():
    now = datetime.now()

    if now.weekday() > 4:
        return False

    minutes = now.hour * 60 + now.minute
    open_time = 16 * 60 + 30   # 4:30 PM
    close_time = 23 * 60       # 11:00 PM

    return open_time <= minutes <= close_time

def is_market_just_open():
    now = datetime.now()
    return now.hour == 16 and now.minute == 30

def is_market_close():
    now = datetime.now()
    return now.hour == 23 and now.minute == 0

# ====== تحليل الخبر ======
def analyze_news(title):
    t = title.lower()
    score = 0
    reasons = []

    if any(w in t for w in ["beat", "strong", "growth", "surge", "profit"]):
        score += 3
        reasons.append("نتائج قوية")

    if any(w in t for w in ["miss", "loss", "drop", "crash"]):
        score -= 3
        reasons.append("نتائج ضعيفة")

    if any(w in t for w in ["war", "iran"]):
        score -= 2
        reasons.append("توتر جيوسياسي")

    if any(w in t for w in ["inflation", "fed", "rates"]):
        score += 1
        reasons.append("بيانات اقتصادية")

    if score >= 3:
        label = "🚀 إيجابي قوي"
    elif score > 0:
        label = "📈 إيجابي"
    elif score <= -3:
        label = "📉 سلبي قوي"
    elif score < 0:
        label = "⚠️ سلبي"
    else:
        label = "⚖️ متضارب"

    return {"score": score, "label": label, "reasons": reasons}

# ====== الأسعار ======
async def get_price(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            c = data.get("c")
            pc = data.get("pc")

            if c and pc:
                return round(((c - pc) / pc) * 100, 2), c
    except:
        pass
    return None, None

# ====== الأخبار ======
async def get_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    try:
        async with session.get(url) as resp:
            return await resp.json()
    except:
        return []

# ====== التشغيل ======
async def main():
    global last_index_sent, last_news_sent
    global market_open_sent, market_close_sent

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = datetime.now()
                current_time = time.time()

                # ===== افتتاح السوق =====
                if is_market_just_open() and not market_open_sent:
                    for chat_id in CHAT_IDS:
                        await bot.send_message(chat_id=chat_id, text="🟢 افتتاح السوق الأمريكي")
                    market_open_sent = True

                # ===== إغلاق السوق =====
                if is_market_close() and not market_close_sent:
                    for chat_id in CHAT_IDS:
                        await bot.send_message(chat_id=chat_id, text="🔴 إغلاق السوق الأمريكي")
                    market_close_sent = True

                # ===== إعادة ضبط يوم جديد =====
                if now.hour == 1:
                    market_open_sent = False
                    market_close_sent = False

                # ===== مؤشرات السوق (فقط وقت السوق) =====
                if is_market_open() and (current_time - last_index_sent > 3600):
                    last_index_sent = current_time

                    spy, _ = await get_price(session, "SPY")
                    qqq, _ = await get_price(session, "QQQ")
                    dia, _ = await get_price(session, "DIA")

                    msg = (
                        f"📊 مؤشرات السوق\n\n"
                        f"💻 ناسداك: {qqq if qqq else '—'}%\n"
                        f"📈 S&P500: {spy if spy else '—'}%\n"
                        f"🏛️ داو جونز: {dia if dia else '—'}%"
                    )

                    for chat_id in CHAT_IDS:
                        await bot.send_message(chat_id=chat_id, text=msg)

                # ===== الأخبار (24/7) =====
                if current_time - last_news_sent > 300:

                    last_news_sent = current_time
                    news_list = await get_news(session)

                    for n in news_list[:5]:
                        title = n.get("headline")
                        url = n.get("url")

                        if not title or not url:
                            continue

                        nid = news_id(title)
                        if nid in sent_news:
                            continue

                        analysis = analyze_news(title)

                        if abs(analysis["score"]) < 2:
                            continue

                        ar = smart_translate(title)

                        msg = (
                            f"{analysis['label']}\n\n"
                            f"📰 {title}\n\n"
                            f"🇸🇦 {ar}\n\n"
                            f"🔗 {url}"
                        )

                        for chat_id in CHAT_IDS:
                            await bot.send_message(chat_id=chat_id, text=msg)

                        sent_news.add(nid)

                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
```
