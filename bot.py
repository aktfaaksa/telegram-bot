# ===== Alpha Market Intelligence v51 (Pro) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

HEADERS = {
    "User-Agent": "AlphaBot/5.1 (aktfaaksa@gmail.com)"
}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"
]

sent_cache = {}
cooldown = {}

# ===== FILTERS =====
TRASH = ["which","should you","vs","opinion","preview"]
KEYWORDS = ["earnings","acquisition","merger","bankruptcy","guidance","fda"]

# ===== GEOPOLITICAL =====
GEOPOLITICAL_EVENTS = {
    "oil": ["oil","opec","crude","energy"],
    "war": ["war","attack","missile","conflict"],
    "sanctions": ["sanctions","ban","restriction"],
    "china": ["china","taiwan","trade war"]
}

SECTOR_MAP = {
    "oil": ["XOM","CVX","OXY"],
    "war": ["LMT","RTX","NOC"],
    "china": ["AAPL","TSLA","NVDA"],
}

# ===== UTIL =====
def translate(text, score):
    if score < 70:
        return ""
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return ""

def extract_symbol(t):
    m = re.findall(r'\(([A-Z]{1,5})\)', t)
    return m[0] if m else None

def is_duplicate(key):
    now = time.time()
    if key in sent_cache and now - sent_cache[key] < 1800:
        return True
    sent_cache[key] = now
    return False

def can_send(sym):
    now = time.time()
    if sym in cooldown and now - cooldown[sym] < 600:
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
                    "content": f"JSON فقط: score 0-100 + sentiment + reason\n{text[:500]}"
                }]
            },
            timeout=8
        )
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        return None

# ===== SAFE REQUEST =====
async def safe_get(session, url):
    for _ in range(3):
        try:
            async with session.get(url) as r:
                return await r.json()
        except:
            await asyncio.sleep(1)
    return None

# ===== GEO DETECT =====
def detect_geo(title):
    for event, words in GEOPOLITICAL_EVENTS.items():
        if any(w in title for w in words):
            return event
    return None

# ===== SEND =====
async def send_msg(text):
    for c in CHAT_IDS:
        try:
            await bot.send_message(chat_id=c, text=text)
        except:
            pass

# ===== PROCESS =====
async def process_news(session, e):

    title = e.title.lower()

    if any(x in title for x in TRASH):
        return

    key = hashlib.md5((e.title + e.link).encode()).hexdigest()
    if is_duplicate(key):
        return

    symbol = extract_symbol(e.title)
    geo = detect_geo(title)

    # ===== GEO WITHOUT SYMBOL =====
    if not symbol and geo:
        for sym in SECTOR_MAP.get(geo, []):
            await generate_signal(session, e, sym, geo)
        return

    if not symbol or not can_send(symbol):
        return

    await generate_signal(session, e, symbol, geo)

# ===== SIGNAL =====
async def generate_signal(session, e, symbol, geo):

    analysis = score_news(e.title)
    if not analysis:
        return

    score = analysis.get("score", 0)
    sentiment = analysis.get("sentiment", "neutral")
    reason = analysis.get("reason", "")

    data = await safe_get(session,
        f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}"
    )

    profile = await safe_get(session,
        f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB}"
    )

    if not data or not profile:
        return

    price = data.get("c")
    dp = data.get("dp", 0)
    volume = data.get("v", 0)
    market_cap = profile.get("marketCapitalization", 0)

    if not price or volume < 300000 or price < 1:
        return

    is_small = market_cap < 2_000_000_000

    # ===== GEO BOOST =====
    if geo:
        score += 15

    if is_small:
        if score < 55 or sentiment != "bullish":
            return
    else:
        if score < 40:
            return

    target = round(price * 1.03, 2)
    stop = round(price * 0.97, 2)

    arabic = translate(e.title, score)

    market_mode = f"🌍 {geo.upper()} BULLISH\n\n" if geo else ""

    msg = f"""{market_mode}🚀 إشارة تداول

🏢 {symbol}
📰 {e.title}
🇸🇦 {arabic}

📊 {price}$ | {round(dp,2)}%
📦 حجم: {volume}

🎯 الهدف: {target}$
🛑 وقف: {stop}$

📊 سكـور: {score}
🧠 {reason}
"""

    if score >= 85 and dp < 2:
        msg += "\n🔥 إشارة قوية"

    if is_small:
        msg += "\n⚠️ Small Cap"

    await send_msg(msg)

# ===== MAIN =====
async def main():

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        await send_msg("✅ Alpha v51 جاهز")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await process_news(session, e)

                await asyncio.sleep(180)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())