# ===== Alpha Market Intelligence v28 HYBRID + SEC =====

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

# ===== SEC =====
SEC_HEADERS = {
    "User-Agent": "AlphaMarketBot aktfaaksa@gmail.com"
}

SEC_URL = "https://www.sec.gov/files/company_tickers.json"

# ===== تنظيف =====
BAD = ["will","should","could","how","why","top","best"]

def clean(title):
    return any(x in title.lower() for x in BAD)

# ===== استخراج السهم =====
def symbol(title):
    m = re.findall(r'\(([A-Z]{1,5})\)', title.upper())
    return m[0] if m else None

# ===== ترجمة =====
def tr(x):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

# ===== Finnhub =====
async def stock(session, s):
    try:
        async with session.get(
            f"https://finnhub.io/api/v1/quote?symbol={s}&token={API_KEY}"
        ) as r:
            return await r.json()
    except:
        return {}

# ===== Volume =====
async def volume(session, s):
    try:
        now = int(time.time())
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={s}&resolution=D&from={now-86400*5}&to={now}&token={API_KEY}"
        async with session.get(url) as r:
            d = await r.json()
        v = d.get("v", [])
        if len(v) < 2: return 0,0
        return v[-1], sum(v[:-1])/len(v[:-1])
    except:
        return 0,0

# ===== SEC LOAD =====
async def load_cik(session):
    try:
        async with session.get(SEC_URL, headers=SEC_HEADERS) as r:
            data = await r.json()
        return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}
    except:
        return {}

# ===== SEC SEND =====
async def send_sec(session, cik_map):
    today = time.strftime("%Y-%m-%d")

    for s, cik in list(cik_map.items())[:200]:  # limit
        try:
            async with session.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=SEC_HEADERS
            ) as r:
                d = await r.json()
        except:
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

            msg = f"""🚨 إعلان رسمي

🏢 {s}
📄 8-K Filing

🔗 https://www.sec.gov
"""

            for c in CHAT_IDS:
                await bot.send_message(chat_id=c, text=msg)

            break

# ===== NEWS =====
async def send_news(session, n):
    title, link = n["title"], n["link"]

    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent: return
    sent.add(h)

    if clean(title): return

    s = symbol(title)
    if not s: return

    st = await stock(session, s)
    price = st.get("c",0)
    change = st.get("dp",0)

    # ===== فلترة =====
    if price == 0 or abs(change) < 1.5 or price < 2:
        return

    cur, avg = await volume(session, s)
    if avg > 0 and cur < avg*1.5:
        return

    msg = f"""🔥 فرصة

📰 {title}
🇸🇦 {tr(title)}

📊 {s} | {price}$ | {round(change,2)}%
📈 فوليوم عالي

🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
async def main():
    print("🚀 v28 HYBRID + SEC RUNNING")

    async with aiohttp.ClientSession() as session:
        cik_map = await load_cik(session)

        while True:
            try:
                # NEWS
                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title":e.title,"link":e.link})

                for n in feed:
                    await send_news(session, n)

                # SEC
                await send_sec(session, cik_map)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())