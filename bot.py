import requests
import asyncio
import json
import hashlib
import os
import feedparser
from datetime import datetime, timedelta
from telegram import Bot
from deep_translator import GoogleTranslator

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("FINNHUB_API_KEY")

bot = Bot(token=TOKEN)

WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY", "QQQ"]

KEYWORDS = [
    "earnings","revenue","profit","loss","forecast",
    "surge","crash","drop","merge","acquire",
    "upgrade","downgrade","inflation","fed",
    "interest rate","economy"
]

# ====== منع تكرار ======
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

# ====== تنظيف الرابط ======
def clean_url(url):
    if not url:
        return None

    if "finnhub.io" in url:
        return None

    if "news.google.com" in url:
        try:
            r = requests.get(url, allow_redirects=True, timeout=5)
            if r.url:
                return r.url
        except:
            return None

    return url

# ====== المصدر ======
def extract_source(title):
    if "-" in title:
        return title.split("-")[-1].strip()
    return "Unknown"

# ====== Yahoo ======
def get_yahoo_news():
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY,QQQ,AAPL,MSFT,NVDA,AMZN,GOOGL"
    feed = feedparser.parse(url)

    news = []
    for e in feed.entries:
        news.append({
            "headline": e.title,
            "url": e.link,
            "datetime": int(datetime.utcnow().timestamp())
        })
    return news

# ====== Finnhub ======
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

# ====== تصنيف ======
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

# ====== التشغيل ======
async def main():
    while True:
        try:
            all_news = []
            titles_seen = set()

            _, spy = get_price("SPY")
            _, qqq = get_price("QQQ")
            market_status = market(spy, qqq)

            all_news.extend(get_general_news())
            all_news.extend(get_yahoo_news())

            all_news = sorted(all_news, key=lambda x: x.get("datetime", 0), reverse=True)

            count = 0

            for n in all_news:
                if count >= 5:
                    break

                title = n.get("headline")
                url = clean_url(n.get("url"))

                if not title or not url:
                    continue

                if title.lower()[:60] in titles_seen:
                    continue
                titles_seen.add(title.lower()[:60])

                nid = news_id(title)
                if nid in sent_news:
                    continue

                if not any(k in title.lower() for k in KEYWORDS):
                    continue

                tag = classify(title)
                sent = sentiment(title)
                source = extract_source(title)

                try:
                    ar = GoogleTranslator(source='auto', target='ar').translate(title)
                except:
                    ar = title

                time_str = datetime.fromtimestamp(n["datetime"]).strftime('%H:%M')

                msg = (
                    f"{market_status}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"{tag} | {sent}\n\n"
                    f"📰 {ar}\n\n"
                    f"🌐 {source} | 🕒 {time_str}\n"
                    f"🔗 {url}"
                )

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