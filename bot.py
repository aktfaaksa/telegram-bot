import asyncio
import aiohttp
import hashlib
import os
import random
import time
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
sent_alerts = set()
last_index_sent = 0

# ====== القطاعات ======
SECTORS = {
    "tech": ["AAPL", "MSFT", "NVDA", "AMD", "META"],
    "energy": ["XOM", "CVX", "OXY", "SLB"],
    "financial": ["JPM", "GS", "BAC", "MS"],
    "healthcare": ["JNJ", "PFE", "MRK", "UNH"],
    "consumer": ["AMZN", "TSLA", "HD", "MCD"],
    "industrial": ["BA", "CAT", "GE", "HON"],
    "communication": ["META", "GOOGL", "NFLX"],
    "utilities": ["NEE", "DUK", "SO"],
    "real_estate": ["PLD", "AMT", "O"]
}

# ====== أدوات ======
def news_id(title):
    words = title.lower().split()
    key = " ".join(words[:8])
    return hashlib.md5(key.encode()).hexdigest()

def smart_translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ====== تحليل الخبر ======
def analyze_news(title):
    t = title.lower()
    score = 0
    reasons = []

    if any(w in t for w in ["beat", "strong", "growth", "surge"]):
        score += 3
        reasons.append("نتائج قوية")

    if any(w in t for w in ["miss", "loss", "drop", "crash"]):
        score -= 3
        reasons.append("نتائج ضعيفة")

    if any(w in t for w in ["war", "iran", "conflict", "hormuz"]):
        score -= 2
        reasons.append("توتر جيوسياسي")

    if any(w in t for w in ["inflation", "oil"]):
        score += 1
        reasons.append("تأثير اقتصادي")

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

# ====== تحديد القطاع ======
def detect_sector(title):
    t = title.lower()

    if any(w in t for w in ["oil", "energy", "gas", "iran"]):
        return "energy"
    if any(w in t for w in ["ai", "chip", "nvidia", "tech"]):
        return "tech"
    if any(w in t for w in ["bank", "fed", "rates"]):
        return "financial"
    if any(w in t for w in ["drug", "health", "fda"]):
        return "healthcare"
    if any(w in t for w in ["retail", "amazon", "tesla"]):
        return "consumer"
    if any(w in t for w in ["industrial", "boeing"]):
        return "industrial"

    return None

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

# ====== تحليل القطاع ======
async def analyze_sector(session, sector):
    stocks = SECTORS.get(sector, [])
    results = []

    for s in stocks:
        change, _ = await get_price(session, s)
        if change is not None:
            results.append((s, change))

    if not results:
        return "غير واضح", []

    avg = sum(c for _, c in results) / len(results)

    if avg > 1:
        trend = "📈 صاعد"
    elif avg < -1:
        trend = "📉 هابط"
    else:
        trend = "⚖️ متذبذب"

    return trend, results

# ====== فلترة أسهم القطاع (بدون خلط) ======
async def get_clean_sector_stocks(session, sector):
    stocks = SECTORS.get(sector, [])
    results = []

    for symbol in stocks:
        change, _ = await get_price(session, symbol)

        if change is None:
            continue

        if abs(change) < 0.5:
            continue

        results.append((symbol, change))

    return sorted(results, key=lambda x: abs(x[1]), reverse=True)

# ====== القرار ======
def make_decision(score, sector_trend):
    if score < 0 and "هابط" in sector_trend:
        return "🚫 تجنب قوي"
    if score < 0:
        return "⚠️ ضعف - انتبه"
    if score > 0 and "صاعد" in sector_trend:
        return "💥 فرصة قوية"
    return "⚪ مراقبة"

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
    global last_index_sent

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                current_time = time.time()

                # ===== مؤشرات السوق =====
                if current_time - last_index_sent > 1800:
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

                # ===== الأخبار =====
                news_list = await get_news(session)

                for n in news_list[:10]:
                    title = n.get("headline")
                    url = n.get("url")

                    if not title or not url:
                        continue

                    nid = news_id(title)
                    if nid in sent_news:
                        continue

                    analysis = analyze_news(title)
                    if abs(analysis["score"]) < 1:
                        continue

                    sector = detect_sector(title)

                    sector_text = "غير محدد"
                    stocks_text = ""
                    sector_trend = ""

                    if sector:
                        trend, _ = await analyze_sector(session, sector)
                        stocks = await get_clean_sector_stocks(session, sector)

                        sector_trend = trend
                        sector_text = f"{sector.upper()} ({trend})"

                        for s, c in stocks:
                            arrow = "↑" if c > 0 else "↓"
                            stocks_text += f"{s} {arrow} {c}%\n"

                    decision = make_decision(analysis["score"], sector_trend)
                    ar = smart_translate(title)

                    msg = (
                        f"{analysis['label']}\n\n"
                        f"🏭 القطاع: {sector_text}\n\n"
                        f"📈 الأسهم:\n{stocks_text if stocks_text else '—'}\n\n"
                        f"🧠 الأسباب: {', '.join(analysis['reasons'])}\n\n"
                        f"💰 القرار: {decision}\n\n"
                        f"📰 {title}\n\n"
                        f"🇸🇦 {ar}\n\n"
                        f"🔗 {url}"
                    )

                    for chat_id in CHAT_IDS:
                        await bot.send_message(chat_id=chat_id, text=msg)

                    sent_news.add(nid)
                    await asyncio.sleep(2)

                print("يتم التحديث...")
                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())