import os
import time
import requests
import feedparser
import hashlib
import json
from datetime import datetime, timezone

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(os.getenv("CHAT_ID", 0)), 6315087880]

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# ===== إعدادات =====
VERSION = "2.0.0"
CYCLE_TIME = 300
MAX_NEWS_PER_CYCLE = 15

# ===== RSS =====
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

# ===== SEC =====
SEC_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"

SEC_HEADERS = {
    "User-Agent": "AlphaBot/2.0 (Financial Bot; aktfaaksa@gmail.com)"
}

SEC_KEYWORDS = [
    "bankruptcy","merger","acquisition","earnings",
    "results","agreement","deal","delist"
]

# ===== فلترة =====
IMPORTANT_KEYWORDS = [
    "earnings","revenue","profit","merger","acquisition",
    "bankruptcy","dividend","guidance","results","deal"
]

BLOCK_WORDS = [
    "analyst","price target","opinion","strategist"
]

# ===== Cache =====
seen_links = set()
seen_titles = set()
stock_cache = {}

# ===== Telegram =====
def send_message(text):
    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
        except:
            pass

# ===== Startup =====
def startup():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_message(f"""
🤖 AlphaBot Pro

📦 Version: {VERSION}
🟢 Running
⏰ {now}
""")

# ===== Fetch News =====
def fetch_news():
    news = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            news.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published_parsed"),
                "source": "NEWS"
            })

    return news

# ===== Fetch SEC =====
def fetch_sec_news():
    try:
        response = requests.get(SEC_RSS, headers=SEC_HEADERS)
        feed = feedparser.parse(response.text)

        news = []

        for entry in feed.entries:
            title = entry.title.lower()

            if not any(k in title for k in SEC_KEYWORDS):
                continue

            news.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published_parsed"),
                "source": "SEC"
            })

        return news
    except:
        return []

# ===== Filters =====
def score_news(text):
    text = text.lower()
    score = 0

    for w in IMPORTANT_KEYWORDS:
        if w in text:
            score += 2

    for w in BLOCK_WORDS:
        if w in text:
            score -= 3

    return score

def is_important(text):
    return score_news(text) > 1

def is_duplicate(news):
    link = news["link"]
    title = hashlib.md5(news["title"].lower().encode()).hexdigest()

    if link in seen_links or title in seen_titles:
        return True

    seen_links.add(link)
    seen_titles.add(title)
    return False

def is_recent(published, hours=2):
    if not published:
        return False

    news_time = datetime(*published[:6], tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    return (now - news_time).total_seconds() <= hours * 3600

# ===== AI =====
def call_ai(prompt, model):
    try:
        res = requests.post(
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
        return res.json()["choices"][0]["message"]["content"]
    except:
        return None

def extract_stock(text):
    prompt = f"""
Extract company name and US ticker.
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

{text}
"""
    return call_ai(prompt, "openai/gpt-4o-mini") or ""

# ===== Market =====
def is_us_stock(ticker):
    if not ticker:
        return False

    if ticker in stock_cache:
        return stock_cache[ticker]

    try:
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_API_KEY}"
        data = requests.get(url).json()
        res = data.get("country") == "US"
        stock_cache[ticker] = res
        return res
    except:
        return False

def get_price(ticker):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        return requests.get(url).json().get("c")
    except:
        return None

# ===== Signal =====
def get_signal(text):
    if "شراء" in text:
        return "🟢 شراء"
    elif "بيع" in text:
        return "🔴 بيع"
    return None

# ===== Main =====
def run():
    while True:
        news_list = fetch_news() + fetch_sec_news()
        count = 0

        for news in news_list:

            if is_duplicate(news):
                continue

            if not is_recent(news["published"], 2):
                continue

            if news["source"] != "SEC" and not is_important(news["title"]):
                continue

            stock = extract_stock(news["title"])
            ticker = stock.get("ticker")
            company = stock.get("company")

            if not is_us_stock(ticker):
                continue

            analysis = analyze(news["title"])
            signal = get_signal(analysis)

            if not signal:
                continue

            price = get_price(ticker)
            tag = "🏛 SEC" if news["source"] == "SEC" else "📰 News"

            msg = f"""
{tag}

🏢 {company}
💲 {ticker}
💰 {price if price else "N/A"}

📊 {signal}

{analysis}

🔗 {news['link']}
"""

            send_message(msg)

            if news["source"] != "SEC":
                count += 1

            if count >= MAX_NEWS_PER_CYCLE:
                break

        time.sleep(CYCLE_TIME)

# ===== Start =====
if __name__ == "__main__":
    startup()
    run()