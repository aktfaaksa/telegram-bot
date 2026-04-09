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

    positive = {
        "surge": 3, "soar": 3, "beat": 4,
        "growth": 2, "record": 3, "strong": 2
    }

    negative = {
        "miss": -4, "lower": -3, "drop": -2,
        "crash": -5, "plunge": -4, "weak": -2
    }

    macro_negative = ["inflation", "risk", "crisis", "war"]
    macro_positive = ["growth", "stability", "holds"]

    for word, val in positive.items():
        if word in t:
            score += val
            confidence += 1

    for word, val in negative.items():
        if word in t:
            score += val
            confidence += 1

    for w in macro_negative:
        if w in t:
            score -= 2
            confidence += 1

    for w in macro_positive:
        if w in t:
            score += 1

    if score >= 4:
        label = "🚀 إيجابي قوي"
        emoji = "🟢"
    elif score >= 2:
        label = "📈 إيجابي"
        emoji = "🟢"
    elif score <= -4:
        label = "📉 سلبي قوي"
        emoji = "🔴"
    elif score <= -2:
        label = "⚠️ سلبي"
        emoji = "🔴"
    else:
        label = "⚖️ متضارب"
        emoji = "⚪"

    if confidence >= 3:
        conf = "🔵 ثقة عالية"
    elif confidence == 2:
        conf = "🟡 ثقة متوسطة"
    else:
        conf = "⚪ ثقة ضعيفة"

    return f"{label} | {conf}", emoji

# ====== تقييم الخبر ======
def news_impact(title):
    t = title.lower()
    score = 0

    if any(w in t for w in ["earnings", "revenue", "forecast"]):
        score += 4
    if any(w in t for w in ["fed", "inflation", "interest rate"]):
        score += 3
    if any(w in t for w in ["acquire", "merge", "deal"]):
        score += 3
    if any(w in t for w in ["surge", "plunge", "crash"]):
        score += 2

    return score

# ====== كشف الفرص ======
def detect_opportunity(analysis, impact):
    if "🚀 إيجابي قوي" in analysis and impact >= 4:
        return "💰💥 فرصة قوية"
    elif "📈 إيجابي" in analysis and impact >= 3:
        return "💰 فرصة محتملة"
    elif "⚠️ سلبي" in analysis:
        return "🚫 تجنب"
    elif "📉 سلبي قوي" in analysis:
        return "🚫 خطر عالي"
    else:
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

# ====== التشغيل ======
async def main():
    while True:
        try:
            news_list = get_news()
            market = market_status()

            for n in news_list:
                title = n.get("headline")
                url = n.get("url")

                if not title or not url:
                    continue

                nid = news_id(title)
                if nid in sent_news:
                    continue

                ticker = extract_ticker(title)
                impact = news_impact(title)

                # ===== SAFE MODE =====
                if ticker:
                    if impact < 1:
                        continue
                else:
                    if impact < 3:
                        continue

                # ===== تنبيه =====
                if impact >= 5:
                    prefix = "🚨 تنبيه قوي"
                elif impact >= 3:
                    prefix = "⚠️ تنبيه متوسط"
                else:
                    prefix = ""

                ar = smart_translate(title)
                analysis, emoji = smart_analysis(title)
                opportunity = detect_opportunity(analysis, impact)

                msg = (
                    f"{emoji} {prefix}\n\n"
                    f"{market}\n"
                    f"━━━━━━━━━━━━━━\n\n"

                    f"🏢 السهم: {ticker if ticker else 'عام'}\n"
                    f"📊 الاتجاه: {analysis}\n"
                    f"💰 الفرصة: {opportunity}\n\n"

                    f"📰 الخبر:\n{title}\n\n"
                    f"🇸🇦 الترجمة:\n{ar}\n\n"

                    f"━━━━━━━━━━━━━━\n"
                    f"🔗 المصدر:\n{url}"
                )

                for chat_id in CHAT_IDS:
                    try:
                        await bot.send_message(chat_id=chat_id, text=msg)
                    except Exception as e:
                        print("خطأ إرسال:", e)

                sent_news.add(nid)
                save_news()

                await asyncio.sleep(2)

            print("يتم التحديث...")
            await asyncio.sleep(15)

        except Exception as e:
            print("خطأ عام:", e)
            await asyncio.sleep(10)

# ===== تشغيل =====
if __name__ == "__main__":
    asyncio.run(main())