# ===== Alpha Market Intelligence v17 PRO (FIXED) =====

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

# ===== IMPACT =====
def get_impact(title):
    t = title.lower()

    if any(x in t for x in ["earnings","merger","acquisition","bankruptcy"]):
        return "🔥 عالي"
    elif any(x in t for x in ["fed","inflation","rate","war","oil","gold"]):
        return "🌍 اقتصادي"
    elif any(x in t for x in ["ai","chip","upgrade"]):
        return "⚡ متوسط"
    else:
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

# ===== TRANSLATION =====
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ===== AI =====
async def analyze_news(title):
    if not OPENROUTER_API_KEY:
        return "القوة: 6/10"

    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
حلل الخبر التالي:

{title}

الاتجاه / القوة (1-10) / الثقة / الإشارة

مختصر جداً بالعربي فقط
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
                return data.get("choices",[{}])[0].get("message",{}).get("content","القوة: 6/10")
    except:
        return "القوة: 6/10"

# ===== STOCK =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

# ===== TECHNICAL =====
async def get_candles(session, symbol):
    now = int(time.time())
    past = now - (60*60*24*200)

    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={past}&to={now}&token={API_KEY}"

    async with session.get(url) as r:
        data = await r.json()
        if data.get("s") != "ok":
            return []
        return data.get("c", [])

def rsi(prices):
    if len(prices) < 15:
        return None
    gains, losses = [], []
    for i in range(1,15):
        diff = prices[-i] - prices[-i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/14 if gains else 0
    avg_loss = sum(losses)/14 if losses else 0
    if avg_loss == 0:
        return 100
    rs = avg_gain/avg_loss
    return round(100-(100/(1+rs)),2)

def ma(prices, n):
    if len(prices) < n:
        return None
    return round(sum(prices[-n:])/n,2)

# ===== SEND =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    print("NEWS:", title)  # DEBUG

    if not is_new(title, link): return False
    if not is_unique(title): return False

    impact = get_impact(title)
    if impact == "🟡 عادي": return False

    symbol = extract_symbol(title)
    translated = translate_text(title)
    ai = await analyze_news(title)

    # ===== فلترة القوة (مرنة) =====
    match = re.search(r"(\d+)/10", ai)

    if match:
        strength = int(match.group(1))
    else:
        strength = 6  # fallback

    if strength < 5:
        return False

    # ===== السعر =====
    stock_info = ""
    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"\n📊 {symbol} | {d.get('c')}$ | {round(d.get('dp',0),2)}%\n"
        except:
            pass

    # ===== التحليل الفني =====
    tech = ""
    if symbol != "MARKET":
        try:
            prices = await get_candles(session, symbol)
            if prices:
                r = rsi(prices)
                m50 = ma(prices,50)
                m200 = ma(prices,200)

                trend = "📈 صاعد" if m50 and m200 and m50>m200 else "📉 هابط"
                signal = "🟢 تشبع بيع" if r and r<30 else "🔴 تشبع شراء" if r and r>70 else ""

                tech = f"\n📊 RSI:{r} | MA50:{m50} | MA200:{m200}\n{trend} {signal}\n"
        except:
            pass

    alert = "🚨 فرصة قوية\n" if strength >= 8 else ""

    message = f"""{alert}{impact}

📰 {title}
🇸🇦 {translated}

{stock_info}
{tech}

🧠 {ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=message)
        except:
            pass

    return True

# ===== MAIN =====
async def main():
    print("🚀 v17 PRO FIXED RUNNING")

    async with aiohttp.ClientSession() as session:
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

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())