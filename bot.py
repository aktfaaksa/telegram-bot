# ===== Alpha Market Intelligence v26 PRO FIXED =====

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

# ===== LOAD EXCEL =====
def load_excel():
    df = pd.read_excel("stocks.xlsx")
    return (
        df["الرمز"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [CHAT_ID_MAIN, 6315087880]

bot = Bot(token=TOKEN)

MAX_NEWS_PER_CYCLE = 15
WATCHLIST = load_excel()

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent_hashes = set()
seen_titles = set()
seen_symbols_cycle = set()

# ===== SEC =====
SEC_HEADERS = {
    "User-Agent": "AlphaMarketBot aktfaaksa@gmail.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

sent_sec_ids = set()
sent_sec_symbols_cycle = set()

# ===== FILTER =====
JUNK = ["mortgage","lifestyle","ramsey","personal","story","transcript"]
BAD_WORDS = ["best stocks","should you buy","top stocks"]

# ===== HELPERS =====
def is_new(title, link):
    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def normalize(title):
    return re.sub(r'[^a-z0-9 ]', '', title.lower())

def is_unique(title):
    short = normalize(title)
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

def is_junk(title):
    t = title.lower()
    return any(k in t for k in JUNK) or any(b in t for b in BAD_WORDS)

# ===== SYMBOL =====
def extract_symbol(title):
    t = title.upper()

    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    for w in re.findall(r'\b[A-Z]{2,5}\b', t):
        if w in WATCHLIST:
            return w

    return "MARKET"

def get_impact(title):
    t = title.lower()
    if any(x in t for x in ["earnings","merger","acquisition"]):
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
        return "محايد | 6/10 | احتفاظ"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model":"google/gemini-2.5-flash-lite",
                    "messages":[{"role":"user","content":title}]
                }
            ) as r:
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()[:120]
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

# ===== SEC LOAD =====
async def load_cik_map(session):
    try:
        async with session.get(SEC_TICKERS_URL, headers=SEC_HEADERS) as r:
            data = await r.json()
        return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in data.values()}
    except:
        return {}

# ===== NEWS =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link): return False
    if not is_unique(title): return False
    if is_junk(title): return False

    symbol = extract_symbol(title)
    if symbol == "MARKET": return False

    if symbol in seen_symbols_cycle: return False
    seen_symbols_cycle.add(symbol)

    impact = get_impact(title)
    if impact == "🟡 عادي": return False

    # ===== Finnhub =====
    stock = await get_stock(session, symbol)

    price = stock.get("c", 0)
    change = stock.get("dp", 0)

    # 🔥 الفلترة الصحيحة (قبل الرسالة)
    if price == 0:
        return False

    if abs(change) < 1.5:
        return False

    if price < 2:
        return False

    # ===== بعد الفلترة فقط =====
    translated = translate_text(title)[:150]
    ai = await analyze_news(title)

    msg = f"""{impact}

📰 {title}
🇸🇦 {translated}

📊 {symbol} | {price}$ | {round(change,2)}%

🧠 {ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        await bot.send_message(chat_id=chat_id, text=msg)

    return True

# ===== MAIN =====
async def main():
    print("🚀 v26 PRO FIXED RUNNING")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                seen_symbols_cycle.clear()

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

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())