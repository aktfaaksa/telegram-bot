# ===== Alpha Market Intelligence v46.5 (Balanced Flow) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

# ✅ مهم لا نحذفه
SEC_HEADERS = {
    "User-Agent": "AlphaBot/3.0 (aktfaaksa@gmail.com)"
}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent = set()
cooldown = {}
last_geo = 0

# ===== FILTERS (موسعة) =====
STRONG = [
    "earnings","revenue","guidance","forecast",
    "fda","approval","acquisition","merger",
    "deal","beats","misses",
    "war","oil","inflation","fed","rates","economy"
]

WEAK = ["skyrocket","boom","rally"]
TRASH = ["which","should you","vs","opinion"]

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

def clean_tickers(lst):
    return [x for x in lst if isinstance(x, str) and x.isupper() and 1 <= len(x) <= 5]

# ===== AI SCORE =====
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

# ===== GEO =====
def geo_score(t):
    t = t.lower()
    score = 0
    if any(x in t for x in ["war","attack","strike","missile"]): score += 4
    if any(x in t for x in ["oil","hormuz"]): score += 3
    if any(x in t for x in ["iran","russia","china"]): score += 2
    return score

def geo_level(s):
    return "🔴 عالي" if s >= 5 else "🟡 متوسط" if s >= 3 else None

# ===== MACRO =====
def macro_analysis(text):
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

{{
"impact": ["...","...","..."],
"winners": ["TICKER","TICKER","TICKER"],
"losers": ["TICKER","TICKER"]
}}

impact بالعربي فقط
winners/losers = tickers أمريكية

{text[:800]}
"""
                }]
            },
            timeout=10
        )

        data = json.loads(r.json()["choices"][0]["message"]["content"])
        impact = data.get("impact", [])
        winners = clean_tickers(data.get("winners", []))
        losers = [l for l in clean_tickers(data.get("losers", [])) if l not in winners]

        return impact, winners, losers

    except:
        return [], [], []

# ===== SEND GEO =====
async def send_geo(n):
    global last_geo

    lvl = geo_level(geo_score(n["title"]))
    if not lvl:
        return

    # 🔥 كولداون ذكي
    cooldown_time = 300 if lvl == "🔴 عالي" else 900
    if time.time() - last_geo < cooldown_time:
        return

    last_geo = time.time()

    impact, winners, losers = macro_analysis(n["title"])

    msg = f"""🌍 حدث مهم (تحليل السوق)

📰 {n["title"]}
🇸🇦 {tr(n["title"])}

⚡️ {lvl}

📊 التأثير:
{chr(10).join([f"• {x}" for x in impact])}

🎯 مستفيد:
🟢 {" - ".join(winners)}

⚠️ متضرر:
🔴 {" - ".join(losers)}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== NEWS =====
async def send_news(session, n):
    title = n["title"].lower()

    if any(x in title for x in TRASH): return
    if not any(x in title for x in STRONG): return

    key = hashlib.md5((n["title"] + n["link"]).encode()).hexdigest()
    if key in sent: return
    sent.add(key)

    await send_geo(n)

    symbol = extract_symbol(n["title"])
    if not symbol or not can_send(symbol):
        return

    analysis = score_news(n["title"])
    if not analysis:
        return

    score = analysis["score"]
    sentiment = analysis["sentiment"]

    if score < 50:
        return

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    msg = f"""{'🟢' if sentiment=='bullish' else '🔴'} {score}/100

🏢 {symbol}
📰 {n["title"]}
🇸🇦 {tr(n["title"])}

📊 {d['c']}$ | {round(d['dp'],2)}%
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v46.5 (BALANCED)")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v46.5 (Balanced)")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await send_news(session, {"title": e.title, "link": e.link})

                await asyncio.sleep(180)  # أسرع

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())