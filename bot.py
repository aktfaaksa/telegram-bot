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

# ✅ أضفنا Chat ID إضافي
CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880,   # الموجود عندك
    1234567890    # 👈 حط هنا ID الشخص الثاني
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

    if "oil" in t or "crude" in t:
        return "energy"
    if "ai" in t or "chip" in t or "nvidia" in t:
        return "tech"
    if "bank" in t or "interest" in t:
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
                news_list = await get_news(session)

                for n in news_list:
                    title = n.get("headline")
                    url = n.get("url")

                    if not title or not url:
                        continue

                    nid = news_id(title)
                    if nid in sent_news:
                        continue

                    # تحليل
                    analysis = analyze_news(title)

                    # فلترة الأخبار الضعيفة
                    if analysis["score"] == 0:
                        continue

                    # قطاع
                    sector = detect_sector(title)

                    sector_text = "غير محدد"
                    stocks_text = ""

                    if sector:
                        trend, stocks = await analyze_sector(session, sector)

                        sector_text = f"{sector.upper()} ({trend})"

                        for s, c in stocks:
                            arrow = "↑" if c > 0 else "↓"
                            stocks_text += f"{s} {arrow} {c}%\n"

                    # ترجمة
                    ar = smart_translate(title)

                    # الرسالة
                    msg = (
                        f"{analysis['label']}\n\n"
                        f"━━━━━━━━━━━━━━\n\n"
                        f"🏭 القطاع: {sector_text}\n\n"
                        f"📈 الأسهم:\n{stocks_text if stocks_text else '—'}\n\n"
                        f"📰 {title}\n\n"
                        f"🇸🇦 {ar}\n\n"
                        f"🔗 {url}"
                    )

                    # إرسال
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