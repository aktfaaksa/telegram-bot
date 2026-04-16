# ===== Alpha Market Intelligence v18 SMART + SEC FINAL =====

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

# ===== SEC =====
SEC_HEADERS = {
    "User-Agent": "alpha-bot aktfaaksa@gmail.com"
}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
IMPORTANT_FORMS = ["8-K", "4", "13D", "NT 10-Q", "S-3"]
sent_sec = set()

# ===== NEWS =====
MAX_NEWS_PER_CYCLE = 15

WATCHLIST = ["AAPL","TSLA","NVDA","AMD","META","MSFT","AMZN","NFLX","INTC","BAC","GOOGL","GS"]

COMPANY_MAP = {
    "TESLA":"TSLA","APPLE":"AAPL","NVIDIA":"NVDA","AMD":"AMD",
    "META":"META","MICROSOFT":"MSFT","AMAZON":"AMZN",
    "NETFLIX":"NFLX","INTEL":"INTC","BANK OF AMERICA":"BAC",
    "GOOGLE":"GOOGL","ALPHABET":"GOOGL","GOLDMAN SACHS":"GS"
}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent_hashes = set()
seen_titles = set()

JUNK = ["mortgage","lifestyle","ramsey","personal","story"]

# ===== HELPERS =====
def is_new(title, link):
    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def normalize(title):
    return re.sub(r'[^a-z0-9 ]', '', title.lower())[:60]

def is_unique(title):
    short = normalize(title)
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

def is_junk(title):
    return any(k in title.lower() for k in JUNK)

# ===== IMPACT =====
def get_impact(title):
    t = title.lower()
    if any(x in t for x in ["earnings","merger","acquisition","bankruptcy"]):
        return "🔥 عالي"
    elif any(x in t for x in ["fed","inflation","rate","war","oil"]):
        return "🌍 اقتصادي"
    elif any(x in t for x in ["ai","chip","upgrade"]):
        return "⚡ متوسط"
    return "🟡 عادي"

# ===== SYMBOL =====
def extract_symbol(title):
    t = title.upper()
    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    for name, s in COMPANY_MAP.items():
        if name in t:
            return s

    for s in WATCHLIST:
        if re.search(rf'\b{s}\b', t):
            return s

    return "MARKET"

# ===== TRANSLATE =====
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== AI =====
async def analyze_news(title):
    if not OPENROUTER_API_KEY:
        return "الاتجاه: محايد\nالقوة: 6/10\nالثقة: 70%\nالإشارة: احتفاظ\nالسبب: افتراضي"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": "google/gemini-2.5-flash-lite",
                    "messages": [{"role":"user","content":title}]
                }
            ) as r:
                data = await r.json()
                return data["choices"][0]["message"]["content"]
    except:
        return "تحليل غير متوفر"

# ===== STOCK =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

# ===== SEND NEWS =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link): return False
    if not is_unique(title): return False
    if is_junk(title): return False

    impact = get_impact(title)
    if impact == "🟡 عادي": return False

    symbol = extract_symbol(title)
    translated = translate_text(title)
    ai = await analyze_news(title)

    stock_info = ""
    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"\n📊 {symbol} | {d.get('c')}$ | {round(d.get('dp',0),2)}%\n"
        except:
            pass

    message = f"""{impact}

📰 {title}
🇸🇦 {translated}

{stock_info}

🧠
{ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=message)
        except:
            pass

    return True

# ===== SEC =====
async def load_cik_map(session):
    async with session.get(SEC_TICKERS_URL, headers=SEC_HEADERS) as r:
        data = await r.json()
    return {item["ticker"]: str(item["cik_str"]).zfill(10) for item in data.values()}

async def get_sec_filings(session, symbol, cik_map):
    cik = cik_map.get(symbol)
    if not cik:
        return []

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    async with session.get(url, headers=SEC_HEADERS) as r:
        data = await r.json()

    filings = data.get("filings", {}).get("recent", {})
    results = []

    for i in range(len(filings.get("form", []))):
        form = filings["form"][i]

        if form in IMPORTANT_FORMS:
            accession = filings["accessionNumber"][i].replace("-", "")
            link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/index.html"

            results.append({
                "symbol": symbol,
                "form": form,
                "date": filings["filingDate"][i],
                "link": link
            })

    return results[:1]

def is_new_sec(f):
    key = f"{f['symbol']}_{f['form']}_{f['date']}"
    if key in sent_sec:
        return False
    sent_sec.add(key)
    return True

def short_label(form):
    return {
        "8-K": "خبر قوي",
        "4": "شراء داخلي",
        "13D": "مستثمر كبير",
        "NT 10-Q": "تأخير",
        "S-3": "بيع أسهم"
    }.get(form, "خبر")

async def send_sec(bot, session, symbol, cik_map):
    data = await get_sec_filings(session, symbol, cik_map)

    for f in data:
        if not is_new_sec(f):
            continue

        label = short_label(f["form"])

        msg = f"""
🔥 {f['form']} ({label}) | {f['symbol']}

🔗 {f['link']}
"""

        for chat_id in CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=msg)
            except:
                pass

# ===== MAIN =====
async def main():
    print("🚀 v18 SMART + SEC FINAL RUNNING")

    async with aiohttp.ClientSession() as session:
        cik_map = await load_cik_map(session)

        while True:
            try:
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

                for s in WATCHLIST:
                    await send_sec(bot, session, s, cik_map)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())