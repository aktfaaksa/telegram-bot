# ===== Alpha Market Intelligence v43 (Elite Stable) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests
from telegram import Bot
from deep_translator import GoogleTranslator
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

SEC_HEADERS = {
    "User-Agent": "AlphaBot/3.0 (aktfaaksa@gmail.com)"
}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent = set()
sent_sec = set()
cooldown = {}
last_geo = 0
active_stocks = set()

MAX_SEC_PER_CYCLE = 2

# ===== FILTERS =====
STRONG = ["earnings","revenue","guidance","forecast",
          "fda","approval","acquisition","merger",
          "deal","upgrade","downgrade","beats","misses"]

WEAK = ["this year","skyrocket","surges","climbs","boom",
        "expansion","growth","outlook","rally"]

TRASH = ["which","should you","vs","analysis","opinion",
         "announces","launches"]

# ===== UTIL =====
def tr(x):
    try:
        return x if len(x) > 300 else GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

def extract_symbol(t):
    m = re.findall(r'\(([A-Z]{1,5})\)', t)
    return m[0] if m else None

def can_send(sym):
    now = time.time()
    if sym in cooldown and now - cooldown[sym] < 1800:
        return False
    cooldown[sym] = now
    return True

# ===== GEO =====
def geo_score(t):
    t = t.lower()

    if any(x in t for x in ["warn","experts","says","analysis","hope"]):
        return 0

    score = 0
    if any(x in t for x in ["war","attack","strike","missile"]): score += 4
    if any(x in t for x in ["oil","hormuz"]): score += 3
    if any(x in t for x in ["iran","russia","china"]): score += 2

    return score

def geo_level(s):
    return "🔴 عالي" if s >= 5 else "🟡 متوسط" if s >= 3 else None

async def send_geo(n):
    global last_geo

    score = geo_score(n["title"])
    lvl = geo_level(score)

    if not lvl or time.time() - last_geo < 1800:
        return

    last_geo = time.time()

    msg = f"""🌍 حدث مهم

📰 {n["title"]}
🇸🇦 {tr(n["title"])}

⚡️ {lvl}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== AI =====
def ai(text):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER}"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"""
👤 الاسم
📊 شراء أو بيع
💰 العدد (إن وجد)
⚡️ إيجابي أو سلبي

{text[:1200]}
"""
                }]
            },
            timeout=10
        )
        return r.json()["choices"][0]["message"]["content"]
    except:
        return None

# ===== NEWS =====
async def send_news(session, n):
    title = n["title"].lower()

    if any(x in title for x in WEAK): return
    if any(x in title for x in TRASH): return
    if not any(x in title for x in STRONG): return

    key = hashlib.md5((n["title"] + n["link"]).encode()).hexdigest()
    if key in sent: return
    sent.add(key)

    await send_geo(n)

    symbol = extract_symbol(n["title"])
    if not symbol or not can_send(symbol): return

    active_stocks.add(symbol)

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    if not d.get("c"): return

    msg = f"""🟢 خبر قوي

🏢 {symbol}
📰 {n["title"]}
🇸🇦 {tr(n["title"])}

📊 {d['c']}$ | {round(d['dp'],2)}%
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== SEC =====
async def send_sec(session):
    if not active_stocks: return

    today = datetime.utcnow().date()
    count = 0

    for ticker in list(active_stocks)[:10]:

        try:
            async with session.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS) as r:
                tickers = await r.json()

            cik = next((str(v["cik_str"]).zfill(10)
                        for v in tickers.values()
                        if v["ticker"] == ticker), None)

            if not cik: continue

            async with session.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                                   headers=SEC_HEADERS) as r:
                data = await r.json()

        except:
            continue

        filings = data.get("filings", {}).get("recent", {})

        for i in range(len(filings.get("form", []))):
            if filings["form"][i] != "4": continue
            if filings["filingDate"][i] != str(today): continue

            acc = filings["accessionNumber"][i]
            key = f"{ticker}_{acc}"
            if key in sent_sec: continue
            sent_sec.add(key)

            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{acc}.txt"

            try:
                async with session.get(url, headers=SEC_HEADERS) as r:
                    txt = await r.text()
            except:
                continue

            if any(x in txt.lower() for x in ["option","award","rsu","restricted"]):
                continue

            if not any(x in txt.lower() for x in ["buy","sale","purchase","sold"]):
                continue

            summary = ai(txt)
            if not summary: continue

            msg = f"""🏛️ SEC

🏢 {ticker}

{summary}
"""

            for c in CHAT_IDS:
                await bot.send_message(chat_id=c, text=msg)

            count += 1
            if count >= MAX_SEC_PER_CYCLE:
                return

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v43")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v43")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await send_news(session, {"title": e.title, "link": e.link})

                await send_sec(session)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())