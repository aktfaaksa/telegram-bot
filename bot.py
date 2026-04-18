# ===== Alpha Market Intelligence v30+ FINAL 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG =====
TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=TOKEN)

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ✅ الإيميل مضاف (نهائي)
SEC_HEADERS = {
    "User-Agent": "AlphaMarketBot/1.0 (aktfaaksa@gmail.com)"
}

# ===== STATE =====
sent = set()
sent_sec = set()
last_sent_symbol = {}
last_geo_time = 0

# ===== KEYWORDS =====
STRONG = ["earnings","merger","acquisition","deal","contract","fda","approval"]
WEAK = ["analysis","why","opinion","watch"]

GEO = ["iran","russia","china","war","oil","fed","inflation"]
GEO_STRONG = ["attack","strike","sanctions","decision","agreement"]
GEO_BAD = ["analysis","opinion","why"]

# ===== UTIL =====
def tr(x):
    try:
        if len(x) > 400:
            return x
        return GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

def can_send(symbol):
    now = time.time()
    if symbol in last_sent_symbol and now - last_sent_symbol[symbol] < 1800:
        return False
    last_sent_symbol[symbol] = now
    return True

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

# ===== GEO =====
def is_geo(title):
    t = title.lower()
    if any(x in t for x in GEO_BAD):
        return False
    return any(x in t for x in GEO) and any(x in t for x in GEO_STRONG)

def geo_impact(title):
    t = title.lower()
    if any(x in t for x in ["iran","oil","middle east"]):
        return "🛢️ النفط ↑"
    if any(x in t for x in ["fed","inflation"]):
        return "💰 الفائدة / السوق"
    if any(x in t for x in ["china","trade"]):
        return "📦 التجارة"
    return "📊 عام"

async def send_geo(n):
    global last_geo_time
    if time.time() - last_geo_time < 1800:
        return

    title, link = n["title"], n["link"]

    if not is_geo(title):
        return

    last_geo_time = time.time()

    msg = f"""🌍 حدث جيوسياسي مهم

📰 {title}
🇸🇦 {tr(title)}

{geo_impact(title)}

⚠️ راقب السوق
🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== AI =====
def ai_analyze(text):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "openai/gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": f"""
حلل هذا التقرير المالي واطلع أهم النقاط:

- نوع الحدث
- أهم الأرقام
- التأثير

واكتب ملخص عربي مختصر:

{text[:2000]}
"""
            }]
        }

        r = requests.post(url, headers=headers, json=data, timeout=20)
        return r.json()["choices"][0]["message"]["content"]

    except:
        return None

# ===== STOCK =====
async def stock(session, s):
    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={s}&token={FINNHUB}") as r:
            return await r.json()
    except:
        return {}

# ===== NEWS =====
async def send_news(session, n):
    title, link = n["title"], n["link"]

    h = hashlib.md5((title + link).encode()).hexdigest()
    if h in sent:
        return
    sent.add(h)

    await send_geo(n)

    level = classify(title)
    if level == "LOW":
        return

    s = symbol(title)
    if not s or not can_send(s):
        return

    st = await stock(session, s)
    price = st.get("c", 0)
    change = st.get("dp", 0)

    if price == 0:
        return

    msg = f"""{"🚨 فرصة" if level=="HIGH" else "🟡 متابعة"}

🏢 {s}

📰 {title}
🇸🇦 {tr(title)}

📊 {price}$ | {round(change,2)}%

🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== SEC =====
CIK_URL = "https://www.sec.gov/files/company_tickers.json"

async def load_cik(session):
    async with session.get(CIK_URL, headers=SEC_HEADERS) as r:
        data = await r.json()
    return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}

async def send_sec(session, cik_map):
    today = time.strftime("%Y-%m-%d")

    for ticker, cik in list(cik_map.items())[:50]:
        try:
            async with session.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=SEC_HEADERS
            ) as r:
                d = await r.json()
        except:
            continue

        filings = d.get("filings", {}).get("recent", {})

        for i in range(len(filings.get("form", []))):
            form = filings["form"][i]

            if form not in ["8-K", "3", "4"]:
                continue

            if filings["filingDate"][i] != today:
                continue

            key = f"{ticker}_{filings['accessionNumber'][i]}"
            if key in sent_sec:
                continue

            sent_sec.add(key)

            text = str(d)[:2000]

            summary = ai_analyze(text)
            if not summary:
                continue

            msg = f"""🏛️ SEC مهم

🏢 {ticker}
📄 Form {form}

{summary}

🔗 https://www.sec.gov
"""

            for c in CHAT_IDS:
                await bot.send_message(chat_id=c, text=msg)

            break

# ===== SYSTEM =====
async def startup():
    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text="✅ البوت يعمل (v30+)")

async def heartbeat():
    while True:
        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="🟢 النظام مستقر")
        await asyncio.sleep(3600)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v30+")

    async with aiohttp.ClientSession() as session:
        cik_map = await load_cik(session)

        await startup()
        asyncio.create_task(heartbeat())

        while True:
            try:
                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title": e.title, "link": e.link})

                for n in feed:
                    try:
                        await send_news(session, n)
                    except:
                        pass

                await send_sec(session, cik_map)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())