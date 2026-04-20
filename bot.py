# ===== Alpha Market Intelligence v50.2 (Ultimate + Small Cap) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests, json
from telegram import Bot
from deep_translator import GoogleTranslator

BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

SEC_HEADERS = {
    "User-Agent": "AlphaBot/5.2 (aktfaaksa@gmail.com)"
}

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"
]

sent = set()
cooldown = {}

# ===== FILTERS =====
CRAMER_FILTER = ["jim cramer"]
ANALYST_FILTER = ["maintains","price target","rating","upgrade","downgrade"]
TRASH = ["which","should you","vs","opinion","preview"]

KEYWORDS = [
    "earnings","results","guidance",
    "acquisition","merger","bankruptcy",
    "deal","agreement","fda"
]

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

# ===== ENTRY =====
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

# ===== TARGET / STOP / CONF =====
def get_target(price, dp):
    if dp <= 1:
        return round(price * 1.03, 2)
    elif dp <= 3:
        return round(price * 1.02, 2)
    else:
        return round(price * 1.01, 2)

def get_stop(price):
    return round(price * 0.97, 2)

def get_confidence(score):
    if score >= 85:
        return "🔥 عالي"
    elif score >= 70:
        return "🟡 متوسط"
    else:
        return "⚪ ضعيف"

# ===== SEND =====
async def send_msg(text):
    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=text)

# ===== PROCESS =====
async def process_news(session, e):

    title = e.title.lower()

    if any(x in title for x in CRAMER_FILTER): return
    if any(x in title for x in ANALYST_FILTER): return
    if any(x in title for x in TRASH): return

    key = hashlib.md5((e.title + e.link).encode()).hexdigest()
    if key in sent: return
    sent.add(key)

    symbol = extract_symbol(e.title)

    # ===== SEC =====
    if "sec.gov" in e.link:
        if not any(k in title for k in KEYWORDS):
            return

        msg = f"""🔥 خبر رسمي (SEC)

📰 {e.title}
🇸🇦 {tr(e.title)}

🏢 {symbol if symbol else "غير محدد"}

🔗 {e.link}
"""
        await send_msg(msg)
        return

    if not symbol or not can_send(symbol):
        return

    analysis = score_news(e.title)
    if not analysis:
        return

    score = analysis.get("score", 0)
    sentiment = analysis.get("sentiment", "neutral")
    reason = analysis.get("reason", "")

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    price = d.get("c")
    dp = d.get("dp", 0)

    if not price:
        return

    # ===== SMALL CAP LOGIC =====
    is_small = price <= 20

    if is_small:
        if not (score >= 35 and sentiment == "bullish"):
            return
    else:
        if score < 45:
            return

    timing = entry_timing(dp)
    contradiction = detect_contradiction(sentiment, dp)

    target = get_target(price, dp)
    stop = get_stop(price)
    confidence = get_confidence(score)

    emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "🟡"

    # ===== SMALL CAP LABEL =====
    tag = "🚀 SMALL CAP SIGNAL\n\n" if is_small else ""

    msg = f"""{tag}{emoji} {score}/100

🏢 {symbol}
📰 {e.title}
🇸🇦 {tr(e.title)}

📊 {price}$ | {round(dp,2)}%

⚡ توقيت الدخول:
{timing}

🎯 الهدف: {target}$
🛑 وقف الخسارة: {stop}$
📊 الثقة: {confidence}

🧠 {reason}
"""

    if score >= 80 and sentiment == "bullish" and dp <= 2:
        msg += "\n🔥 إشارة قوية"

    if is_small:
        msg += "\n⚠️ مخاطرة عالية (Small Cap)"

    if contradiction:
        msg += f"\n{contradiction}"

    await send_msg(msg)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v50.2 (SMALL CAP ENABLED)")

    async with aiohttp.ClientSession(headers=SEC_HEADERS) as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v50.2 (Small Cap Mode)")

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