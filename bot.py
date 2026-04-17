# ===== Alpha Market Intelligence v29.3 | Smart Geo Control 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time
from telegram import Bot
from deep_translator import GoogleTranslator

TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [CHAT_ID_MAIN, 6315087880]
bot = Bot(token=TOKEN)

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent = set()
sent_sec = set()
last_geo_time = 0

SEC_HEADERS = {
    "User-Agent": "AlphaMarketBot aktfaaksa@gmail.com"
}

SEC_URL = "https://www.sec.gov/files/company_tickers.json"

# ===== KEYWORDS =====
STRONG = [
    "earnings","acquisition","merger","contract","deal",
    "partnership","fda","approval","ai","nvidia","guidance"
]

WEAK = [
    "price target","rating","coverage","transcript",
    "investment","outlook","analysis","why","undervalued",
    "daily","wrap","stocks rise","could","beginning",
    "watch","story","milestone","invest"
]

GEO = [
    "war","conflict","sanctions","china","russia",
    "military","oil","iran","israel","ukraine",
    "fed","interest rates","inflation"
]

def is_geo(title):
    return any(x in title.lower() for x in GEO)

def classify(title):
    t = title.lower()
    if any(x in t for x in WEAK):
        return "LOW"
    if any(x in t for x in STRONG):
        return "HIGH"
    return "MED"

def symbol(title):
    m = re.findall(r'\(([A-Z]{1,5})\)', title.upper())
    return m[0] if m else None

def tr(x):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

# ===== GEO CONTROL =====
async def send_geo(session, n):
    global last_geo_time

    title, link = n["title"], n["link"]

    if not is_geo(title):
        return

    # ⏱️ cooldown 15 min
    if time.time() - last_geo_time < 900:
        return

    last_geo_time = time.time()

    msg = f"""🌍 حدث جيوسياسي مهم

📰 {title}
🇸🇦 {tr(title)}

💡 التأثير:
- السوق العام
- الطاقة / النفط
- تقلب عالي

⚠️ انتبه لحركة السوق

🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== STOCK =====
async def stock(session, s):
    try:
        async with session.get(
            f"https://finnhub.io/api/v1/quote?symbol={s}&token={API_KEY}"
        ) as r:
            return await r.json()
    except:
        return {}

# ===== VOLUME =====
async def volume(session, s):
    try:
        now = int(time.time())
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={s}&resolution=D&from={now-86400*5}&to={now}&token={API_KEY}"
        async with session.get(url) as r:
            d = await r.json()
        v = d.get("v", [])
        if len(v) < 2:
            return 0,0
        return v[-1], sum(v[:-1])/len(v[:-1])
    except:
        return 0,0

# ===== NEWS =====
async def send_news(session, n):
    title, link = n["title"], n["link"]

    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent:
        return
    sent.add(h)

    # 🌍 جيوسياسي
    await send_geo(session, n)

    level = classify(title)
    if level == "LOW":
        return

    s = symbol(title)
    if not s:
        return

    st = await stock(session, s)
    price = st.get("c",0)
    change = st.get("dp",0)

    if price == 0:
        return

    cur, avg = await volume(session, s)
    vol_ratio = (cur/avg) if avg > 0 else 1

    if level == "HIGH":
        if change < 1.5 or vol_ratio < 1.2:
            return
    elif level == "MED":
        if change < 0.8 or vol_ratio < 1.0:
            return

    msg = f"""{"🚨 فرصة فورية" if level=="HIGH" else "🟡 متابعة"}

🏢 {s}

📰 {title}
🇸🇦 {tr(title)}

📊 {price}$ | +{round(change,2)}%
📈 فوليوم: {round(vol_ratio,2)}x

💡 السبب:
- خبر {'قوي' if level=='HIGH' else 'متوسط'}

🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
async def main():
    print("🚀 v29.3 SMART GEO RUNNING")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت يعمل الآن (v29.3)")

        while True:
            try:
                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title":e.title,"link":e.link})

                for n in feed:
                    await send_news(session, n)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())