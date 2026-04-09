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

# ====== منع التكرار ======
def news_id(title):
    return hashlib.md5(title.lower()[:60].encode()).hexdigest()

def load_news():
    try:
        with open("sent.json", "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_news():
    with open("sent.json", "w") as f:
        json.dump(list(sent_news), f)

sent_news = load_news()

# ====== استخراج السهم ======
def extract_ticker(title):
    words = title.split()
    for w in words:
        if w.isupper() and 2 <= len(w) <= 5:
            return w
    return None

# ====== ترجمة ======
def smart_translate(title):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(title)
    except:
        return title

# ====== تحليل ذكي ======
def smart_analysis(title):
    t = title.lower()
    score = 0
    confidence = 0

    positive = {"surge":3,"soar":3,"beat":4,"growth":2,"record":3}
    negative = {"miss":-4,"lower":-3,"drop":-2,"crash":-5,"plunge":-4}

    for word,val in positive.items():
        if word in t:
            score += val
            confidence += 1

    for word,val in negative.items():
        if word in t:
            score += val
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

    if confidence >= 2:
        conf = "🔵 ثقة عالية"
    else:
        conf = "⚪ ثقة ضعيفة"

    return f"{label} | {conf}", emoji

# ====== تقييم الخبر ======
def news_impact(title):
    t = title.lower()
    score = 0

    if any(w in t for w in ["earnings","revenue","forecast"]):
        score += 4
    if any(w in t for w in ["fed","inflation"]):
        score += 3
    if any(w in t for w in ["surge","plunge","crash"]):
        score += 2

    return score

# ====== الفرص ======
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
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    try:
        return requests.get(url, timeout=5).json()
    except:
        return []

# ====== Top Movers ======
def get_top_movers():
    try:
        url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={API_KEY}"
        symbols = requests.get(url, timeout=5).json()

        movers = []

        for s in symbols[:20]:
            symbol = s.get("symbol")
            price, change = get_price(symbol)

            if price and change:
                if abs(change) >= 5:
                    movers.append((symbol, change))

        return movers[:3]
    except:
        return []

# ====== التشغيل ======
async def main():
    while True:
        try:
            market = market_status()
            news_list = get_news()

            # ===== الأخبار =====
            for n in news_list:
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
                save_news()

                await asyncio.sleep(2)

            # ===== Top Movers =====
            movers = get_top_movers()

            for symbol, change in movers:

                direction = "📈 صعود قوي" if change > 0 else "📉 هبوط قوي"
                emoji = "🚀" if change > 0 else "🔻"

                msg = (
                    f"{emoji} سهم يتحرك بقوة\n\n"
                    f"🏢 {symbol}\n"
                    f"{direction}\n"
                    f"📊 {change}%\n\n"
                    f"💰 فرصة محتملة"
                )

                for chat_id in CHAT_IDS:
                    await bot.send_message(chat_id=chat_id, text=msg)

                await asyncio.sleep(2)

            print("يتم التحديث...")
            await asyncio.sleep(20)

        except Exception as e:
            print("خطأ:", e)
            await asyncio.sleep(10)

# ===== تشغيل =====
if __name__ == "__main__":
    asyncio.run(main())