# ===== Alpha Market Intelligence v29.6 | Clean Pro Engine 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

# ✅ الشخص الثاني مضاف
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
    "watch","story","milestone","invest","cramer","buffett"
]

GEO = [
    "war","conflict","sanctions","china","russia",
    "military","oil","iran","israel","ukraine",
    "fed","interest rates","inflation"
]

GEO_STRONG = [
    "attack","strike","ceasefire","agreement",
    "sanctions","decision","announces","conflict escalates",
    "deal reached","truce"
]

GEO_BAD = [
    "why","best","top","stock","buy","invest",
    "cramer","buffett","opinion","analysis",
    "long-term","what’s next","could","should"
]

# ===== FUNCTIONS =====

def is_geo(title):
    t = title.lower()

    if any(x in t for x in GEO_BAD):
        return False

    if any(x in t for x in GEO_STRONG) and any(x in t for x in GEO):
        return True

    return False


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


# ===== STOCK DATA =====
async def stock(session, s):
    try:
        async with session.get(
            f"https://finnhub.io/api/v1/quote?symbol={s}&token={API_KEY}"
        ) as r:
            return await r.json()
    except:
        return {}


async def volume(session, s):
    try:
        now = int(time.time())
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={s}&resolution=D&from={now-86400*5}&to={now}&token={API_KEY}"
        async with session.get(url) as r:
            d = await r.json()
        v = d.get("v", [])
        if len(v) < 2:
            return 0, 0
        return v[-1], sum(v[:-1]) / len(v[:-1])
    except:
        return 0, 0


# ===== GEO =====
async def send_geo(session, n):
    global last_geo_time

    title, link = n["title"], n["link"]

    if not is_geo(title):
        return

    # ⏱️ cooldown 15 دقيقة
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

⚠️ راقب السوق

🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)


# ===== NEWS =====
async def send_news(session, n):
    title, link = n["title"], n["link"]

    h = hashlib.md5((title + link).encode()).hexdigest()
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
    price = st.get("c", 0)
    change = st.get("dp", 0)

    if price == 0:
        return

    cur, avg = await volume(session, s)
    vol_ratio = (cur / avg) if avg > 0 else 1

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


# ===== SEC =====
async def load_cik(session):
    async with session.get(SEC_URL, headers=SEC_HEADERS) as r:
        data = await r.json()
    return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}


async def send_sec(session, cik_map):
    today = time.strftime("%Y-%m-%d")

    for s, cik in list(cik_map.items())[:100]:
        try:
            async with session.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=SEC_HEADERS
            ) as r:
                d = await r.json()
        except:
            continue

        text = str(d).lower()

        # ✅ فلترة ذكية
        if not any(x in text for x in ["earnings","acquisition","merger","ceo","agreement"]):
            continue

        f = d.get("filings", {}).get("recent", {})

        for i in range(len(f.get("form", []))):
            if f["form"][i] != "8-K":
                continue

            if f["filingDate"][i] != today:
                continue

            key = f"{s}_{f['accessionNumber'][i]}"
            if key in sent_sec:
                continue

            sent_sec.add(key)

            msg = f"""🚨 إعلان رسمي مهم

🏢 {s}
📄 8-K Filing

⚡ حدث مهم (Earnings / CEO / Deal)

🔗 https://www.sec.gov
"""

            for c in CHAT_IDS:
                await bot.send_message(chat_id=c, text=msg)

            break


# ===== MAIN =====
async def main():
    print("🚀 v29.6 CLEAN PRO RUNNING")

    async with aiohttp.ClientSession() as session:
        cik_map = await load_cik(session)

        # رسالة تشغيل
        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت يعمل الآن (v29.6)")

        while True:
            try:
                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title": e.title, "link": e.link})

                for n in feed:
                    await send_news(session, n)

                # 🔥 SEC رجعناه
                await send_sec(session, cik_map)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())