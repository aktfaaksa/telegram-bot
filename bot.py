import requests
import asyncio
import json
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
    6315087880
]

# ====== تخزين ======
sent_news = set()
sent_movers = set()

# ====== أدوات ======
def news_id(title):
    return hashlib.md5(title.lower()[:60].encode()).hexdigest()

def extract_ticker(title):
    for w in title.split():
        if w.isupper() and 2 <= len(w) <= 5:
            return w
    return None

def smart_translate(title):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(title)
    except:
        return title

# ====== تحليل ======
def smart_analysis(title):
    t = title.lower()
    score = 0
    confidence = 0

    positive = {"surge":3,"soar":3,"beat":4,"growth":2}
    negative = {"miss":-4,"lower":-3,"drop":-2,"crash":-5}

    for w,v in positive.items():
        if w in t:
            score += v
            confidence += 1

    for w,v in negative.items():
        if w in t:
            score += v
            confidence += 1

    if score >= 4:
        label,emoji = "🚀 إيجابي قوي","🟢"
    elif score >= 2:
        label,emoji = "📈 إيجابي","🟢"
    elif score <= -4:
        label,emoji = "📉 سلبي قوي","🔴"
    elif score <= -2:
        label,emoji = "⚠️ سلبي","🔴"
    else:
        label,emoji = "⚖️ متضارب","⚪"

    conf = "🔵 ثقة عالية" if confidence >= 2 else "⚪ ثقة ضعيفة"

    return f"{label} | {conf}", emoji

def news_impact(title):
    t = title.lower()
    score = 0
    if "earnings" in t:
        score += 4
    if "inflation" in t:
        score += 3
    if "surge" in t or "crash" in t:
        score += 2
    return score

def detect_opportunity(analysis, impact):
    if "🚀" in analysis and impact >= 4:
        return "💥 فرصة قوية"
    elif "📈" in analysis:
        return "💰 فرصة محتملة"
    elif "⚠️" in analysis or "📉" in analysis:
        return "🚫 تجنب"
    return "⚪ مراقبة"

# ====== السعر ======
def get_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        d = requests.get(url, timeout=5).json()
        c = d.get("c")
        pc = d.get("pc")
        if c and pc:
            change = ((c - pc) / pc) * 100
            return c, round(change, 2)
    except:
        pass
    return None, None

# ====== السوق ======
def market_status():
    _, spy = get_price("SPY")
    _, qqq = get_price("QQQ")

    if spy and qqq:
        if spy > 0 and qqq > 0:
            return "📈 السوق صاعد"
        elif spy < 0 and qqq < 0:
            return "📉 السوق هابط"

    return "⚖️ السوق متذبذب"

# ====== الأخبار ======
def get_news():
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
        return requests.get(url, timeout=5).json()
    except:
        return []

# ====== Top Movers (NASDAQ + NYSE فقط 🔥) ======
def get_top_movers():
    try:
        nasdaq_url = f"https://finnhub.io/api/v1/stock/symbol?exchange=NASDAQ&token={API_KEY}"
        nyse_url = f"https://finnhub.io/api/v1/stock/symbol?exchange=NYSE&token={API_KEY}"

        symbols = requests.get(nasdaq_url).json() + requests.get(nyse_url).json()

        movers = []

        for s in symbols[:80]:
            symbol = s.get("symbol")

            if len(symbol) > 5:
                continue

            price, change = get_price(symbol)

            if not price:
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

# ====== التشغيل ======
async def main():
    while True:
        try:
            market = market_status()

            # ===== الأخبار =====
            for n in get_news():
                title = n.get("headline")
                url = n.get("url")

                if not title or not url:
                    continue

                nid = news_id(title)
                if nid in sent_news:
                    continue

                impact = news_impact(title)
                if impact < 2:
                    continue

                analysis, emoji = smart_analysis(title)
                opportunity = detect_opportunity(analysis, impact)
                ar = smart_translate(title)
                ticker = extract_ticker(title)

                msg = (
                    f"{emoji} خبر جديد\n\n"
                    f"{market}\n"
                    f"━━━━━━━━━━━━━━\n\n"
                    f"🏢 {ticker if ticker else 'عام'}\n"
                    f"📊 {analysis}\n"
                    f"💰 {opportunity}\n\n"
                    f"📰 {title}\n\n"
                    f"🇸🇦 {ar}\n\n"
                    f"🔗 {url}"
                )

                for chat_id in CHAT_IDS:
                    await bot.send_message(chat_id=chat_id, text=msg)

                sent_news.add(nid)
                await asyncio.sleep(2)

            # ===== Top Movers =====
            for symbol, price, change in get_top_movers():

                mid = f"{symbol}_{round(change)}"
                if mid in sent_movers:
                    continue

                sent_movers.add(mid)

                direction = "📈 صعود قوي" if change > 0 else "📉 هبوط قوي"
                emoji = "🚀" if change > 0 else "🔻"
                risk = "⚠️ Penny Stock" if price < 1 else ""

                msg = (
                    f"{emoji} سهم قوي يتحرك\n\n"
                    f"🏢 {symbol}\n"
                    f"{direction}\n"
                    f"📊 {change}%\n"
                    f"{risk}\n\n"
                    f"💰 فرصة محتملة"
                )

                for chat_id in CHAT_IDS:
                    await bot.send_message(chat_id=chat_id, text=msg)

                await asyncio.sleep(2)

            # تنظيف
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