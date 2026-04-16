# ===== Alpha Market Intelligence v18 SMART + TOP50 DAILY =====

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

# ===== WATCHLIST ثابتة =====
WATCHLIST = ["AAPL","TSLA","NVDA","AMD","META","MSFT","AMZN","NFLX","INTC","BAC","GOOGL","GS"]

# ===== AUTO TOP 50 =====
AUTO_WATCHLIST = []

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

# ===== TOP 50 DAILY =====
async def get_top50(session):
    url = f"https://finnhub.io/api/v1/stock/market/list/gainers?token={API_KEY}"

    try:
        async with session.get(url) as r:
            data = await r.json()

        symbols = []
        for x in data:
            s = x.get("symbol")
            if s:
                symbols.append(s)

        return symbols[:50]

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
    elif any(x in t for x in ["fed","inflation","rate","war","gold","oil"]):
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

    for s in WATCHLIST + AUTO_WATCHLIST:
        if re.search(rf'\b{s}\b', t):
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
        return "الاتجاه: محايد\nالقوة: 6/10\nالثقة: 70%\nالإشارة: احتفاظ\nالسبب: تحليل افتراضي"

    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
حلل الخبر التالي:

{title}

أجب فقط بهذا الشكل:

الاتجاه: صعودي / هبوطي / محايد
القوة: رقم/10
الثقة: %
الإشارة: شراء / بيع / احتفاظ
السبب: 3 كلمات فقط
"""

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

    payload = {
        "model": "google/gemini-2.5-flash-lite",
        "messages": [{"role":"user","content":prompt}]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as r:
                data = await r.json()
                return "\n".join(data["choices"][0]["message"]["content"].split("\n")[:5])
    except:
        return "تحليل غير متوفر"

# ===== STOCK =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

# ===== TECH =====
async def get_candles(session, symbol):
    now = int(time.time())
    past = now - (60*60*24*200)

    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={past}&to={now}&token={API_KEY}"

    async with session.get(url) as r:
        data = await r.json()
        return data.get("c", []) if data.get("s")=="ok" else []

def rsi(prices):
    if len(prices) < 15: return None
    gains, losses = [], []
    for i in range(1,15):
        diff = prices[-i] - prices[-i-1]
        (gains if diff>0 else losses).append(abs(diff))
    avg_gain = sum(gains)/14 if gains else 0
    avg_loss = sum(losses)/14 if losses else 0
    return 100 if avg_loss==0 else round(100-(100/(1+(avg_gain/avg_loss))),2)

def ma(prices,n):
    return round(sum(prices[-n:])/n,2) if len(prices)>=n else None

# ===== SEND =====
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
    if strength < 5: return False

    stock_info, tech = "", ""

    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"\n📊 {symbol} | {d.get('c')}$ | {round(d.get('dp',0),2)}%\n"

            prices = await get_candles(session, symbol)
            if prices:
                tech = f"\n📊 RSI:{rsi(prices)} | MA50:{ma(prices,50)} | MA200:{ma(prices,200)}\n"
        except:
            pass

    alert = "🚨 فرصة قوية\n" if strength >= 8 else ""

    message = f"""{alert}{impact}

📰 {title}
🇸🇦 {translated}

{stock_info}
{tech}

🧠
{ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        await bot.send_message(chat_id=chat_id, text=message)

    return True

# ===== MAIN =====
async def main():
    print("🚀 v18 SMART + TOP50 DAILY")

    async with aiohttp.ClientSession() as session:

        global AUTO_WATCHLIST
        AUTO_WATCHLIST = await get_top50(session)
        last_update = time.time()

        while True:
            try:
                # تحديث يومي
                if time.time() - last_update > 86400:
                    AUTO_WATCHLIST = await get_top50(session)
                    last_update = time.time()

                feed = []
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        feed.append({"title":e.title,"link":e.link})

                count = 0
                for n in feed:
                    if count >= MAX_NEWS_PER_CYCLE: break
                    if await send(bot, session, n): count += 1

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())