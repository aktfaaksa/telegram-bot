# AlphaBot Pro v4.2 CLEAN

import os, time, requests, feedparser, hashlib, re
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

CHAT_IDS = [int(os.getenv("CHAT_ID")), 6315087880]

RSS = [
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html"
]

BLOCK = ["crypto","coin","token","video","opinion"]
MACRO = ["oil","dollar","gold","bond","iran","war","inflation","rates","fed"]
IMPORTANT = ["earnings","revenue","profit","merger","acquisition","guidance","shares","stock","drop","plunge","surge","jump"]

seen = set()

def send(msg):
    for c in CHAT_IDS:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      json={"chat_id": c, "text": msg})

def is_new(t):
    h = hashlib.md5(t.encode()).hexdigest()
    if h in seen: return False
    seen.add(h)
    return True

def recent(p):
    if not p: return True
    t = datetime(*p[:6], tzinfo=timezone.utc)
    return (datetime.now(timezone.utc)-t).seconds < 10800

def ai(prompt):
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={"model":"openai/gpt-4o-mini",
                  "messages":[{"role":"user","content":prompt}]})
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""

def get_stock(title):
    prompt = f'Extract US ticker only JSON: {{"ticker":"...","company":"..."}} -> {title}'
    try:
        data = eval(ai(prompt))
        if data.get("ticker") and len(data["ticker"]) <= 5:
            return data["ticker"], data["company"]
    except:
        pass
    return None, None

def analyze(title):
    prompt = f"""
اعطني فقط:
- قرار: BUY أو SELL أو NEUTRAL
- قوة: رقم من 1 الى 10
- سبب مختصر عربي

{title}
"""
    return ai(prompt)

def parse(text):
    signal = "⚪ NEUTRAL"
    if "BUY" in text: signal = "🟢 BUY"
    if "SELL" in text: signal = "🔴 SELL"

    m = re.search(r'(\d+)', text)
    score = int(m.group(1)) if m else 5
    score = min(score,10)

    return signal, score

def price(t):
    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={t}&token={FINNHUB_API_KEY}")
        return r.json().get("c")
    except:
        return None

def run():
    send("🚀 AlphaBot v4.2 CLEAN Started")

    while True:
        news = []
        for u in RSS:
            f = feedparser.parse(u)
            for e in f.entries:
                news.append(e)

        for n in news:
            title = n.title.lower()

            if any(w in title for w in BLOCK): continue
            if any(w in title for w in MACRO): continue
            if not any(w in title for w in IMPORTANT): continue
            if not is_new(n.title): continue
            if not recent(n.get("published_parsed")): continue

            ticker, company = get_stock(n.title)

            # ❗ أهم سطر
            if not ticker:
                continue

            analysis = analyze(n.title)
            signal, score = parse(analysis)
            p = price(ticker)

            msg = f"""
📊 Alpha Signal

🏢 {company}
💲 {ticker}
💰 {p if p else "N/A"}

📢 {signal}
⭐ {score}/10

{analysis}

🔗 {n.link}
"""
            send(msg)

        time.sleep(300)

if __name__ == "__main__":
    run()