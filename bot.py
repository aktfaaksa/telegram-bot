# ===== Alpha Market Intelligence v50.6 (PRO MODE) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")
ALPHA = os.getenv("ALPHA_VANTAGE_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

SEC_HEADERS = {"User-Agent": "AlphaBot/5.6 (aktfaaksa@gmail.com)"}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"
]

sent = set()
cooldown = {}

CRAMER_FILTER = ["jim cramer"]
ANALYST_FILTER = ["maintains","price target","rating","upgrade","downgrade"]
TRASH = ["which","should you","vs","opinion","preview"]

INVESTOR_FILTER = [
    "david einhorn","hedge fund","likes this stock",
    "buying this stock","bullish"
]

WEAK_NEWS = [
    "overlooked","growth stock","why","to buy now"
]

# ===== RSI =====
async def get_rsi(symbol):
    if not ALPHA:
        return None
    url = f"https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval=5min&time_period=14&series_type=close&apikey={ALPHA}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                data = await r.json()
                rsi_data = data.get("Technical Analysis: RSI", {})
                if not rsi_data:
                    return None
                latest = list(rsi_data.values())[0]
                return float(latest["RSI"])
    except:
        return None

# ===== VOLUME =====
async def get_volume_data(session, symbol):
    try:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=5&count=20&token={FINNHUB}"
        async with session.get(url) as r:
            data = await r.json()
            volumes = data.get("v", [])
            if not volumes or len(volumes) < 5:
                return None, None
            current_volume = volumes[-1]
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
            return current_volume, avg_volume
    except:
        return None, None

# ===== UTIL =====
def tr(x):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

def extract_symbol(t):
    m = re.findall(r'\(([A-Z]{1,5})\)', t)
    return m[0] if m else None

def can_send(sym):
    now = time.time()
    if sym in cooldown and now - cooldown[sym] < 900:
        return False
    cooldown[sym] = now
    return True

# ===== AI =====
def score_news(text):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER}"},
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"""
أرجع JSON فقط:
{{"score": 0-100, "sentiment": "bullish أو bearish أو neutral", "reason": "سبب مختصر"}}

{text[:800]}
"""
                }]
            },
            timeout=10
        )
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        return None

# ===== HELPERS =====
def entry_timing(dp):
    return "🟢 مبكر" if dp <= 1 else "🟡 متوسط" if dp <= 3 else "🔴 متأخر"

def get_target(price): return round(price * 1.03, 2)
def get_stop(price): return round(price * 0.97, 2)

async def send_msg(text):
    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=text)

# ===== PROCESS =====
async def process_news(session, e):

    title = e.title.lower()

    # ===== FILTERS =====
    if any(x in title for x in CRAMER_FILTER): return
    if any(x in title for x in ANALYST_FILTER): return
    if any(x in title for x in TRASH): return
    if any(x in title for x in INVESTOR_FILTER): return
    if any(x in title for x in WEAK_NEWS): return

    key = hashlib.md5((e.title + e.link).encode()).hexdigest()
    if key in sent: return
    sent.add(key)

    symbol = extract_symbol(e.title)
    if not symbol or not can_send(symbol):
        return

    analysis = score_news(e.title)
    if not analysis:
        return

    score = analysis.get("score", 0)
    sentiment = analysis.get("sentiment", "neutral")
    reason = analysis.get("reason", "")

    if score < 70 or sentiment != "bullish":
        return

    # ===== PRICE =====
    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    price = d.get("c")
    dp = d.get("dp", 0)
    if not price:
        return

    # ===== NO LATE ENTRY =====
    if dp > 3:
        return

    # ===== VOLUME =====
    current_vol, avg_vol = await get_volume_data(session, symbol)

    if current_vol and avg_vol:
    if current_vol < avg_vol * 1.3:
        return  # فلتر معقول 👍
    
    # ===== RSI =====
    rsi = None
    if score >= 70:
        rsi = await get_rsi(symbol)

    if rsi and rsi > 75:
        return

    # ===== OUTPUT =====
    timing = entry_timing(dp)
    target = get_target(price)
    stop = get_stop(price)

    msg = f"""💀 PRO SIGNAL

🟢 {score}/100

🏢 {symbol}
📰 {e.title}
🇸🇦 {tr(e.title)}

📊 {price}$ | {round(dp,2)}%
📊 Volume: 🔥 عالي

📉 RSI: {round(rsi,2) if rsi else "N/A"}

⚡ توقيت الدخول: {timing}
🎯 الهدف: {target}$
🛑 وقف الخسارة: {stop}$

🧠 {reason}
"""

    if score >= 85:
        msg += "\n🚀 إشارة نارية جدًا"

    await send_msg(msg)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v50.6 (PRO MODE)")

    async with aiohttp.ClientSession(headers=SEC_HEADERS) as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v50.6 (PRO MODE)")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await process_news(session, e)

                await asyncio.sleep(120)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())