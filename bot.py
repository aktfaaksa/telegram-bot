# ===== Alpha Market Intelligence v26 CLEAN =====

import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
import time
import pandas as pd
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG =====
MAX_NEWS_PER_CYCLE = 10
MAX_SEC_PER_CYCLE = 3

# ===== LOAD EXCEL =====
def load_excel():
    df = pd.read_excel("stocks.xlsx")
    return df["الرمز"].dropna().astype(str).str.strip().str.upper().unique().tolist()

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [CHAT_ID_MAIN]
bot = Bot(token=TOKEN)

WATCHLIST = load_excel()
AUTO_WATCHLIST = []

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent_hashes = set()
seen_symbols_cycle = set()

# ===== FILTER =====
BAD_WORDS = [
    "best stocks","should you buy","top stocks",
    "motley fool","opinion","analysis","i want to own"
]

def is_clean(title):
    t = title.lower()
    return not any(x in t for x in BAD_WORDS)

# ===== SYMBOL =====
def extract_symbol(title):
    t = title.upper()

    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    words = re.findall(r'\b[A-Z]{2,5}\b', t)
    for w in words:
        if w in WATCHLIST:
            return w

    return None

# ===== AI (مختصر جدًا) =====
async def analyze(title):
    if not OPENROUTER_API_KEY:
        return "محايد | 5/10 | انتظار"

    prompt = f"{title}\n\nصعودي او هبوطي او محايد | رقم/10 | شراء او بيع او احتفاظ | سبب كلمة"

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={"model":"google/gemini-2.5-flash-lite",
                      "messages":[{"role":"user","content":prompt}]}
            ) as r:
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()
    except:
        return "محايد | 5/10 | انتظار"

# ===== TRANSLATE (مختصر) =====
def translate(text):
    try:
        t = GoogleTranslator(source='auto', target='ar').translate(text)
        return t[:120]  # 🔥 قص الترجمة
    except:
        return text[:120]

# ===== STOCK =====
async def get_stock(session, symbol):
    try:
        async with session.get(
            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        ) as r:
            return await r.json()
    except:
        return {}

# ===== NEWS =====
async def send_news(bot, session, news):

    title = news["title"]
    link = news["link"]

    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)

    if not is_clean(title):
        return False

    symbol = extract_symbol(title)
    if not symbol:
        return False

    if symbol in seen_symbols_cycle:
        return False
    seen_symbols_cycle.add(symbol)

    translated = translate(title)
    ai = await analyze(title)
    stock = await get_stock(session, symbol)

    msg = f"""🔥 خبر

📰 {title}
🇸🇦 {translated}

📊 {symbol} | {stock.get('c')}$

🧠 {ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        await bot.send_message(chat_id=chat_id, text=msg)

    return True

# ===== SEC =====
SEC_HEADERS = {"User-Agent":"bot"}
SEC_URL = "https://www.sec.gov/files/company_tickers.json"

sent_sec_ids = set()

async def load_cik(session):
    async with session.get(SEC_URL, headers=SEC_HEADERS) as r:
        data = await r.json()
    return {v["ticker"]:str(v["cik_str"]).zfill(10) for v in data.values()}

async def send_sec(bot, session, symbol, cik_map):

    cik = cik_map.get(symbol)
    if not cik:
        return False

    try:
        async with session.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=SEC_HEADERS
        ) as r:
            data = await r.json()
    except:
        return False

    filings = data.get("filings",{}).get("recent",{})

    for i in range(len(filings.get("form",[]))):

        if filings["form"][i] != "8-K":
            continue

        acc = filings["accessionNumber"][i]
        key = f"{symbol}_{acc}"

        if key in sent_sec_ids:
            continue

        acc_clean = acc.replace("-","")
        link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/index.html"

        try:
            async with session.get(link, headers=SEC_HEADERS) as r2:
                text = (await r2.text()).lower()
        except:
            continue

        # 🔥 فلترة قوية
        if "warrant" in text or "offering" in text:
            continue

        event = "SEC مهم"

        if "earnings" in text:
            event = "أرباح"
        elif "merger" in text or "acquisition" in text:
            event = "اندماج"

        sent_sec_ids.add(key)

        msg = f"""🚨 SEC

🔥 {event} | {symbol}

🔗 {link}
"""

        for chat_id in CHAT_IDS:
            await bot.send_message(chat_id=chat_id, text=msg)

        return True

    return False

# ===== MAIN =====
async def main():
    print("🚀 CLEAN BOT RUNNING")

    async with aiohttp.ClientSession() as session:

        cik_map = await load_cik(session)

        while True:
            try:
                seen_symbols_cycle.clear()

                # ===== NEWS =====
                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title":e.title,"link":e.link})

                count = 0
                for n in feed:
                    if count >= MAX_NEWS_PER_CYCLE:
                        break
                    if await send_news(bot, session, n):
                        count += 1

                # ===== SEC =====
                sec_count = 0
                for s in WATCHLIST:
                    if sec_count >= MAX_SEC_PER_CYCLE:
                        break

                    if await send_sec(bot, session, s, cik_map):
                        sec_count += 1

                    await asyncio.sleep(1)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())