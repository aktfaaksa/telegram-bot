# ===== Alpha Market Intelligence FINAL (SEC SMART ONLY) =====

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

    for s in WATCHLIST + AUTO_WATCHLIST:
        if s in t:
            return s

    return "MARKET"

# ===== TRANSLATION =====
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

# ===== SEC (تم تطويره فقط 🔥) =====
async def send_sec(bot, session, symbol, cik_map):

    data = await get_sec_filings(session, symbol, cik_map)

    for f in data:

        if not is_new_sec(f):
            continue

        title = "تحديث مهم"
        summary = "لم يتم العثور على تفاصيل واضحة"
        direction = "📊 محايد"

        try:
            async with session.get(f["link"], headers=SEC_HEADERS) as r:
                html = await r.text()

            doc_match = re.search(r'href="(/Archives/edgar/data/.*?\.htm)"', html)

            if doc_match:
                doc_url = "https://www.sec.gov" + doc_match.group(1)

                async with session.get(doc_url, headers=SEC_HEADERS) as r2:
                    doc_text = await r2.text()

                text = re.sub(r'<.*?>', '', doc_text).lower()

                if "acquisition" in text:
                    title = "استحواذ"
                    direction = "📈 صعودي"
                elif "merger" in text:
                    title = "اندماج"
                    direction = "📈 صعودي"
                elif "agreement" in text:
                    title = "اتفاقية"
                    direction = "📈 صعودي"
                elif "ceo" in text or "resign" in text:
                    title = "تغيير إداري"
                    direction = "📉 سلبي"
                elif "bankruptcy" in text:
                    title = "إفلاس"
                    direction = "📉 هبوط قوي"
                elif "offering" in text:
                    title = "طرح أسهم"
                    direction = "📉 سلبي"

                lines = doc_text.split("\n")

                for line in lines:
                    line = re.sub(r'<.*?>', '', line).strip()
                    if 50 < len(line) < 200:
                        summary = line
                        break

        except:
            pass

        msg = f"""🔥 {f['form']} ({title}) | {f['symbol']}

📄 {summary[:120]}

{direction}

🔗 {f['link']}
"""

        for chat_id in CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=msg)
            except:
                pass