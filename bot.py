# ===== Alpha Market Intelligence v16 ELITE (TECH EDITION) =====

import asyncio
import aiohttp
import feedparser
import hashlib
import os
import re
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

CHAT_IDS = [CHAT_ID_MAIN, 6315087880]  # ✅ موجود مثل ما طلبت

bot = Bot(token=TOKEN)

# ===== CONFIG =====
MAX_NEWS_PER_CYCLE = 15

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

# ===== IMPACT =====
def get_impact(title):
    t = title.lower()

    if any(x in t for x in HIGH_IMPACT):
        return "🔥 عالي"

    elif any(x in t for x in MACRO_IMPACT):
        if any(k in t for k in ["war","conflict","crisis","inflation","rate"]):
            return "🌍 اقتصادي عالي"
        return "🌍 اقتصادي"

    elif any(x in t for x in TECH_IMPACT + MEDIUM_IMPACT):
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

# ===== AI =====
async def analyze_news(title, impact):
    if not OPENROUTER_API_KEY:
        return "❌ لا يوجد API"

    if "🔥" in impact or "اقتصادي عالي" in impact:
        model = "anthropic/claude-3.7-sonnet"
    else:
        model = "google/gemini-2.5-flash-lite"

    url = "https://openrouter.ai/api/v1/chat/completions"

    prompt = f"""
حلل الخبر التالي:

{title}

أجب بالعربي فقط وبشكل مختصر جداً:

الاتجاه: صعودي / هبوطي / محايد
القوة: رقم من 1 إلى 10 (مثل 7/10)
الثقة: نسبة مئوية
الإشارة: شراء / بيع / احتفاظ
السبب: سبب مالي واضح (3 إلى 6 كلمات)

إذا القوة أقل من 7 اجعل الإشارة احتفاظ.

ممنوع أي كلمة إنجليزية.
ممنوع أي شرح إضافي.
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
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
                else:
                    return "❌ خطأ في التحليل"
    except:
        return "❌ فشل التحليل"

# ===== STOCK =====
async def get_stock(session, symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
    async with session.get(url) as r:
        return await r.json()

# ===== TECHNICAL INDICATORS =====
async def get_candles(session, symbol):
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&count=200&token={API_KEY}"
    async with session.get(url) as r:
        data = await r.json()
        return data.get("c", [])

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    gains, losses = [], []

    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i-1]
        if diff >= 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains)/period if gains else 0
    avg_loss = sum(losses)/period if losses else 0

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def moving_average(prices, period):
    if len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period, 2)

# ===== NEWS =====
def get_rss():
    out = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            out.append({"title": e.title, "link": e.link})
    return out

async def get_all(session):
    return get_rss()

# ===== SEND =====
async def send(bot, session, news):
    title = news["title"]
    link = news["link"]

    if not is_new(title, link):
        return False

    if not is_unique(title):
        return False

    impact = get_impact(title)
    if impact == "🟡 عادي":
        return False

    symbol = extract_symbol(title)
    translated = translate_text(title)
    ai = await analyze_news(title, impact)

    # ===== فلترة القوة =====
    match = re.search(r"القوة:\s*(\d+)", ai)
    if not match:
        return False

    strength = int(match.group(1))
    if strength <= 5:
        return False

    # ===== تنبيه =====
    alert = "🚨 فرصة قوية\n" if strength >= 8 else ""

    # ===== السعر =====
    stock_info = ""
    if symbol != "MARKET":
        try:
            d = await get_stock(session, symbol)
            stock_info = f"\n📊 {symbol}\n💰 {d.get('c')}$\n📈 {round(d.get('dp',0),2)}%\n"
        except:
            pass

    # ===== التحليل الفني =====
    tech_info = ""
    if symbol != "MARKET":
        try:
            prices = await get_candles(session, symbol)
            if prices:
                rsi = calculate_rsi(prices)
                ma50 = moving_average(prices, 50)
                ma200 = moving_average(prices, 200)

                trend = "📈 صاعد" if ma50 and ma200 and ma50 > ma200 else "📉 هابط"
                rsi_signal = "🟢 تشبع بيع" if rsi and rsi < 30 else "🔴 تشبع شراء" if rsi and rsi > 70 else ""

                tech_info = f"\n📊 التحليل الفني:\nRSI: {rsi}\nMA50: {ma50}\nMA200: {ma200}\n{trend} {rsi_signal}\n"
        except:
            pass

    message = f"""
{alert}{impact}

📰 *{title}*

🇸🇦 _{translated}_

{stock_info}
{tech_info}

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
    print("🚀 v16 TECH RUNNING")

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
                print("MAIN ERROR:", e)
                await asyncio.sleep(60)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())