# ===== Alpha Hybrid Market Intelligence (Live Feed) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot

# ===== API KEYS (مهم - لا يتغير) =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

# ===== RSS =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent = set()

# ===== FILTERS =====
WEAK_NEWS = [
    "what makes", "why ", "undervalued",
    "best stock", "to invest", "top stock",
    "earnings transcript", "conference call",
    "q1", "q2", "q3", "q4"
]

# ===== استخراج رمز السهم =====
def extract_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== AI تحليل =====
def score_news(text):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER}"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"""
حلل هذا الخبر وأرجع JSON فقط:
{{"score": 0-100, "sentiment": "bullish أو bearish أو neutral", "reason": "شرح عربي مختصر"}}

{text[:500]}
"""
                }]
            },
            timeout=10
        )
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        return None

# ===== إرسال =====
async def send_msg(text):
    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=text)

# ===== LIVE FEED =====
async def live_feed():

    entries = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        entries.extend(feed.entries)

    news, signals, risks = [], [], []

    for e in entries:

        key = hashlib.md5((e.title + e.link).encode()).hexdigest()
        if key in sent:
            continue
        sent.add(key)

        title = e.title.lower()

        # فلترة
        if any(x in title for x in WEAK_NEWS):
            continue

        analysis = score_news(e.title)
        if not analysis:
            continue

        score = analysis.get("score", 0)
        sentiment = analysis.get("sentiment", "")
        reason = analysis.get("reason", "")

        if score < 70:
            continue

        symbol = extract_symbol(e.title)

        # تصنيف
        if sentiment == "bearish":
            risks.append(f"🚨 {reason}")

        elif symbol:
            signals.append(f"🎯 {symbol} - {reason}")

        else:
            news.append(f"📰 {reason}")

    # تحديد العدد
    news = news[:5]
    signals = signals[:3]
    risks = risks[:3]

    # بناء الرسالة
    msg = "📡 تحديث السوق (Live)\n\n"

    if news:
        msg += "🟢 أخبار مهمة:\n" + "\n".join(news) + "\n\n"

    if signals:
        msg += "🎯 فرص:\n" + "\n".join(signals) + "\n\n"

    if risks:
        msg += "🚨 تحذيرات:\n" + "\n".join(risks) + "\n\n"

    if not news and not signals and not risks:
        msg += "⚪ السوق هادئ حالياً"

    await send_msg(msg)

# ===== MAIN =====
async def main():
    print("🚀 تشغيل البوت (Live Market Feed)")

    # رسالة بداية
    await send_msg("✅ البوت شغال (Live Feed كل 5 دقائق)")

    while True:
        try:
            await live_feed()
            await asyncio.sleep(300)  # كل 5 دقائق

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(60)

asyncio.run(main())