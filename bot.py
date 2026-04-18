# ===== Alpha Market Intelligence v31 (Smart Analysis) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG =====
TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

bot = Bot(token=TOKEN)

RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ✅ SEC Email
SEC_HEADERS = {
    "User-Agent": "AlphaMarketBot/1.0 (aktfaaksa@gmail.com)"
}

# ===== STATE =====
sent = set()
sent_sec = set()
last_sent_symbol = {}
last_geo_time = 0

# ===== KEYWORDS =====
STRONG = ["earnings","merger","acquisition","deal","contract","fda","approval"]
WEAK = ["analysis","why","opinion","watch"]

# ===== UTIL =====
def tr(x):
    try:
        if len(x) > 400:
            return x
        return GoogleTranslator(source='auto', target='ar').translate(x)
    except:
        return x

def can_send(symbol):
    now = time.time()
    if symbol in last_sent_symbol and now - last_sent_symbol[symbol] < 1800:
        return False
    last_sent_symbol[symbol] = now
    return True

def symbol(title):
    m = re.findall(r'\(([A-Z]{1,5})\)', title.upper())
    return m[0] if m else None

# ===== GEO SMART =====
def geo_score(title):
    t = title.lower()
    score = 0

    # كلمات قوية
    if any(x in t for x in ["attack","strike","war","missile"]):
        score += 3

    if any(x in t for x in ["sanctions","ban","tariffs"]):
        score += 2

    if any(x in t for x in ["agreement","deal","ceasefire"]):
        score += 2

    # مناطق حساسة
    if any(x in t for x in ["iran","russia","ukraine","middle east"]):
        score += 2

    if any(x in t for x in ["oil","gas","port"]):
        score += 2

    return score

def geo_level(score):
    if score >= 5:
        return "🔴 عالي"
    elif score >= 3:
        return "🟡 متوسط"
    return "🟢 ضعيف"

def geo_impact(title):
    t = title.lower()

    if any(x in t for x in ["oil","gas","iran","russia","middle east","port"]):
        return "🛢️ النفط / الطاقة"

    if any(x in t for x in ["fed","inflation","rates"]):
        return "💰 السوق / الفائدة"

    if any(x in t for x in ["china","trade","tariffs"]):
        return "📦 التجارة"

    return "📊 السوق العام"

async def send_geo(n):
    global last_geo_time

    title, link = n["title"], n["link"]

    score = geo_score(title)

    if score < 3:
        return

    if time.time() - last_geo_time < 1800:
        return

    last_geo_time = time.time()

    level = geo_level(score)
    impact = geo_impact(title)

    msg = f"""🌍 حدث جيوسياسي مهم

📰 {title}
🇸🇦 {tr(title)}

{impact}
⚡️ التصنيف: {level}

⚠️ راقب السوق
🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== AI =====
def ai_analyze(text):
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "openai/gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": f"""
حلل هذا التقرير المالي واطلع أهم النقاط:

- الحدث
- الأرقام
- التأثير

بشكل عربي مختصر:

{text[:2000]}
"""
            }]
        }

        r = requests.post(url, headers=headers, json=data, timeout=20)
        return r.json()["choices"][0]["message"]["content"]

    except:
        return None

# ===== NEWS =====
async def send_news(session, n):
    title, link = n["title"], n["link"]

    h = hashlib.md5((title + link).encode()).hexdigest()
    if h in sent:
        return
    sent.add(h)

    await send_geo(n)

    if any(x in title.lower() for x in WEAK):
        return

    s = symbol(title)
    if not s or not can_send(s):
        return

    st = await session.get(f"https://finnhub.io/api/v1/quote?symbol={s}&token={FINNHUB}")
    data = await st.json()

    price = data.get("c", 0)
    change = data.get("dp", 0)

    if price == 0:
        return

    msg = f"""🟡 متابعة

🏢 {s}

📰 {title}
🇸🇦 {tr(title)}

📊 {price}$ | {round(change,2)}%

🔗 {link}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== SEC (AI) =====
async def send_sec(session):
    url = "https://data.sec.gov/submissions/CIK0000320193.json"

    try:
        async with session.get(url, headers=SEC_HEADERS) as r:
            data = await r.text()
    except:
        return

    if "8-K" not in data:
        return

    summary = ai_analyze(data)

    if not summary:
        return

    msg = f"""🏛️ SEC مهم

{summary}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== SYSTEM =====
async def startup():
    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text="✅ البوت يعمل (v31)")

async def heartbeat():
    while True:
        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="🟢 النظام مستقر")
        await asyncio.sleep(3600)

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v31")

    async with aiohttp.ClientSession() as session:
        await startup()
        asyncio.create_task(heartbeat())

        while True:
            try:
                for url in RSS_FEEDS:
                    f = feedparser.parse(url)
                    for e in f.entries:
                        await send_news(session, {"title": e.title, "link": e.link})

                await send_sec(session)

                await asyncio.sleep(300)

            except Exception as e:
                print("ERROR:", e)
                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())