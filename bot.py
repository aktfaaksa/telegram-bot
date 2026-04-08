import requests
import asyncio
import json
import hashlib
import os
from datetime import datetime, timedelta
from telegram import Bot
from deep_translator import GoogleTranslator

# ====== بياناتك (من Render) ======
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

# ====== الأسهم القيادية ======
WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY", "QQQ"]

# ====== أسماء الشركات ======
COMPANY_NAMES = {
    "AAPL": "apple",
    "MSFT": "microsoft",
    "NVDA": "nvidia",
    "AMZN": "amazon",
    "GOOGL": "google"
}

# ====== كلمات ======
KEYWORDS = [
    "earnings","revenue","profit","loss","guidance","forecast",
    "surge","crash","drop","fall","merge","acquire",
    "upgrade","downgrade","inflation","interest rate","fed",
    "oil","war","economy","market"
]

STRONG_KEYWORDS = [
    "earnings","surge","crash","fed","inflation"
]

# ====== بصمة الخبر ======
def news_id(title):
    return hashlib.md5(title.lower().encode()).hexdigest()

# ====== تحميل ======
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

# ====== API ======
def safe_request(url):
    try:
        data = requests.get(url).json()
        if isinstance(data, list):
            return data
        return []
    except:
        return []

def get_stock_news(symbol):
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={yesterday.date()}&to={today.date()}&token={API_KEY}"
    return safe_request(url)

def get_general_news():
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    return safe_request(url)

# ====== تحليل ======
def sentiment(title):
    t = title.lower()
    if "surge" in t or "profit" in t:
        return "🟢 إيجابي"
    elif "crash" in t or "loss" in t:
        return "🔴 سلبي"
    return ""

def is_important(title):
    return any(k in title.lower() for k in KEYWORDS)

def is_strong(title):
    return any(k in title.lower() for k in STRONG_KEYWORDS)

# ====== سعر ======
def get_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        d = requests.get(url).json()

        c = d.get("c")
        pc = d.get("pc")

        if c and pc:
            change = ((c - pc) / pc) * 100
            return c, round(change, 2)
    except:
        pass
    return None, None

# ====== السوق ======
def market(spy, qqq):
    if spy and qqq:
        if spy > 0 and qqq > 0:
            return "📈 السوق صاعد"
        elif spy < 0 and qqq < 0:
            return "📉 السوق هابط"
    return "⚖️ السوق متذبذب"

# ====== تشغيل ======
async def main():
    while True:
        try:
            all_news = []

            # السوق
            _, spy = get_price("SPY")
            _, qqq = get_price("QQQ")
            market_status = market(spy, qqq)

            # أخبار الأسهم
            for s in WATCHLIST:
                news = get_stock_news(s)

                for n in news:
                    title = n.get("headline", "").lower()
                    company_name = COMPANY_NAMES.get(s, "").lower()

                    if company_name and company_name in title:
                        n["symbol"] = s
                        all_news.append(n)

            # أخبار عامة
            all_news.extend(get_general_news())

            # ترتيب
            all_news = sorted(all_news, key=lambda x: x.get("datetime", 0), reverse=True)

            count = 0

            for n in all_news:
                if count >= 5:
                    break

                title = n.get("headline")
                url = n.get("url")
                symbol = n.get("symbol", "")

                if not title:
                    continue

                nid = news_id(title)
                if nid in sent_news:
                    continue

                if not is_important(title):
                    continue

                if not is_strong(title):
                    continue

                s = sentiment(title)

                price_text = ""
                change = None

                if symbol:
                    price, change = get_price(symbol)
                    if price:
                        price_text = f"💰 {price}$ | {change}%"

                sig = ""
                if change:
                    if change > 5:
                        sig = "🔥 فرصة"
                    elif change < -5:
                        sig = "🚨 خطر"

                time = datetime.fromtimestamp(n["datetime"]).strftime('%H:%M')

                try:
                    ar = GoogleTranslator(source='auto', target='ar').translate(title)
                except:
                    ar = title

                msg = f"""
{market_status}

{f"📈 {symbol}" if symbol else ""}

{price_text}

{s} {sig}

📰 {ar}
🌐 {title}

🕒 {time}

🔗 {url}
"""

                msg = msg.replace("\n\n\n", "\n\n")

                await bot.send_message(chat_id=CHAT_ID, text=msg)

                sent_news.add(nid)
                save_news()

                count += 1
                await asyncio.sleep(2)

            print("يتم التحديث...")
            await asyncio.sleep(60)

        except Exception as e:
            print("خطأ:", e)
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
    # update