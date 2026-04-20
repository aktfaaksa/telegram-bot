# ===== Alpha Market Intelligence v51 (Railway Ready + Debug) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG (Railway) =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

if not BOT_TOKEN or not FINNHUB or not OPENROUTER:
    raise ValueError("❌ تأكد من Environment Variables في Railway")

# 👇 حط ID حقك هنا
CHAT_IDS = [6315087880]

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

TRASH = ["which","should you","vs","opinion","preview"]

# ===== GEOPOLITICAL =====
GEOPOLITICAL_EVENTS = {
    "oil": ["oil","opec","crude","energy"],
    "war": ["war","attack","missile","conflict"],
    "china": ["china","taiwan"]
}

SECTOR_MAP = {
    "oil": ["XOM","CVX"],
    "war": ["LMT","RTX"],
    "china": ["AAPL","TSLA"]
}

# ===== UTIL =====
def translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return ""

def extract_symbol(t):
    m = re.findall(r'\(([A-Z]{1,5})\)', t)
    return m[0] if m else None

def is_duplicate(key):
    now = time.time()
    if key in sent_cache and now - sent_cache[key] < 600:
        return True
    sent_cache[key] = now
    return False

def detect_geo(title):
    for event, words in GEOPOLITICAL_EVENTS.items():
        if any(w in title for w in words):
            return event
    return None

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
                    "content": f"JSON فقط: score + sentiment + reason\n{text[:300]}"
                }]
            },
            timeout=6
        )
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except:
        print("AI ERROR")
        return None

# ===== SAFE REQUEST =====
async def safe_get(session, url):
    for _ in range(2):
        try:
            async with session.get(url) as r:
                return await r.json()
        except:
            await asyncio.sleep(1)
    print("API FAIL:", url)
    return None

# ===== SEND =====
async def send_msg(text):
    for c in CHAT_IDS:
        try:
            await bot.send_message(chat_id=c, text=text)
        except Exception as e:
            print("TELEGRAM ERROR:", e)

# ===== SIGNAL =====
async def generate_signal(session, e, symbol, geo):

    print(f"\n--- PROCESS {symbol} ---")

    analysis = score_news(e.title)
    if not analysis:
        print("SKIP: no AI")
        return

    score = analysis.get("score", 0)
    sentiment = analysis.get("sentiment", "neutral")
    reason = analysis.get("reason", "")

    print("AI:", score, sentiment)

    data = await safe_get(session,
        f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}"
    )

    if not data:
        print("SKIP: no market data")
        return

    price = data.get("c")
    volume = data.get("v", 0)

    print("MARKET:", price, volume)

    if not price:
        print("SKIP: no price")
        return

    # 🔥 فلترة مخففة
    if score < 35:
        print("SKIP: low score")
        return

    if volume < 100000:
        print("SKIP: low volume")
        return

    # 🌍 GEO BOOST
    if geo:
        score += 10

    target = round(price * 1.03, 2)
    stop = round(price * 0.97, 2)

    msg = f"""🚀 إشارة (DEBUG)

🏢 {symbol}
📰 {e.title}

📊 {price}$ | Vol:{volume}
📊 Score: {score}

🧠 {reason}
"""

    await send_msg(msg)
    print("SENT ✅")

# ===== PROCESS =====
async def process_news(session, e):

    print("\nNEWS:", e.title)

    title = e.title.lower()

    if any(x in title for x in TRASH):
        print("SKIP: trash")
        return

    key = hashlib.md5((e.title + e.link).encode()).hexdigest()
    if is_duplicate(key):
        print("SKIP: duplicate")
        return

    symbol = extract_symbol(e.title)
    geo = detect_geo(title)

    print("SYMBOL:", symbol, "| GEO:", geo)

    # 🌍 جيوسياسي بدون سهم
    if not symbol and geo:
        for sym in SECTOR_MAP.get(geo, []):
            await generate_signal(session, e, sym, geo)
        return

    if not symbol:
        print("SKIP: no symbol")
        return

    await generate_signal(session, e, symbol, geo)

# ===== MAIN =====
async def main():

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        await send_msg("🧪 DEBUG MODE شغال (Railway)")

        while True:
            try:
                print("\n🔥 LOOP START")

                for url in RSS_FEEDS:
                    print("\nFEED:", url)
                    feed = feedparser.parse(url)

                    for e in feed.entries[:5]:
                        await process_news(session, e)

                await asyncio.sleep(60)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(20)

asyncio.run(main())