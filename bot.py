# ===== Alpha Market Intelligence v38 (Elite Clean) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

SEC_HEADERS = {
    "User-Agent": "AlphaBot/1.0 (aktfaaksa@gmail.com)"
}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ===== STATE =====
sent = set()
sent_sec = set()
cooldown = {}
last_geo = 0

# ===== FILTERS =====
BAD_NEWS = [
    "announces","launches","case study","initiative","expands",
    "best","top","why","report","partnership"
]

BIG_COMPANIES = [
    "apple","tesla","amazon","nvidia","microsoft","google","meta"
]

# ===== UTIL =====
def tr(x):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(x) if len(x) < 300 else x
    except:
        return x

def can_send(symbol):
    now = time.time()
    if symbol in cooldown and now - cooldown[symbol] < 1800:
        return False
    cooldown[symbol] = now
    return True

def extract_symbol(title):
    m = re.findall(r'\(([A-Z]{1,5})\)', title)
    return m[0] if m else None

# ===== GEO =====
def geo_score(title):
    t = title.lower()

    if any(x in t for x in BIG_COMPANIES):
        return 0

    score = 0
    if any(x in t for x in ["attack","strike","war","missile"]): score += 4
    if any(x in t for x in ["oil","hormuz","gas"]): score += 3
    if any(x in t for x in ["iran","russia","ukraine","middle east"]): score += 2
    if re.search(r'\d+%', t): score += 3
    if any(x in t for x in ["rally","crash","surge"]): score += 2

    return score

def geo_level(score):
    if score >= 6: return "🔴 عالي"
    if score >= 3: return "🟡 متوسط"
    return None

def geo_impact(title):
    t = title.lower()
    if any(x in t for x in ["oil","hormuz","iran","russia"]):
        return "🛢️ النفط / الطاقة"
    if "fed" in t:
        return "💰 الفائدة"
    return "📊 السوق"

async def send_geo(news):
    global last_geo

    score = geo_score(news["title"])
    level = geo_level(score)

    if not level or time.time() - last_geo < 1800:
        return

    last_geo = time.time()

    msg = f"""🌍 حدث مهم

📰 {news["title"]}
🇸🇦 {tr(news["title"])}

{geo_impact(news["title"])}
⚡️ {level}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== AI =====
def ai_analyze(text, form):
    try:
        if form == "4":
            prompt = f"""
Form 4 insider trading:

اكتب بهذا الشكل فقط:

👤 الاسم
📊 شراء أسهم (Insider Buy) أو بيع أسهم (Insider Sell)
💰 الرقم (إذا موجود فقط)
⚡️ إيجابي أو سلبي

قواعد:
- سطر واحد لكل معلومة
- بدون نقاط أو شرطات
- لا تكتب "العملية"
- لا تكتب شرح

{text[:1500]}
"""
        else:
            prompt = f"""
👤 الشخص
📊 الحدث
⚡️ التأثير

{text[:1500]}
"""

        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
        )

        return r.json()["choices"][0]["message"]["content"]

    except:
        return None

# ===== CLEAN OUTPUT =====
def clean(text):
    lines = text.split("\n")
    result = []

    for line in lines:
        line = line.strip()

        if not line or "غير" in line:
            continue

        if line.startswith("-"):
            line = line.replace("-", "").strip()

        if "العملية" in line:
            continue

        result.append(line)

    return "\n".join(result)

# ===== NEWS =====
async def send_news(session, news):
    title = news["title"]

    if any(x in title.lower() for x in BAD_NEWS):
        return

    key = hashlib.md5((title + news["link"]).encode()).hexdigest()
    if key in sent:
        return
    sent.add(key)

    await send_geo(news)

    symbol = extract_symbol(title)
    if not symbol or not can_send(symbol):
        return

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            data = await r.json()
    except:
        return

    if not data.get("c"):
        return

    msg = f"""🟡 خبر

🏢 {symbol}
📰 {title}
🇸🇦 {tr(title)}

📊 {data['c']}$ | {round(data['dp'],2)}%
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== SEC =====
async def send_sec(session):
    url = "https://data.sec.gov/submissions/CIK0000320193.json"

    try:
        async with session.get(url, headers=SEC_HEADERS) as r:
            data = await r.json()
    except:
        return

    ticker = data.get("tickers", ["AAPL"])[0]
    filings = data.get("filings", {}).get("recent", {})

    for i in range(len(filings.get("form", []))):
        form = filings["form"][i]

        if form != "4":
            continue

        accession = filings["accessionNumber"][i]

        key = f"{ticker}_{accession}"
        if key in sent_sec:
            continue
        sent_sec.add(key)

        acc = accession.replace("-", "")
        link = f"https://www.sec.gov/Archives/edgar/data/320193/{acc}/{accession}.txt"

        try:
            async with session.get(link, headers=SEC_HEADERS) as r:
                text = await r.text()
        except:
            continue

        if not any(x in text.lower() for x in ["buy","purchase","sale","sold"]):
            continue

        summary = ai_analyze(text, form)
        if not summary:
            return

        summary = clean(summary)

        msg = f"""🏛️ SEC

🏢 {ticker}
📄 Form 4

{summary}
"""

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text=msg)

        break

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v38")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v38")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for entry in feed.entries:
                        await send_news(session, {
                            "title": entry.title,
                            "link": entry.link
                        })

                await send_sec(session)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())