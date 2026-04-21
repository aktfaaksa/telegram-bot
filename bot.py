# ===== Alpha Market Intelligence v2.3 (Event + Translation) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== API =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=BOT_TOKEN)

# ===== RSS =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reuters.com/markets/us/rss"
]

sent = set()

# ===== FILTERS =====
CRAMER_FILTER = ["jim cramer", "cramer", "mad money"]

TRASH_FILTER = [
    "likes this stock", "should you buy", "top stock",
    "why this stock", "opinion", "analysis", "preview"
]

WEAK_NEWS = [
    "earnings transcript", "conference call",
    "q1", "q2", "q3", "q4"
]

EVENT_KEYWORDS = [
    "announces", "approval", "acquires",
    "merger", "deal", "partnership",
    "reports", "beats", "misses",
    "raises", "cuts", "launches"
]

PREDICTION_FILTER = [
    "expects", "forecast", "predict",
    "could", "may", "might",
    "analyst", "analysts",
    "price target", "outlook"
]

# ===== ترجمة =====
def tr(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== استخراج السهم =====
def extract_symbol(text):
    m = re.findall(r'\(([A-Z]{1,5})\)', text)
    return m[0] if m else None

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

    bullish = 0
    bearish = 0

    for e in entries:

        key = hashlib.md5((e.title + e.link).encode()).hexdigest()
        if key in sent:
            continue
        sent.add(key)

        title = e.title.lower()

        # ===== فلترة =====
        if any(x in title for x in CRAMER_FILTER):
            continue

        if any(x in title for x in TRASH_FILTER):
            continue

        if any(x in title for x in WEAK_NEWS):
            continue

        if any(x in title for x in PREDICTION_FILTER):
            continue

        if not any(word in title for word in EVENT_KEYWORDS):
            continue

        if len(title) < 25:
            continue

        symbol = extract_symbol(e.title)

        # ترجمة
        translated = tr(e.title)

        formatted = f"📰 {e.title}\n🇸🇦 {translated}"

        # ===== تصنيف =====
        if any(x in title for x in ["drops", "falls", "declines", "cut", "risk"]):
            risks.append(f"🚨 {e.title}\n🇸🇦 {translated}")
            bearish += 1

        elif any(x in title for x in ["surges", "rises", "gains", "beats", "deal", "acquires"]):
            if symbol:
                signals.append(f"🎯 {symbol}\n{e.title}\n🇸🇦 {translated}")
            else:
                market_news.append(formatted)
            bullish += 1

        else:
            market_news.append(formatted)

    # ===== الاتجاه =====
    if bullish > bearish:
        trend = "🟢 صاعد"
    elif bearish > bullish:
        trend = "🔴 هابط"
    else:
        trend = "🟡 متذبذب"

    total = bullish + bearish
    score = int((bullish / total) * 100) if total > 0 else 50

    # ===== تقليل =====
    market_news = market_news[:4]
    signals = signals[:3]
    risks = risks[:3]

    # ===== الرسالة =====
    msg = f"📡 تحديث السوق (Live)\n\n📊 الاتجاه: {trend}\n📊 القوة: {score}/100\n\n"

    if market_news:
        msg += "🟢 السوق:\n" + "\n\n".join(market_news) + "\n\n"

    if signals:
        msg += "🎯 فرص:\n" + "\n\n".join(signals) + "\n\n"

    if risks:
        msg += "🚨 مخاطر:\n" + "\n\n".join(risks) + "\n\n"

    if not market_news and not signals and not risks:
        msg += "⚪ لا يوجد أحداث حقيقية حالياً"

    await send_msg(msg)

# ===== MAIN =====
async def main():
    print("🚀 تشغيل v2.3 (Event + Translation)")

    await send_msg("✅ البوت شغال v2.3 (ترجمة + نظام احترافي)")

    while True:
        try:
            await live_feed()
            await asyncio.sleep(300)  # كل 5 دقائق

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(60)

asyncio.run(main())