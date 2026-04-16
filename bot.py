# ===== Alpha Market Intelligence v23 ELITE FINAL =====

import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
import time
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [CHAT_ID_MAIN, 6315087880]
bot = Bot(token=TOKEN)

MAX_NEWS_PER_CYCLE = 15

WATCHLIST = ["AAPL","TSLA","NVDA","AMD","META","MSFT","AMZN","NFLX","INTC","BAC","GOOGL","GS"]
AUTO_WATCHLIST = []

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent_hashes = set()
seen_titles = set()
seen_symbols_cycle = set()

# ===== SEC =====
SEC_HEADERS = {
    "User-Agent": "market-bot aktfaaksa@gmail.com"
}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

sent_sec_ids = set()
sent_sec_symbols_cycle = set()

# ===== EVENT MAP =====
EVENT_MAP = {
    "acquisition": "استحواذ",
    "merger": "اندماج",
    "offering": "طرح أسهم",
    "warrant": "Warrants",
    "convertible": "سندات",
    "bankruptcy": "إفلاس",
    "restructuring": "إعادة هيكلة",
    "partnership": "شراكة",
    "collaboration": "تعاون",
    "agreement": "اتفاقية",
    "contract": "عقد"
}

PRIORITY = [
    "استحواذ","اندماج","إفلاس",
    "طرح أسهم","Warrants","سندات",
    "شراكة","تعاون","اتفاقية"
]

# ===== FILTER =====
JUNK = ["mortgage","lifestyle","ramsey","personal","story","transcript"]
BAD_WORDS = ["best stocks","should you buy","top stocks","is this stock","one of the best"]

# ===== TOP 50 =====
async def get_top50(session):
    try:
        async with session.get(
            f"https://finnhub.io/api/v1/stock/market/list/gainers?token={API_KEY}"
        ) as r:
            data = await r.json()
        return [x["symbol"] for x in data][:50]
    except:
        return []

# ===== HELPERS =====
def is_new(title, link):
    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def normalize(title):
    return re.sub(r'[^a-z0-9 ]', '', title.lower())[:50]

def is_unique(title):
    short = normalize(title)
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

def is_junk(title):
    t = title.lower()
    return any(k in t for k in JUNK) or any(b in t for b in BAD_WORDS)

def extract_symbol(title):
    t = title.upper()
    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    for s in WATCHLIST + AUTO_WATCHLIST:
        if s in t:
            return s

    return "MARKET"

def get_impact(title):
    t = title.lower()
    if any(x in t for x in ["earnings","merger","acquisition","bankruptcy"]):
        return "🔥 عالي"
    elif any(x in t for x in ["ai","chip","upgrade"]):
        return "⚡ متوسط"
    return "🟡 عادي"

def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== AI =====
async def analyze_news(title):
    if not OPENROUTER_API_KEY:
        return "محايد | 6/10 | احتفاظ | عادي"

    prompt = f"""
{title}

اكتب فقط:
صعودي أو هبوطي أو محايد | رقم/10 | شراء أو بيع أو احتفاظ | سبب كلمتين
"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model":"google/gemini-2.5-flash-lite",
                    "messages":[{"role":"user","content":prompt}]
                }
            ) as r:
                data = await r.json()
                result = data["choices"][0]["message"]["content"].strip()
                return result.replace("(", "").replace(")", "")
    except:
        return "تحليل غير متوفر"

# ===== STOCK =====
async def get_stock(session, symbol):
    try:
        async with session.get(
            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        ) as r:
            return await r.json()
    except:
        return {}

# ===== SEC =====
async def load_cik_map(session):
    async with session.get(SEC_TICKERS_URL, headers=SEC_HEADERS) as r:
        data = await r.json()
    return {v["ticker"]:str(v["cik_str"]).zfill(10) for v in data.values()}

async def send_sec(bot, session, symbol, cik_map):

    # منع تكرار نفس السهم
    if symbol in sent_sec_symbols_cycle:
        return

    cik = cik_map.get(symbol)
    if not cik:
        return

    try:
        async with session.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=SEC_HEADERS
        ) as r:
            data = await r.json()
    except:
        return

    filings = data.get("filings",{}).get("recent",{})

    for i in range(len(filings.get("form",[]))):

        if filings["form"][i] != "8-K":
            continue

        accession_id = filings["accessionNumber"][i]

        # منع التكرار الحقيقي
        key = f"{symbol}_{accession_id}"

        if key in sent_sec_ids:
            continue

        sent_sec_ids.add(key)
        sent_sec_symbols_cycle.add(symbol)

        accession = accession_id.replace("-","")
        link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/index.html"

        event = "حدث مهم"

        try:
            async with session.get(link, headers=SEC_HEADERS) as r2:
                text = (await r2.text()).lower()

            found = []

            for k,v in EVENT_MAP.items():
                if k in text:
                    if k == "contract":
                        continue
                    found.append(v)

            if not found and "contract" in text:
                found.append("عقد")

            for p in PRIORITY:
                if p in found:
                    event = p
                    break

            if event == "حدث مهم" and found:
                event = found[0]

        except:
            pass

        msg = f"""🔥 8-K ({event}) | {symbol}

📄 إشعار رسمي

🔗 {link}
"""

        for chat_id in CHAT_IDS:
            await bot.send_message(chat_id=chat_id, text=msg)

        break

# ===== SEND NEWS =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link): return False
    if not is_unique(title): return False
    if is_junk(title): return False

    symbol = extract_symbol(title)

    if symbol == "MARKET":
        return False

    if symbol in seen_symbols_cycle:
        return False
    seen_symbols_cycle.add(symbol)

    impact = get_impact(title)
    if impact == "🟡 عادي":
        return False

    translated = translate_text(title)
    ai = await analyze_news(title)

    stock = await get_stock(session, symbol)

    msg = f"""{impact}

📰 {title}
🇸🇦 {translated}

📊 {symbol} | {stock.get('c')}$ | {round(stock.get('dp',0),2)}%

🧠 {ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        await bot.send_message(chat_id=chat_id, text=msg)

    return True

# ===== MAIN =====
async def main():
    print("🚀 ELITE FINAL RUNNING")

    async with aiohttp.ClientSession() as session:

        global AUTO_WATCHLIST
        AUTO_WATCHLIST = await get_top50(session)
        last_update = time.time()

        cik_map = await load_cik_map(session)

        while True:
            try:
                if time.time() - last_update > 86400:
                    AUTO_WATCHLIST = await get_top50(session)
                    last_update = time.time()

                seen_symbols_cycle.clear()
                sent_sec_symbols_cycle.clear()

                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title":e.title,"link":e.link})

                count = 0
                for n in feed:
                    if count >= MAX_NEWS_PER_CYCLE:
                        break
                    if await send(bot, session, n):
                        count += 1

                for s in (WATCHLIST + AUTO_WATCHLIST)[:5]:
                    await send_sec(bot, session, s, cik_map)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())