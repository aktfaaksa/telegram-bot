# ==============================
# AlphaBot Pro
# Version: 3.1.0 (FIXED & RELAXED)
# ==============================

import os
import time
import requests
import feedparser
import hashlib
import json
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(os.getenv("CHAT_ID", 0)), 6315087880]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

VERSION = "3.1.0"
CYCLE_TIME = 300
MAX_NEWS_PER_CYCLE = 15

RSS_FEEDS = [
    "https://www.benzinga.com/feed",
    "https://www.reuters.com/markets/us/rss",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://finance.yahoo.com/rss/",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.investing.com/rss/news_25.rss",
    "https://seekingalpha.com/feed.xml"
]

SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/3.1 (Financial Bot; aktfaaksa@gmail.com)"
}

SEC_KEYWORDS = [
    "bankruptcy","merger","acquisition","earnings",
    "results","agreement","deal","delist"
]

IMPORTANT_KEYWORDS = [
    "earnings","revenue","profit","merger","acquisition",
    "bankruptcy","dividend","guidance","results","deal"
]

BLOCK_WORDS = [
    "analyst","price target","opinion","strategist"
]

seen_links = set()
seen_titles = set()
stock_cache = {}

def send_message(text):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
        except:
            pass

def startup():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_message(f"""
🤖 AlphaBot Pro

📦 Version: {VERSION}
🟢 RELAXED MODE ACTIVE
⏰ {now}
""")

def fetch_news():
    data = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            data.append({
                "title": e.title,
                "link": e.link,
                "published": e.get("published_parsed"),
                "source": "NEWS"
            })
    return data

def fetch_sec():
    try:
        res = requests.get(SEC_RSS, headers=SEC_HEADERS)
        feed = feedparser.parse(res.text)

        data = []
        for e in feed.entries:
            t = e.title.lower()
            if not any(k in t for k in SEC_KEYWORDS):
                continue

            data.append({
                "title": e.title,
                "link": e.link,
                "published": e.get("published_parsed"),
                "source": "SEC"
            })
        return data
    except:
        return []

def is_duplicate(news):
    h = hashlib.md5(news["title"].lower().encode()).hexdigest()
    if news["link"] in seen_links or h in seen_titles:
        return True

    seen_links.add(news["link"])
    seen_titles.add(h)
    return False

def is_recent(published, hours=4):
    if not published:
        return True  # خففنا الشرط

    t = datetime(*published[:6], tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - t).total_seconds() <= hours * 3600

def score_news(text):
    text = text.lower()
    score = 0

    for w in IMPORTANT_KEYWORDS:
        if w in text:
            score += 3

    for w in BLOCK_WORDS:
        if w in text:
            score -= 2

    return score

def call_ai(prompt, model):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return r.json()["choices"][0]["message"]["content"]
    except:
        return ""

def extract_stock(text):
    prompt = f"""
Extract company and ticker if possible.
Return JSON:
{{"company":"...","ticker":"..."}}

{text}
"""
    res = call_ai(prompt, "anthropic/claude-3.7-sonnet")

    try:
        return json.loads(res)
    except:
        return {"company":"Unknown","ticker":None}

def analyze(text):
    prompt = f"""
حلل الخبر:

- ملخص عربي
- صنف: شراء / بيع / محايد
- قوة الخبر من 1 الى 10

{text}
"""
    return call_ai(prompt, "openai/gpt-4o-mini")

def extract_score(ai_text):
    try:
        nums = [int(s) for s in ai_text.split() if s.isdigit()]
        return max(nums) if nums else 5
    except:
        return 5

def get_signal(text):
    if "شراء" in text:
        return "🟢 شراء"
    elif "بيع" in text:
        return "🔴 بيع"
    return "⚪ محايد"

def get_price(ticker):
    if not ticker:
        return None

    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        return requests.get(url).json().get("c")
    except:
        return None

def run():
    while True:
        all_news = fetch_news() + fetch_sec()
        candidates = []

        print("TOTAL NEWS:", len(all_news))

        for news in all_news:

            if is_duplicate(news):
                continue

            if not is_recent(news["published"], 4):
                continue

            base_score = score_news(news["title"])

            stock = extract_stock(news["title"])
            ticker = stock.get("ticker")
            company = stock.get("company")

            ai_text = analyze(news["title"])
            ai_score = extract_score(ai_text)

            total_score = base_score + ai_score

            candidates.append({
                "news": news,
                "ticker": ticker,
                "company": company,
                "analysis": ai_text,
                "score": total_score
            })

        print("CANDIDATES:", len(candidates))

        candidates.sort(key=lambda x: x["score"], reverse=True)

        count = 0

        for item in candidates:
            news = item["news"]

            signal = get_signal(item["analysis"])
            price = get_price(item["ticker"])

            tag = "🏛 SEC" if news["source"] == "SEC" else "📰 News"

            msg = f"""
{tag}

🏢 {item['company']}
💲 {item['ticker'] if item['ticker'] else "N/A"}
💰 {price if price else "N/A"}

📊 {signal}
⭐ Score: {item['score']}

{item['analysis']}

🔗 {news['link']}
"""

            send_message(msg)

            if news["source"] != "SEC":
                count += 1

            if count >= MAX_NEWS_PER_CYCLE:
                break

        time.sleep(CYCLE_TIME)

if __name__ == "__main__":
    startup()
    run()