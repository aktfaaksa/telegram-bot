# ===== Alpha Market Intelligence v47.1 (Context Aware) 🚀 =====

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

# ===== FILTERS =====
STRONG = [
    "earnings","revenue","guidance","forecast",
    "fda","approval","acquisition","merger",
    "deal","beats","misses",
    "war","oil","inflation","fed","rates","economy","ai","chip","risk"
]

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

# ===== SMART CONTEXT SYSTEM =====
def smart_sector_map(text):
    t = text.lower()

    # 🟢 Risk ON (سوق إيجابي)
    if any(x in t for x in ["risk","optimism","rally","confidence","recovery"]):
        return ["إقبال على المخاطرة", "تحسن السوق"], ["NVDA","AAPL","TSLA"], ["TLT"]

    # 🛢️ طاقة
    if any(x in t for x in ["oil","energy","opec"]):
        return ["ارتفاع النفط"], ["XOM","CVX"], ["DAL","AAL"]

    # ⚔️ حرب (بدون risk-on)
    if any(x in t for x in ["war","attack","military"]) and not any(x in t for x in ["risk","optimism"]):
        return ["توتر جيوسياسي"], ["LMT","RTX"], ["DAL","AAL"]

    # 💻 تقنية
    if any(x in t for x in ["ai","chip","technology"]):
        return ["نمو قطاع التقنية"], ["NVDA","MSFT"], ["INTC"]

    # 🏦 بنوك
    if any(x in t for x in ["bank","fed","rates"]):
        return ["تحرك الفائدة"], ["JPM","BAC"], ["ARKK"]

    return None

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
tickers أمريكية فقط

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

        if not impact:
            impact = ["تحليل عام"]

        return impact, winners, losers

    except:
        smart = smart_sector_map(text)
        if smart:
            return smart

        return ["خبر عام بدون تأثير مباشر"], [], []

# ===== SEND GEO =====
async def send_geo(n):
    global last_geo

    lvl = geo_level(geo_score(n["title"]))
    if not lvl:
        return

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
🟢 {" - ".join(winners) if winners else "لا يوجد"}

⚠️ متضرر:
🔴 {" - ".join(losers) if losers else "لا يوجد"}
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

    emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "🟡"

    msg = f"""{emoji} {score}/100

🏢 {symbol}
📰 {n["title"]}
🇸🇦 {tr(n["title"])}

📊 {d['c']}$ | {round(d['dp'],2)}%

🧠 {reason}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v47.1 (CONTEXT AWARE)")

    async with aiohttp.ClientSession() as session:

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز v47.1 (Context Aware)")

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