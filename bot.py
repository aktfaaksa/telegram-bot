# ===== Alpha Market Intelligence v2.0 (Clean + Smart) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, requests, json
from telegram import Bot

# ===== API =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

# ===== RSS =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reuters.com/markets/us/rss"
]

sent = set()

# ===== FILTERS (🔥 مهم جدًا) =====
CRAMER_FILTER = ["jim cramer", "cramer", "mad money"]

TRASH_FILTER = [
    "likes this stock", "should you buy", "top stock",
    "why this stock", "opinion", "analysis", "preview"
]

WEAK_NEWS = [
    "earnings transcript", "conference call",
    "q1", "q2", "q3", "q4"
]

# ===== استخراج رمز السهم =====
def extract_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

# ===== AI تحليل متقدم =====
def analyze_news(text):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER}"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"""
حلل الخبر وارجع JSON فقط:
{{
"type": "market أو stock أو risk",
"impact": "high أو medium أو low",
"direction": "bullish أو bearish أو neutral",
"summary": "شرح عربي واضح ومختصر"
}}

{text[:600]}
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

# ===== LIVE SYSTEM =====
async def live_feed():

    entries = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        entries.extend(feed.entries)

    market_news, signals, risks = [], [], []

    for e in entries:

        key = hashlib.md5((e.title + e.link).encode()).hexdigest()
        if key in sent:
            continue
        sent.add(key)

        title = e.title.lower()

        # ===== فلترة قوية =====
        if any(x in title for x in CRAMER_FILTER):
            continue

        if any(x in title for x in TRASH_FILTER):
            continue

        if any(x in title for x in WEAK_NEWS):
            continue

        analysis = analyze_news(e.title)
        if not analysis:
            continue

        impact = analysis.get("impact")
        direction = analysis.get("direction")
        summary = analysis.get("summary")
        typ = analysis.get("type")

        # فقط الأخبار القوية
        if impact != "high":
            continue

        symbol = extract_symbol(e.title)

        # ===== التصنيف الذكي =====
        if typ == "risk" or direction == "bearish":
            risks.append(f"🚨 {summary}")

        elif typ == "stock" and symbol:
            signals.append(f"🎯 {symbol} - {summary}")

        elif typ == "market":
            market_news.append(f"📰 {summary}")

    # تحديد العدد
    market_news = market_news[:4]
    signals = signals[:3]
    risks = risks[:3]

    # ===== بناء الرسالة =====
    msg = "📡 تحديث السوق الذكي (Live)\n\n"

    if market_news:
        msg += "🟢 السوق:\n" + "\n".join(market_news) + "\n\n"

    if signals:
        msg += "🎯 فرص قوية:\n" + "\n".join(signals) + "\n\n"

    if risks:
        msg += "🚨 مخاطر:\n" + "\n".join(risks) + "\n\n"

    if not market_news and not signals and not risks:
        msg += "⚪ لا يوجد أخبار مؤثرة حالياً"

    await send_msg(msg)

# ===== MAIN =====
async def main():
    print("🚀 تشغيل v2.0 (Smart Clean Feed)")

    await send_msg("✅ البوت شغال v2.0 (فلترة ذكية + بدون ضوضاء)")

    while True:
        try:
            await live_feed()
            await asyncio.sleep(300)  # كل 5 دقائق

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(60)

asyncio.run(main())