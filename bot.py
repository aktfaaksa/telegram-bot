# ===== Alpha Market Intelligence v48 (Trading Mode) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator

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

# ===== ENTRY TIMING =====
def entry_timing(dp):
    if dp <= 1:
        return "🟢 مبكر"
    elif dp <= 3:
        return "🟡 متوسط"
    else:
        return "🔴 متأخر"

# ===== CONTRADICTION =====
def detect_contradiction(sentiment, dp):
    if sentiment == "bullish" and dp < 0:
        return "⚠️ خبر إيجابي لكن السعر نازل"
    if sentiment == "bearish" and dp > 0:
        return "⚠️ خبر سلبي لكن السعر مرتفع"
    return None

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

# ===== NEWS =====
async def send_news(session, n):
    symbol = extract_symbol(n["title"])
    if not symbol or not can_send(symbol):
        return

    analysis = score_news(n["title"])
    if not analysis:
        return

    score = analysis.get("score", 0)
    sentiment = analysis.get("sentiment", "neutral")
    reason = analysis.get("reason", "")

    if score < 40:
        return

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    price = d.get("c")
    dp = d.get("dp", 0)

    if not price:
        return

    # ===== NEW FEATURES =====
    timing = entry_timing(dp)
    contradiction = detect_contradiction(sentiment, dp)

    emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "🟡"

    msg = f"""{emoji} {score}/100

🏢 {symbol}
📰 {n["title"]}
🇸🇦 {tr(n["title"])}

📊 {price}$ | {round(dp,2)}%

⚡ توقيت الدخول:
{timing}

🧠 {reason}
"""

    if score >= 75 and sentiment == "bullish":
        msg += "\n🔥 إشارة قوية"

    if contradiction:
        msg += f"\n{contradiction}"

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v48 (TRADING MODE)")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v48 (Trading Mode)")

        while True:
            try:
                for url in RSS_FEEDS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await send_news(session, {"title": e.title, "link": e.link})

                await asyncio.sleep(180)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

asyncio.run(main())