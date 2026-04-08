import requests
import asyncio
import json
import hashlib
import os
import feedparser
from datetime import datetime, timedelta
from telegram import Bot
from deep_translator import GoogleTranslator

# ====== بيانات ======
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY", "QQQ"]

COMPANY_NAMES = {
    "AAPL": "apple",
    "MSFT": "microsoft",
    "NVDA": "nvidia",
    "AMZN": "amazon",
    "GOOGL": "google"
}

# ====== فلترة متوسطة ======
KEYWORDS = [
    "earnings","revenue","profit","loss","forecast",
    "surge","crash","drop","merge","acquire",
    "upgrade","downgrade","inflation","fed",
    "interest rate","economy"
]

# ====== منع تكرار ======
def news_id(title):
    t = title.lower().replace("breaking:", "").strip()
    return hashlib.md5(t[:60].encode()).hexdigest()

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

# ====== Yahoo ======
def get_yahoo_news():
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY,QQQ,AAPL,MSFT,NVDA,AMZN,GOOGL&region=US&lang=en-US"
    feed = feedparser.parse(url)

    news_list = []
    for entry in feed.entries:
        news_list.append({
            "headline": entry.title,
            "url": entry.link,
            "datetime": int(datetime.utcnow().timestamp())
        })
    return news_list

# ====== Finnhub ======
def get_stock_news(symbol):
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={yesterday.date()}&to={today.date()}&token={API_KEY}"
    try:
        return requests.get(url).json()
    except:
        return []

def get_general_news():
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    try:
        return requests.get(url).json()
    except:
        return []

# ====== تحليل ======
def sentiment(title):
    t = title.lower()
    if "surge" in t or "profit" in t:
        return "🟢 إيجابي"
    elif "crash" in t or "loss" in t:
        return "🔴 سلبي"
    return "⚪ عادي"

# ====== تصنيف 🔥 ======
def classify(title):
    t = title.lower()

    if "fed" in t or "inflation" in t:
        return "🏦 اقتصادي"
    if "earnings" in t:
        return "📊 نتائج"
    if "crash" in t:
        return "🚨 خطر"
    if "surge" in t:
        return "🔥 قوي"

    return "📰 خبر"

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
            titles_seen = set()

            _, spy = get_price("SPY")
            _, qqq = get_price("QQQ")
            market_status = market(spy, qqq)

            # Finnhub
            for s in WATCHLIST:
                news = get_stock_news(s)
                for n in news:
                    title = n.get("headline", "").lower()
                    company_name = COMPANY_NAMES.get(s, "").lower()

                    if company_name and company_name in title:
                        n["symbol"] = s
                        all_news.append(n)

            all_news.extend(get_general_news())
            all_news.extend(get_yahoo_news())

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

                # تحويل Google → مباشر
                if url and "news.google.com" in url:
                    try:
                        r = requests.get(url, allow_redirects=True)
                        url = r.url
                    except:
                        pass

                clean = title.lower()[:60]
                if clean in titles_seen:
                    continue
                titles_seen.add(clean)

                nid = news_id(title)
                if nid in sent_news:
                    continue

                if not any(k in title.lower() for k in KEYWORDS):
                    continue

                s = sentiment(title)
                tag = classify(title)

                price_text = ""
                sig = ""

                if symbol:
                    price, change = get_price(symbol)
                    if price:
                        price_text = f"💰 {price}$ | {change}%"

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

{tag}

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