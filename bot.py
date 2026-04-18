# ===== Alpha Market Intelligence v32 (Clean Decision Bot) 🚀 =====

import asyncio, aiohttp, feedparser, hashlib, os, re, time, requests
from telegram import Bot
from deep_translator import GoogleTranslator

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
FINNHUB = os.getenv("FINNHUB_API_KEY")
OPENROUTER = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]
bot = Bot(token=BOT_TOKEN)

SEC_HEADERS = {
    "User-Agent": "AlphaBot/1.0 (aktfaaksa@gmail.com)"
}

RSS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

sent = set()
cooldown = {}
last_geo = 0

# ===== UTIL =====
def tr(x):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(x) if len(x) < 300 else x
    except:
        return x

def can_send(s):
    now = time.time()
    if s in cooldown and now - cooldown[s] < 1800:
        return False
    cooldown[s] = now
    return True

def symbol(t):
    m = re.findall(r'\(([A-Z]{1,5})\)', t)
    return m[0] if m else None

# ===== GEO =====
def geo_score(t):
    t = t.lower()
    score = 0

    if any(x in t for x in ["attack","strike","war"]): score += 4
    if any(x in t for x in ["oil","hormuz","gas"]): score += 3
    if any(x in t for x in ["iran","russia","ukraine"]): score += 2
    if re.search(r'\d+%', t): score += 3
    if any(x in t for x in ["rally","crash","surge"]): score += 2

    return score

def geo_level(s):
    return "🔴 عالي" if s >= 6 else "🟡 متوسط" if s >= 3 else None

def geo_impact(t):
    t = t.lower()
    if any(x in t for x in ["oil","iran","hormuz","russia"]):
        return "🛢️ النفط / الطاقة"
    if "fed" in t:
        return "💰 الفائدة"
    return "📊 السوق"

async def send_geo(n):
    global last_geo
    score = geo_score(n["title"])
    lvl = geo_level(score)

    if not lvl or time.time() - last_geo < 1800:
        return

    last_geo = time.time()

    msg = f"""🌍 حدث مهم

📰 {n["title"]}
🇸🇦 {tr(n["title"])}

{geo_impact(n["title"])}
⚡️ {lvl}
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== AI (Decision Style) =====
def ai(text):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": f"""
استخرج فقط:

👤 من؟
📊 ماذا حدث؟
💰 الرقم؟
⚡️ التأثير (إيجابي/سلبي/محايد)

بدون شرح - 4 سطور فقط:

{text[:1500]}
"""
                }]
            },
            timeout=15
        )
        return r.json()["choices"][0]["message"]["content"]
    except:
        return None

# ===== NEWS =====
async def send_news(session, n):
    h = hashlib.md5((n["title"] + n["link"]).encode()).hexdigest()
    if h in sent: return
    sent.add(h)

    await send_geo(n)

    s = symbol(n["title"])
    if not s or not can_send(s): return

    try:
        async with session.get(f"https://finnhub.io/api/v1/quote?symbol={s}&token={FINNHUB}") as r:
            d = await r.json()
    except:
        return

    if not d.get("c"): return

    msg = f"""🟡 خبر

🏢 {s}
📰 {n["title"]}
🇸🇦 {tr(n["title"])}

📊 {d['c']}$ | {round(d['dp'],2)}%
"""

    for c in CHAT_IDS:
        await bot.send_message(chat_id=c, text=msg)

# ===== SEC =====
async def send_sec(session):
    url = "https://data.sec.gov/submissions/CIK0000320193.json"

    try:
        async with session.get(url, headers=SEC_HEADERS) as r:
            d = await r.json()
    except:
        return

    f = d.get("filings", {}).get("recent", {})
    if not f: return

    for i in range(len(f.get("form", []))):
        if f["form"][i] not in ["8-K","3","4"]:
            continue

        acc = f["accessionNumber"][i].replace("-", "")
        link = f"https://www.sec.gov/Archives/edgar/data/320193/{acc}/{f['accessionNumber'][i]}.txt"

        try:
            async with session.get(link, headers=SEC_HEADERS) as r:
                txt = await r.text()
        except:
            continue

        # فلترة ذكية
        if not any(x in txt.lower() for x in ["share","stock","officer","ceo"]):
            continue

        summary = ai(txt)
        if not summary:
            return

        msg = f"""🏛️ SEC

📄 {f["form"][i]}

{summary}
"""

        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text=msg)

        break

# ===== MAIN =====
async def main():
    print("🚀 RUNNING v32")

    async with aiohttp.ClientSession() as session:
        for c in CHAT_IDS:
            await bot.send_message(chat_id=c, text="✅ البوت جاهز")

        while True:
            try:
                for url in RSS:
                    feed = feedparser.parse(url)
                    for e in feed.entries:
                        await send_news(session, {"title": e.title, "link": e.link})

                await send_sec(session)

                await asyncio.sleep(300)

            except Exception as e:
                print(e)
                await asyncio.sleep(60)

asyncio.run(main())