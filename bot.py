# ===== Alpha Market Intelligence v14.0 (Llama + Gemma AI) =====

import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
from telegram import Bot
from deep_translator import GoogleTranslator
from openai import OpenAI

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))
CHAT_IDS = [CHAT_ID_MAIN, 6315087880]

bot = Bot(token=TOKEN)

# ===== AI CLIENT =====
client = OpenAI(
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://example.com",
        "X-Title": "alpha-bot"
    }
)

# ===== AI (🔥 Llama + Gemma fallback) =====
async def ai_analyze(title):
    models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free"
    ]

    for model in models:
        try:
            print("Trying:", model)

            response = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": f"""
Decision: BUY or SELL or HOLD
Confidence: %

News: {title}
"""
                }],
                timeout=12
            )

            result = response.choices[0].message.content
            if result:
                return result

        except Exception as e:
            print("AI error:", model, e)

    return ""

# ===== WATCHLIST =====
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
MAX_NEWS_PER_CYCLE = 15

HIGH_IMPACT = ["beats earnings","misses earnings","raises guidance","cuts forecast","acquisition","merger","buyout","bankruptcy","wins contract"]
MEDIUM_IMPACT = ["upgrade","downgrade","price target","partnership"]
MACRO_IMPACT = ["fed","interest rate","inflation","cpi","ppi","jobs","unemployment","gdp","recession","treasury","yield","dow","nasdaq","s&p","oil","iran","gold"]
TECH_IMPACT = ["ai","chip","semiconductor","nvidia"]

IGNORE_ANALYSIS = ["what","why","how","will","could","should"]
IGNORE_WEAK = ["how to","rules","tax","mortgage"]
IGNORE_OPINION = ["best","top stocks","buy now"]
IGNORE_ADMIN = ["appoint","hire","executive"]
IGNORE_USELESS = ["optimistic","steady"]
IGNORE_LOCAL = ["airport","city"]
IGNORE_MEDIA = ["newsletter","video","interview"]
IGNORE_FEATURE = ["startup","profile"]
IGNORE_CRYPTO = ["crypto","bitcoin"]

def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def is_new(title, link):
    h = hashlib.md5((title+link).encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

def normalize(title):
    t = re.sub(r'[^a-z0-9 ]', '', title.lower())
    return t[:60]

def is_unique(title):
    short = normalize(title)
    if short in seen_titles:
        return False
    seen_titles.add(short)
    return True

def get_impact(title):
    t = title.lower()
    if any(x in t for x in HIGH_IMPACT):
        return "🔥 HIGH"
    elif any(x in t for x in MACRO_IMPACT):
        return "🌍 MACRO"
    elif any(x in t for x in TECH_IMPACT):
        return "⚡ MEDIUM"
    elif any(x in t for x in MEDIUM_IMPACT):
        return "⚡ MEDIUM"
    else:
        return "🟡 GENERAL"

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
    return None

async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

async def get_market_news(session):
    url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
    async with session.get(url) as r:
        data = await r.json()
    return [{"title": n["headline"], "link": n["url"]} for n in data[:20] if n.get("url")]

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
    data.extend(await get_market_news(session))
    return data

# ===== SEND =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    title_lower = title.lower()

    if any(x in title_lower for x in IGNORE_ANALYSIS + IGNORE_WEAK + IGNORE_OPINION):
        return False

    impact = get_impact(title)
    symbol = extract_symbol(title) or "MARKET"

    translated = translate_text(title)

    stock_info = ""
    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"\n📊 {symbol} | {d.get('c')}$ ({round(d.get('dp',0),2)}%)\n"
        except:
            pass

    # 🔥 AI فقط للأخبار المهمة
    ai_text = ""
    if impact in ["🔥 HIGH", "🌍 MACRO"]:
        ai = await ai_analyze(title)
        if ai:
            ai_text = f"\n🤖 {ai}\n"

    message = f"""
{impact}

📰 {title}

🇸🇦 {translated}
{stock_info}
{ai_text}
🔗 {link}
"""

    for chat_id in CHAT_IDS:
        await bot.send_message(chat_id=chat_id, text=message)

    return True

# ===== MAIN =====
async def main():
    print("🚀 Bot v14 AI Running...")

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

if __name__ == "__main__":
    asyncio.run(main())