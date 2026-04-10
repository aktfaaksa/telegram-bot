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
    6315087880,
]

sent_news = set()
sent_movers = set()

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

    positive = ["surge", "soar", "beat", "growth", "strong"]
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

    return {"score": score, "label": label}

# ====== القطاع ======
def detect_sector(title):
    t = title.lower()

    if any(w in t for w in ["oil", "energy", "gas", "opec", "iran"]):
        return "energy"
    if any(w in t for w in ["ai", "chip", "nvidia", "tech"]):
        return "tech"
    if any(w in t for w in ["bank", "interest", "fed"]):
        return "financial"

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

# ====== القطاع ======
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

# ====== Macro ======
async def get_macro_analysis(session):
    oil, _ = await get_price(session, "USO")
    gold, _ = await get_price(session, "GLD")
    spy, _ = await get_price(session, "SPY")
    qqq, _ = await get_price(session, "QQQ")

    if spy and qqq:
        if spy > 0 and qqq > 0:
            market = "📈 صاعد"
        elif spy < 0 and qqq < 0:
            market = "📉 هابط"
        else:
            market = "⚖️ متذبذب"
    else:
        market = "غير واضح"

    signal = "⚖️ طبيعي"
    if oil and oil > 1:
        signal = "🔥 تضخم"
    if gold and gold > 1:
        signal = "🛡️ خوف"
    if oil and gold and oil > 1 and gold > 1:
        signal = "⚠️ تضخم + خوف"

    return {"oil": oil, "gold": gold, "market": market, "signal": signal}

# ====== 🧠 Decision Engine (محسن) ======
def make_decision(score, sector_trend, macro):
    if score < 0 and "هابط" in sector_trend:
        return "🚫 تجنب قوي"

    if score > 0 and "هابط" in sector_trend:
        return "⚠️ تناقض - انتبه"

    if score > 0 and "صاعد" in sector_trend and macro["market"] == "📈 صاعد":
        return "💥 فرصة قوية"

    if score > 0 and "صاعد" in sector_trend:
        return "💰 فرصة محتملة"

    if macro["signal"] == "⚠️ تضخم + خوف":
        return "⚠️ حذر"

    return "⚪ مراقبة"

# ====== Top Movers ======
async def get_top_movers(session):
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={API_KEY}"
    try:
        async with session.get(url) as resp:
            symbols = await resp.json()

        movers = []

        for s in symbols[:60]:
            symbol = s.get("symbol")

            if not symbol or len(symbol) > 5:
                continue

            change, price = await get_price(session, symbol)

            if change is None or price is None:
                continue

            # فلترة ذكية
            if price < 1:
                if abs(change) < 10:
                    continue
            else:
                if abs(change) < 5:
                    continue

            movers.append((symbol, price, change))

        return movers[:3]

    except:
        return []

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
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                macro = await get_macro_analysis(session)

                # ===== الأخبار =====
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
                    sector_trend = ""

                    if sector:
                        trend, stocks = await analyze_sector(session, sector)
                        sector_trend = trend
                        sector_text = f"{sector.upper()} ({trend})"

                        for s, c in stocks:
                            arrow = "↑" if c > 0 else "↓"
                            stocks_text += f"{s} {arrow} {c}%\n"

                    decision = make_decision(analysis["score"], sector_trend, macro)
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
                        f"💰 القرار: {decision}\n\n"
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

                # ===== Top Movers =====
                movers = await get_top_movers(session)

                for symbol, price, change in movers:
                    mid = f"{symbol}_{round(change)}"
                    if mid in sent_movers:
                        continue

                    sent_movers.add(mid)

                    direction = "📈 صعود قوي" if change > 0 else "📉 هبوط قوي"
                    emoji = "🚀" if change > 0 else "🔻"

                    msg = (
                        f"{emoji} سهم يتحرك بقوة\n\n"
                        f"🏢 {symbol}\n"
                        f"{direction}\n"
                        f"📊 {change}%\n"
                        f"💵 ${price}\n\n"
                        f"💰 فرصة محتملة"
                    )

                    for chat_id in CHAT_IDS:
                        try:
                            await bot.send_message(chat_id=chat_id, text=msg)
                        except:
                            pass

                    await asyncio.sleep(2)

                if len(sent_movers) > 50:
                    sent_movers.clear()

                print("يتم التحديث...")
                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

# ===== تشغيل =====
if __name__ == "__main__":
    asyncio.run(main())