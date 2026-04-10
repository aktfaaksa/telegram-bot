import asyncio
import aiohttp
import hashlib
import os
import random
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

    if any(w in t for w in ["beat", "strong", "growth", "surge", "record"]):
        score += 3
        reasons.append("نتائج قوية")

    if any(w in t for w in ["miss", "loss", "drop", "crash", "warning"]):
        score -= 3
        reasons.append("نتائج ضعيفة")

    if any(w in t for w in ["war", "iran", "conflict", "tension"]):
        score -= 2
        reasons.append("توتر جيوسياسي")

    if any(w in t for w in ["inflation", "oil", "energy"]):
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

    if any(w in t for w in ["oil", "energy", "gas", "opec", "iran"]):
        return "energy"

    if any(w in t for w in ["ai", "chip", "nvidia", "tech", "apple"]):
        return "tech"

    if any(w in t for w in ["bank", "interest", "fed", "rates"]):
        return "financial"

    if any(w in t for w in ["drug", "health", "fda", "pharma"]):
        return "healthcare"

    if any(w in t for w in ["retail", "amazon", "consumer", "tesla"]):
        return "consumer"

    if any(w in t for w in ["industrial", "manufacturing", "boeing"]):
        return "industrial"

    if any(w in t for w in ["google", "meta", "netflix"]):
        return "communication"

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

# ====== Macro ======
async def get_macro_analysis(session):
    oil, _ = await get_price(session, "USO")
    gold, _ = await get_price(session, "GLD")
    spy, _ = await get_price(session, "SPY")
    qqq, _ = await get_price(session, "QQQ")

    if spy is not None and qqq is not None:
        if spy > 0 and qqq > 0:
            market = "📈 صاعد"
        elif spy < 0 and qqq < 0:
            market = "📉 هابط"
        else:
            market = "⚖️ متذبذب"
    else:
        market = "غير واضح"

    signal = "⚖️ طبيعي"

    if oil is not None and oil > 1:
        signal = "🔥 تضخم"

    if gold is not None and gold > 1:
        signal = "🛡️ خوف"

    if oil is not None and gold is not None:
        if oil > 1 and gold > 1:
            signal = "⚠️ تضخم + خوف"

    return {"oil": oil, "gold": gold, "market": market, "signal": signal}

# ====== القرار ======
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

# ====== Pre-Explosion Scanner ======
async def get_explosion_candidates(session):
    try:
        nasdaq_url = f"https://finnhub.io/api/v1/stock/symbol?exchange=NASDAQ&token={API_KEY}"
        nyse_url = f"https://finnhub.io/api/v1/stock/symbol?exchange=NYSE&token={API_KEY}"

        async with session.get(nasdaq_url) as r1:
            nasdaq = await r1.json()

        async with session.get(nyse_url) as r2:
            nyse = await r2.json()

        symbols = nasdaq + nyse

        if len(symbols) > 120:
            start = random.randint(0, len(symbols) - 120)
            symbols = symbols[start:start + 120]

        candidates = []

        for s in symbols:
            symbol = s.get("symbol")

            if not symbol or not symbol.isalpha() or len(symbol) > 5:
                continue

            change, price = await get_price(session, symbol)

            if change is None or price is None:
                continue

            if price < 0.3:
                continue

            if 2 <= change < 5:
                label = "🟡 مراقبة"
            elif 5 <= change < 10:
                label = "🔥 مرشح انفجار"
            elif change >= 10:
                label = "🚀 انفجار"
            else:
                continue

            candidates.append((symbol, price, change, label))

        return candidates[:5]

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
                news_list = await get_news(session)

                # تنظيف الذاكرة
                if len(sent_news) > 100:
                    sent_news.clear()

                # ===== الأخبار =====
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
                        f"🏭 القطاع: {sector_text}\n\n"
                        f"📈 الأسهم:\n{stocks_text if stocks_text else '—'}\n\n"
                        f"🧠 الأسباب: {', '.join(analysis['reasons'])}\n\n"
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

                # ===== Pre-Explosion =====
                candidates = await get_explosion_candidates(session)

                for symbol, price, change, label in candidates:
                    cid = f"{symbol}_{round(change)}"
                    if cid in sent_alerts:
                        continue

                    sent_alerts.add(cid)

                    msg = (
                        f"{label}\n\n"
                        f"🏢 {symbol}\n"
                        f"📊 {change}%\n"
                        f"💵 ${price}\n\n"
                        f"⚡ حركة غير طبيعية"
                    )

                    for chat_id in CHAT_IDS:
                        try:
                            await bot.send_message(chat_id=chat_id, text=msg)
                        except:
                            pass

                    await asyncio.sleep(2)

                if len(sent_alerts) > 50:
                    sent_alerts.clear()

                print("يتم التحديث...")
                await asyncio.sleep(20)

            except Exception as e:
                print("خطأ:", e)
                await asyncio.sleep(10)

# ===== تشغيل =====
if __name__ == "__main__":
    asyncio.run(main())