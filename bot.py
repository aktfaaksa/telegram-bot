# ===== Alpha Market Intelligence v46.1 (Macro JSON Fixed) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

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
active_stocks = set()

# ===== FILTERS =====
STRONG = ["earnings","revenue","guidance","forecast",
          "fda","approval","acquisition","merger",
          "deal","beats","misses"]

WEAK = ["this year","skyrocket","surges","climbs","boom",
        "expansion","growth","outlook","rally"]

TRASH = ["which","should you","vs","analysis","opinion",
         "announces","launches","price target","preview"]

# ===== UTIL =====
def tr(x):
    try:
        return x if len(x) > 300 else GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

def extract_symbol(t):
    m = re.findall(r'\(([A-Z]{1,5})\)', t)
    return m[0] if m else None

def can_send(sym):
    now = time.time()
    if sym in cooldown and now - cooldown[sym] < 1800:
        return False
    cooldown[sym] = now
    return True

# ===== FORMAT =====
def format_sentiment(sentiment, score):
    if sentiment == "bullish":
        return "🟢", "إيجابي قوي" if score >= 70 else "إيجابي"
    elif sentiment == "bearish":
        return "🔴", "سلبي قوي" if score >= 70 else "سلبي"
    return "🟡", "محايد"

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

# ===== MACRO JSON =====
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
أرجع JSON فقط بدون أي نص إضافي:

{{
"impact": ["...","...","..."],
"winners": ["...","...","..."],
"losers": ["...","..."]
}}

حلل الخبر:
{text[:800]}
"""
                }]
            },
            timeout=10
        )

        content = r.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    except:
        return None

async def send_geo(n):
    global last_geo

    score = geo_score(n["title"])
    lvl = geo_level(score)

    if not lvl or time.time() - last_geo < 1800:
        return

    last_geo = time.time()

    analysis = macro_analysis(n["title"])

    if analysis:
        impact = "\n".join([f"• {x}" for x in analysis["impact"]])
        winners = " - ".join(analysis["winners"])
        losers = " - ".join(analysis["losers"])
    else:
        impact = "تعذر التحليل"
        winners = "-"
        losers = "-"

    msg = f"""🌍 حدث مهم (تحليل السوق)

📰 {n["title"]}
🇸🇦 {tr(n["title"])}

⚡️ {lvl}

📊 التأثير:
{impact}

🎯 مستفيد:
🟢 {winners}

⚠️ متضرر:
🔴 {losers}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== NEWS =====
async def send_news(session, n):
    title = n["title"].lower()

    if any(x in title for x in WEAK): return
    if any(x in title for x in TRASH): return
    if not any(x in title for x in STRONG): return

    key = hashlib.md5((n["title"] + n["link"]).encode()).hexdigest()
    if key in sent: return
    sent.add(key)

    await send_geo(n)

    symbol = extract_symbol(n["title"])
    if not symbol or not can_send(symbol): return

    active_stocks.add(symbol)

    analysis = score_news(n["title"])
    if not analysis: return

    score = analysis.get("score", 0)
    sentiment = analysis.get("sentiment", "neutral")
    reason = analysis.get("reason", "")

    if score < 50:
        return

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    if not d.get("c"): return

    emoji, sentiment_ar = format_sentiment(sentiment, score)

    msg = f"""{emoji} {sentiment_ar} ({score}/100)

🏢 {symbol}
📰 {n["title"]}
🇸🇦 {tr(n["title"])}

📊 {d['c']}$ | {round(d['dp'],2)}%

🧠 {reason}
"""

    if score >= 75 and sentiment == "bullish":
        msg += "\n📢 فرصة شراء محتملة"
    elif score >= 75 and sentiment == "bearish":
        msg += "\n📢 احتمال هبوط"

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v46.1 (JSON MACRO FIXED)")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v46.1 (Macro JSON)")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await send_news(session, {"title": e.title, "link": e.link})

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())