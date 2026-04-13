import asyncio
import aiohttp
import hashlib
import os
import time
from telegram import Bot
from deep_translator import GoogleTranslator
from openai import OpenAI

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=TOKEN)

# ✅ OpenRouter
client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ✅ شخصين (واحد من ENV + واحد ثابت)
CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880
]

WATCHLIST = [
    "NVDA","AAPL","MSFT","GOOGL","AMZN","META","TSLA",
    "AMD","AVGO","TSM","INTC",
    "JPM","GS","BAC",
    "XOM","CVX",
    "JNJ","PFE","MRK",
    "MCD","NKE","HD",
    "NFLX","CRM","UBER"
]

sent_news = set()
last_run = 0

# ====== أدوات ======
def normalize_title(title):
    return " ".join(str(title).lower().split()[:6])

def news_id(title):
    return hashlib.md5(normalize_title(title).encode()).hexdigest()

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def analyze_keywords(title):
    t = title.lower()
    keywords = ["beat","strong","growth","surge","profit","record","miss","loss","drop","crash"]
    return any(w in t for w in keywords)

# ====== AI ======
async def ai_analyze(title):
    try:
        prompt = f"""
You are a professional stock analyst.

Analyze the news and return ONLY:

Decision: BUY or SELL or HOLD
Confidence: number from 0 to 100

Rules:
- Be strict and realistic
- Only give BUY if strong positive impact
- Only give SELL if strong negative impact

News: {title}
"""

        response = client.chat.completions.create(
            model="qwen/qwen3-next-80b-a3b-instruct:free",
            messages=[{"role": "user", "content": prompt}],
            extra_headers={
                "X-Title": "trading-bot"
            }
        )

        return response.choices[0].message.content

    except Exception as e:
        print("AI Error:", e)
        return None

# ====== Finnhub ======
async def get_news(session):
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
        async with session.get(url) as r:
            data = await r.json()
            return data if isinstance(data, list) else []
    except:
        return []

async def get_price(session, symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        async with session.get(url) as r:
            d = await r.json()
            if d.get("c") and d.get("pc"):
                return round(((d["c"] - d["pc"]) / d["pc"]) * 100, 2)
    except:
        pass
    return None

# ====== التشغيل ======
async def main():
    global last_run

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                if time.time() - last_run > 120:
                    last_run = time.time()

                    news = await get_news(session)

                    for n in news[:20]:
                        title = n.get("headline")
                        url = n.get("url")

                        if not title or not url:
                            continue

                        nid = news_id(title)
                        if nid in sent_news:
                            continue

                        if not analyze_keywords(title):
                            continue

                        for symbol in WATCHLIST:
                            if symbol.lower() in title.lower():

                                change = await get_price(session, symbol)
                                if not change or abs(change) < 2:
                                    continue

                                ai_result = await ai_analyze(title)
                                if not ai_result:
                                    continue

                                arrow = "📈" if change > 0 else "📉"

                                msg = f"""🚨 فرصة تداول

💼 {symbol} {arrow} {change}%

📰 {title}

🇸🇦 {translate(title)}

🤖 {ai_result}

🔗 {url}"""

                                # ✅ إرسال لشخصين
                                for c in CHAT_IDS:
                                    await bot.send_message(chat_id=c, text=msg)

                                sent_news.add(nid)
                                break

                        await asyncio.sleep(1)

                await asyncio.sleep(20)

            except Exception as e:
                print("Error:", e)
                await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())