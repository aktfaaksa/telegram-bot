# ===== Alpha Market Intelligence v13 AI SAFE =====

import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
from datetime import datetime, timedelta
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

# ✅ تم الحفاظ عليه
CHAT_IDS = [CHAT_ID_MAIN, 6315087880]

bot = Bot(token=TOKEN)

# ===== WATCHLIST =====
WATCHLIST = ["AAPL","TSLA","NVDA","AMD","META","MSFT","AMZN","NFLX","INTC","BAC","GOOGL","GS"]

# ===== COMPANY MAP =====
COMPANY_MAP = {
    "TESLA":"TSLA","APPLE":"AAPL","NVIDIA":"NVDA","AMD":"AMD",
    "META":"META","MICROSOFT":"MSFT","AMAZON":"AMZN",
    "NETFLIX":"NFLX","INTEL":"INTC","BANK OF AMERICA":"BAC",
    "GOOGLE":"GOOGL","ALPHABET":"GOOGL","GOLDMAN SACHS":"GS"
}

# ===== RSS =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ===== MEMORY =====
sent_hashes = set()
seen_titles = set()

# ===== SETTINGS =====
MAX_NEWS_PER_CYCLE = 15

# ===== IMPACT =====
HIGH_IMPACT = ["beats earnings","misses earnings","raises guidance","cuts forecast","acquisition","merger","buyout","bankruptcy","wins contract"]

MEDIUM_IMPACT = ["upgrade","downgrade","price target","partnership"]

MACRO_IMPACT = ["fed","interest rate","inflation","cpi","ppi","jobs","unemployment","gdp","recession","treasury","yield","dow","nasdaq","s&p","oil","iran","gold","hormuz"]

TECH_IMPACT = ["ai","chip","semiconductor","nvidia"]

# ===== TRANSLATION =====
def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

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

# ===== IMPACT LOGIC =====
def get_impact(title):
    t = title.lower()

    if any(x in t for x in HIGH_IMPACT):
        return "🔥 HIGH"
    elif any(x in t for x in MACRO_IMPACT):
        return "🌍 MACRO"
    elif any(x in t for x in TECH_IMPACT + MEDIUM_IMPACT):
        return "⚡ MEDIUM"
    else:
        return "🟡 GENERAL"

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

# ===== AI ANALYSIS =====
async def analyze_news(title, impact):
    if not OPENROUTER_API_KEY:
        return ""

    # توزيع ذكي
    if impact == "🔥 HIGH":
        model = "anthropic/claude-3.7-sonnet"
    else:
        model = "google/gemini-3.1-flash-lite"

    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
You are a hedge fund analyst.

Analyze this news:

{title}

Return in Arabic:

الاتجاه: Bullish/Bearish/Neutral
القوة: 1-10
الثقة: %
الإشارة: Buy/Sell/Hold
السبب: سطر واحد فقط

مختصر جدا.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as r:
                data = await r.json()
                return data["choices"][0]["message"]["content"]
    except:
        return ""

# ===== STOCK =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

# ===== NEWS =====
def get_rss():
    out = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            out.append({"title": e.title, "link": e.link})
    return out

async def get_all(session):
    data = []
    data.extend(get_rss())
    return data

# ===== SEND =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    impact = get_impact(title)

    # 💰 توفير مهم
    if impact == "🟡 GENERAL":
        return False

    symbol = extract_symbol(title)

    translated = translate_text(title)

    # ===== AI =====
    ai = await analyze_news(title, impact)

    stock_info = ""
    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"""
📊 {symbol}
💰 Price: {d.get('c')}$
📈 Change: {round(d.get('dp',0),2)}%
"""
        except:
            pass

    message = f"""
{impact}

📰 *{title}*

🇸🇦 _{translated}_

{stock_info}

🧠 التحليل:
{ai}

🔗 {link}
"""

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except:
            pass

    return True

# ===== MAIN =====
async def main():
    print("🚀 AI Bot Running...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                news = await get_all(session)

                count = 0
                for n in news:
                    if count >= MAX_NEWS_PER_CYCLE:
                        break

                    if await send(bot, session, n):
                        count += 1

                await asyncio.sleep(300)

            except Exception as e:
                print("Error:", e)
                await asyncio.sleep(60)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())