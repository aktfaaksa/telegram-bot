import asyncio
import aiohttp
import hashlib
import os
from telegram import Bot
from deep_translator import GoogleTranslator

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880,   # حسابك
    # 1234567890  # 👈 أضف الشخص الثاني هنا
]

# ====== تخزين ======
sent_news = set()

# ====== القطاعات ======
SECTORS = {
    "energy": ["XOM", "CVX", "OXY"],
    "tech": ["AAPL", "MSFT", "NVDA"],
    "financial": ["JPM", "GS", "BAC"]
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

    positive = ["surge", "soar", "beat", "growth", "strong", "upgrade"]
    negative = ["miss", "drop", "crash", "loss", "downgrade"]

    score = 0

    for w in positive:
        if w in t:
            score += 2

    for w in negative:
        if w in t:
            score -= 2

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

    return {
        "score": score,
        "label": label
    }

# ====== تحديد القطاع ======
def detect_sector(title):
    t = title.lower()

    if any(word in t for word in ["oil", "crude", "energy", "gas", "opec", "iran"]):
        return "energy"

    if any(word in t for word in ["ai", "chip", "nvidia", "tech", "semiconductor"]):
        return "tech"

    if any(word in t for word in ["bank", "interest", "fed", "rates"]):
        return "financial"

    return None

# ====== جلب السعر ======
async def get_price(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"

    try:
        async with session.get(url) as resp:
            data = await resp.json()
            c = data.get("c")
            pc = data.get("pc")

            if c and pc:
                change = ((c - pc) / pc) * 100
                return round(change, 2)
    except:
        pass

    return None

# ====== تحليل القطاع ======
async def analyze_sector(session, sector):
    stocks = SECTORS.get(sector, [])
    results = []

    for s in stocks:
        change = await get_price(session, s)
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

# ====== Macro (النفط + الذهب + السوق) ======
async def get_macro(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"

    try:
        async with session.get(url) as resp:
            data = await resp.json()
            c = data.get("c")
            pc = data.get("pc")

            if c and pc:
                change = ((c - pc) / pc) * 100
                return round(change, 2)
    except:
        pass

    return None


async def get_macro_analysis(session):
    oil = await get_macro(session, "CL=F")
    gold = await get_macro(session, "GC=F")
    spy = await get_macro(session, "SPY")
    qqq = await get_macro(session, "QQQ")

    # السوق
    if spy is not None and qqq is not None:
        if spy > 0 and qqq > 0:
            market = "📈 صاعد"
        elif spy < 0 and qqq < 0:
            market = "📉 هابط"
        else:
            market = "⚖️ متذبذب"
    else:
        market = "غير واضح"

    # تحليل عام
    signal = "⚖️ طبيعي"

    if oil is not None and oil > 1:
        signal = "🔥 ضغط تضخمي"

    if gold is not None and gold > 1:
        signal = "🛡️ توجه للأمان"

    if oil is not None and gold is not None:
        if oil > 1 and gold > 1:
            signal = "⚠️ تضخم + خوف"

    return {
        "oil": oil,
        "gold": gold,
        "market": market,
        "signal": signal
    }

# ====== جلب الأخبار ======
async def get_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"

    try:
        async with session.get(url) as resp:
            return await resp.json()
    except:
        return []

# ====== التشغيل ======
async def main():
    async with aiohttp.ClientSession() as session:

        while True:
            try:
                # 🧠 تحليل السوق
                macro = await get_macro_analysis(session)

                news_list = await get_news(session)

                for n in news_list:
                    title = n.get("headline")
                    url = n.get("url")

                    if not title or not url:
                        continue

                    nid = news_id(title)
                    if nid in sent_news:
                        continue

                    analysis = analyze_news(title)

                    if analysis["score"] == 0:
                        continue

                    sector = detect_sector(title)

                    sector_text = "غير محدد"
                    stocks_text = ""

                    if sector:
                        trend, stocks = await analyze_sector(session, sector)
                        sector_text = f"{sector.upper()} ({trend})"

                        for s, c in stocks:
                            arrow = "↑" if c > 0 else "↓"
                            stocks_text += f"{s} {arrow} {c}%\n"

                    ar = smart_translate(title)

                    msg = (
                        f"{analysis['label']}\n\n"
                        f"📈 السوق: {macro['market']}\n"
                        f"━━━━━━━━━━━━━━\n\n"
                        f"🛢️ النفط: {macro['oil']}%\n"
                        f"🪙 الذهب: {macro['gold']}%\n"
                        f"🧠 {macro['signal']}\n\n"
                        f"🏭 القطاع: {sector_text}\n\n"
                        f"📈 الأسهم:\n{stocks_text if stocks_text else '—'}\n\n"
                        f"📰 {title}\n\n"
                        f"🇸🇦 {ar}\n\n"
                        f"🔗 {url}"
                    )

                    for chat_id in CHAT_IDS:
                        try:
                            await bot.send_message(chat_id=chat_id, text=msg)
                        except:
                            pass

                    sent_news.add(nid)
                    await asyncio.sleep(2)

                print("يتم التحديث...")
                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

# ===== تشغيل =====
if __name__ == "__main__":
    asyncio.run(main())