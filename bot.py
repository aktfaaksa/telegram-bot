# ===== Alpha Market Intelligence FINAL (SEC EVENT TYPE) =====

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

# ===== WATCHLIST =====
WATCHLIST = [
    "AAPL","TSLA","NVDA","MSFT","AMZN","GOOGL","META",
    "PLTR","SMCI","COIN","UBER","SHOP",
    "RIOT","MARA","SOFI","DKNG",
    "AVGO","TSM"
]

AUTO_WATCHLIST = []

# ===== NEWS =====
MAX_NEWS_PER_CYCLE = 15

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent_hashes = set()
seen_titles = set()

JUNK = [
    "mortgage","lifestyle","ramsey","personal","story",
    "jim cramer","opinion","analyst says","transcript","earnings transcript"
]

# ===== SEC =====
SEC_HEADERS = {
    "User-Agent": "alpha-bot aktfaaksa@gmail.com"
}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
IMPORTANT_FORMS = ["8-K", "13D"]
sent_sec = set()

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

def get_impact(title):
    t = title.lower()
    if any(x in t for x in ["earnings","merger","acquisition","bankruptcy"]):
        return "🔥 عالي"
    elif any(x in t for x in ["fed","inflation","rate","war","oil"]):
        return "🌍 اقتصادي"
    elif any(x in t for x in ["ai","chip","upgrade"]):
        return "⚡ متوسط"
    return "🟡 عادي"

def extract_symbol(title):
    t = title.upper()
    match = re.findall(r'\(([A-Z]{1,5})\)', t)
    if match:
        return match[0]

    for s in WATCHLIST + AUTO_WATCHLIST:
        if s in t:
            return s

    return "MARKET"

def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== AI =====
async def analyze_news(title):
    if not OPENROUTER_API_KEY:
        return "الاتجاه: محايد\nالقوة: 6/10\nالثقة: 70%\nالإشارة: احتفاظ\nالسبب: افتراضي"

    prompt = f"""
حلل الخبر التالي:

{title}

أجب فقط بهذا الشكل:

الاتجاه: صعودي / هبوطي / محايد
القوة: رقم/10
الثقة: %
الإشارة: شراء / بيع / احتفاظ
السبب: 3 كلمات فقط

ممنوع الشرح
"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": "google/gemini-2.5-flash-lite",
                    "messages": [{"role":"user","content":prompt}]
                }
            ) as r:
                data = await r.json()
                return "\n".join(data["choices"][0]["message"]["content"].split("\n")[:5])
    except:
        return "تحليل غير متوفر"

# ===== STOCK =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

# ===== AUTO WATCHLIST =====
async def get_top_movers(session):
    url = f"https://finnhub.io/api/v1/stock/market/list/gainers?token={API_KEY}"
    try:
        async with session.get(url) as r:
            data = await r.json()
        return [x["symbol"] for x in data[:5]]
    except:
        return []

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

    ALL_STOCKS = WATCHLIST + AUTO_WATCHLIST
    if symbol not in ALL_STOCKS:
        return False

    translated = translate_text(title)
    ai = await analyze_news(title)

    match = re.search(r"(\d+)/10", ai)
    strength = int(match.group(1)) if match else 6

    if strength < 6:
        return False

    stock_info = ""
    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"\n📊 {symbol} | {d.get('c')}$ | {round(d.get('dp',0),2)}%\n"
        except:
            pass

    alert = "🚨 فرصة قوية\n" if strength >= 8 and impact != "🟡 عادي" else ""

    message = f"""{alert}{impact}

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

# ===== SEC (نوع الحدث واضح 🔥) =====
async def load_cik_map(session):
    async with session.get(SEC_TICKERS_URL, headers=SEC_HEADERS) as r:
        data = await r.json()
    return {item["ticker"]: str(item["cik_str"]).zfill(10) for item in data.values()}

async def send_sec(bot, session, symbol, cik_map):

    cik = cik_map.get(symbol)
    if not cik:
        return

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    async with session.get(url, headers=SEC_HEADERS) as r:
        data = await r.json()

    filings = data.get("filings", {}).get("recent", {})

    for i in range(len(filings.get("form", []))):

        form = filings["form"][i]

        if form not in IMPORTANT_FORMS:
            continue

        date = filings["filingDate"][i]
        accession = filings["accessionNumber"][i].replace("-", "")

        key = f"{symbol}_{form}_{date}"
        if key in sent_sec:
            continue

        sent_sec.add(key)

        link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/index.html"

        # ===== تحديد نوع الحدث 🔥 =====
        event = "حدث مهم"
        direction = "📊 محايد"

        try:
            async with session.get(link, headers=SEC_HEADERS) as r2:
                text = (await r2.text()).lower()

            if "acquisition" in text:
                event = "استحواذ"
                direction = "📈 صعودي"
            elif "merger" in text:
                event = "اندماج"
                direction = "📈 صعودي"
            elif "agreement" in text:
                event = "اتفاقية"
                direction = "📈 صعودي"
            elif "ceo" in text or "resign" in text:
                event = "تغيير إداري"
                direction = "📉 سلبي"
            elif "bankruptcy" in text:
                event = "إفلاس"
                direction = "📉 هبوط قوي"
            elif "offering" in text:
                event = "طرح أسهم"
                direction = "📉 سلبي"

        except:
            pass

        msg = f"""🔥 {form} ({event}) | {symbol}

📄 إشعار رسمي
{direction}

🔗 {link}
"""

        for chat_id in CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=msg)
            except:
                pass

        break

# ===== MAIN =====
async def main():
    print("🚀 BOT RUNNING FINAL")

    async with aiohttp.ClientSession() as session:

        cik_map = await load_cik_map(session)

        while True:
            try:
                for s in WATCHLIST[:5]:
                    await send_sec(bot, session, s, cik_map)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())