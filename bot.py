```python
import asyncio
import aiohttp
import hashlib
import os
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
last_index_sent = 0

# وضع النخبة (يشغل فقط الأخبار القوية)
ELITE_MODE = False

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
    return hashlib.md5(title.lower().encode()).hexdigest()

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

    positive = ["beat", "strong", "growth", "surge", "record", "profit"]
    negative = ["miss", "loss", "drop", "crash", "decline"]

    geo = ["war", "iran", "conflict", "hormuz"]
    macro = ["inflation", "rates", "fed", "interest"]

    if any(w in t for w in positive):
        score += 3
        reasons.append("نتائج قوية")

    if any(w in t for w in negative):
        score -= 3
        reasons.append("نتائج ضعيفة")

    if any(w in t for w in geo):
        score -= 2
        reasons.append("توتر جيوسياسي")

    if any(w in t for w in macro):
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

# ====== تحليل القطاع (سريع) ======
async def analyze_sector(session, sector):
    stocks = SECTORS.get(sector, [])
    tasks = [get_price(session, s) for s in stocks]
    results_raw = await asyncio.gather(*tasks)

    results = []
    for s, (change, _) in zip(stocks, results_raw):
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

# ====== فلترة الأسهم ======
async def get_clean_sector_stocks(session, sector):
    stocks = SECTORS.get(sector, [])
    tasks = [get_price(session, s) for s in stocks]
    results_raw = await asyncio.gather(*tasks)

    results = []
    for s, (change, _) in zip(stocks, results_raw):
        if change is None:
            continue
        if abs(change) < 0.5:
            continue
        results.append((s, change))

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

                    # فلترة ذكية
                    IMPORTANT_KEYWORDS = ["earnings", "fed", "interest", "inflation", "war", "oil"]

                    if abs(analysis["score"]) < 2 and not any(k in title.lower() for k in IMPORTANT_KEYWORDS):
                        continue

                    # وضع النخبة
                    if ELITE_MODE:
                        if "🚀" not in analysis["label"] and "📉" not in analysis["label"]:
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
                        f"{analysis['label']}\n"
                        f"{'='*25}\n\n"
                        f"🏭 القطاع: {sector_text}\n\n"
                        f"📊 الأسهم الأقوى:\n{stocks_text if stocks_text else '—'}\n"
                        f"{'-'*25}\n"
                        f"🧠 الأسباب:\n• " + "\n• ".join(analysis['reasons']) + "\n\n"
                        f"💰 القرار: {decision}\n"
                        f"{'='*25}\n\n"
                        f"📰 {title}\n\n"
                        f"🇸🇦 {ar}\n\n"
                        f"🔗 المصدر:\n{url}"
                    )

                    for chat_id in CHAT_IDS:
                        await bot.send_message(chat_id=chat_id, text=msg)

                    sent_news.add(nid)

                    # تنظيف الذاكرة
                    if len(sent_news) > 500:
                        sent_news.pop()

                    await asyncio.sleep(2)

                print("يتم التحديث...")
                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
```
