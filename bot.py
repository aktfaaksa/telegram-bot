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

# ====== الأسهم ======
WATCHLIST = ["TSLA", "NVDA", "AAPL"]

TICKER_MAP = {
    "tesla": "TSLA",
    "nvidia": "NVDA",
    "apple": "AAPL"
}

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
    t = title.lower()

    for symbol in WATCHLIST:
        if symbol.lower() in t:
            return symbol

    for name, symbol in TICKER_MAP.items():
        if name in t:
            return symbol

    return None

# ====== ترجمة ذكية ======
def smart_translate(title):
    t = title.lower()

    if "earnings" in t and "beat" in t:
        return "أرباح أعلى من التوقعات (إيجابي 📈)"
    if "miss" in t:
        return "أرباح أقل من المتوقع (سلبي 📉)"
    if "surge" in t or "soar" in t:
        return "ارتفاع قوي (إيجابي 📈)"
    if "crash" in t or "plunge" in t:
        return "هبوط حاد (سلبي 📉)"
    if "fed" in t:
        return "خبر عن الفيدرالي (تأثير على السوق)"

    try:
        return GoogleTranslator(source='auto', target='ar').translate(title)
    except:
        return title

# ====== تحليل بسيط ======
def simple_analysis(title):
    t = title.lower()

    if "earnings" in t and "beat" in t:
        return "📈 إشارة إيجابية قوية"
    if "miss" in t:
        return "📉 إشارة سلبية"
    if "surge" in t or "soar" in t:
        return "🚀 زخم صعود"
    if "crash" in t or "plunge" in t:
        return "⚠️ ضغط هبوطي"

    return "⚖️ تأثير غير واضح"

# ====== تقييم الخبر ======
def news_impact(title):
    t = title.lower()
    score = 0

    if any(w in t for w in ["earnings", "revenue", "forecast"]):
        score += 4
    if any(w in t for w in ["fed", "inflation", "interest rate"]):
        score += 3
    if any(w in t for w in ["acquire", "merge", "lawsuit"]):
        score += 3
    if any(w in t for w in ["surge", "plunge", "crash", "soar"]):
        score += 2

    return score

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

# ====== حالة السوق ======
def market_status():
    _, spy_change = get_price("SPY")
    _, qqq_change = get_price("QQQ")

    if spy_change is not None and qqq_change is not None:
        if spy_change > 0 and qqq_change > 0:
            return "📈 السوق صاعد"
        elif spy_change < 0 and qqq_change < 0:
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

                if ticker and ticker not in WATCHLIST:
                    continue

                impact = news_impact(title)

                if impact < 2:
                    continue

                if impact >= 5:
                    prefix = "🚨 تنبيه قوي\n"
                elif impact >= 3:
                    prefix = "⚠️ تنبيه متوسط\n"
                else:
                    prefix = ""

                ar = smart_translate(title)
                analysis = simple_analysis(title)

                msg = (
                    f"{prefix}"
                    f"{market}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"🏢 {ticker if ticker else 'عام'}\n\n"
                    f"📰 {title}\n"
                    f"🇸🇦 {ar}\n\n"
                    f"📊 {analysis}\n\n"
                    f"🔗 {url}"
                )

                for chat_id in CHAT_IDS:
                    try:
                        await bot.send_message(chat_id=chat_id, text=msg)
                    except Exception as e:
                        print(f"فشل الإرسال: {e}")

                sent_news.add(nid)
                save_news()

                await asyncio.sleep(2)

            print("يتم التحديث...")
            await asyncio.sleep(15)

        except Exception as e:
            print("خطأ عام:", e)
            await asyncio.sleep(10)

# ====== تشغيل ======
if __name__ == "__main__":
    asyncio.run(main())