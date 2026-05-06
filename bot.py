# AlphaBot Pro v5.0 Smart News
# RSS + Finnhub + SEC + OpenRouter + Telegram

import os
import re
import json
import time
import hashlib
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


# =========================
# 1) SETTINGS
# =========================

VERSION = "v5.0 Smart News"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "AlphaBot aktfaaksa@gmail.com")

# الآيدي القديم الموجود في كودك السابق
DEFAULT_EXTRA_CHAT_IDS = [6315087880]

CHECK_EVERY_SECONDS = 90
MAX_NEWS_AGE_MINUTES = 60
MIN_IMPACT_SCORE = 6
MAX_ALERTS_PER_CYCLE = 5
MAX_DAILY_ALERTS = 80
TICKER_COOLDOWN_MINUTES = 20

STATE_FILE = "seen_news.json"

RSS_SOURCES = [
    {
        "name": "Reuters US Markets",
        "url": "https://www.reuters.com/markets/us/rss"
    },
    {
        "name": "CNBC Markets",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    },
    {
        "name": "Nasdaq News",
        "url": "https://www.nasdaq.com/feed/rssoutbound?category=Stocks"
    }
]

BLOCK_WORDS = [
    "crypto", "coin", "token", "bitcoin", "ethereum",
    "video", "podcast", "trailer", "sports", "nfl", "nba"
]

IMPORTANT_KEYWORDS = [
    "earnings", "revenue", "eps", "guidance", "outlook",
    "raises guidance", "cuts guidance", "beats", "misses",
    "fda", "approval", "rejection", "phase 1", "phase 2", "phase 3",
    "merger", "acquisition", "acquires", "buyout",
    "offering", "public offering", "registered direct",
    "bankruptcy", "chapter 11", "investigation", "sec investigation",
    "contract", "agreement", "partnership", "order",
    "downgrade", "upgrade", "price target",
    "8-k", "10-q", "10-k", "s-3", "form 4"
]

US_MARKET_KEYWORDS = [
    "fed", "federal reserve", "cpi", "inflation", "jobs report",
    "payrolls", "interest rates", "treasury yields", "pce"
]


# =========================
# 2) DATE HELPERS
# =========================

def now_utc():
    return datetime.now(timezone.utc)


def current_date_key():
    return now_utc().strftime("%Y-%m-%d")


# =========================
# 3) CHAT IDS
# =========================

def get_chat_ids():
    ids = []

    raw_chat_ids = os.getenv("CHAT_IDS", "").strip()

    if raw_chat_ids:
        for item in raw_chat_ids.split(","):
            item = item.strip()
            if item.isdigit():
                ids.append(int(item))

    if CHAT_ID and str(CHAT_ID).strip().isdigit():
        ids.append(int(CHAT_ID))

    for extra_id in DEFAULT_EXTRA_CHAT_IDS:
        ids.append(extra_id)

    unique_ids = []
    for cid in ids:
        if cid not in unique_ids:
            unique_ids.append(cid)

    return unique_ids


CHAT_IDS = get_chat_ids()


# =========================
# 4) TELEGRAM
# =========================

def send_telegram(message):
    if not BOT_TOKEN:
        print("BOT_TOKEN missing", flush=True)
        return

    if not CHAT_IDS:
        print("CHAT_IDS missing", flush=True)
        return

    for chat_id in CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "disable_web_page_preview": True
                },
                timeout=15
            )
        except Exception as e:
            print(f"Telegram send error to {chat_id}: {e}", flush=True)


def startup_message():
    msg = f"""✅ AlphaBot Connected

الإصدار: {VERSION}
الحالة: يعمل الآن
المصادر: RSS + Finnhub + SEC + OpenRouter
وضع الإرسال: الأخبار المؤثرة فقط
الفلترة: خبر جديد + غير مكرر + قوة 7/10 أو أعلى
عدد المستلمين: {len(CHAT_IDS)}
"""
    send_telegram(msg)


# =========================
# 5) STATE / DUPLICATES
# =========================

def load_state():
    default_state = {
        "seen": [],
        "ticker_last_alert": {},
        "daily": {
            "date": current_date_key(),
            "count": 0
        }
    }

    if not os.path.exists(STATE_FILE):
        return default_state

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        state.setdefault("seen", [])
        state.setdefault("ticker_last_alert", {})
        state.setdefault("daily", {"date": current_date_key(), "count": 0})

        if state["daily"].get("date") != current_date_key():
            state["daily"] = {"date": current_date_key(), "count": 0}

        return state

    except Exception as e:
        print(f"load_state error: {e}", flush=True)
        return default_state


def save_state(state):
    try:
        state["seen"] = state.get("seen", [])[-3000:]

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"save_state error: {e}", flush=True)


def make_news_id(item):
    raw = f"{item.get('source','')}|{item.get('ticker','')}|{item.get('title','')}|{item.get('url','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# =========================
# 6) TIME HELPERS
# =========================

def parse_rss_time(entry):
    try:
        if entry.get("published_parsed"):
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        if entry.get("updated_parsed"):
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        if entry.get("published"):
            dt = parsedate_to_datetime(entry.published)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        if entry.get("updated"):
            dt = parsedate_to_datetime(entry.updated)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

    except Exception:
        return None

    return None


def is_fresh_news(published_at):
    if not published_at:
        return False

    age = now_utc() - published_at

    if age.total_seconds() < 0:
        return True

    return age <= timedelta(minutes=MAX_NEWS_AGE_MINUTES)


def human_age(published_at):
    if not published_at:
        return "غير معروف"

    minutes = int((now_utc() - published_at).total_seconds() / 60)

    if minutes < 1:
        return "الآن"
    if minutes == 1:
        return "قبل دقيقة"
    if minutes < 60:
        return f"قبل {minutes} دقيقة"

    hours = minutes // 60
    return f"قبل {hours} ساعة"


# =========================
# 7) BASIC FILTERS
# =========================

def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def is_blocked(title):
    title_l = title.lower()
    return any(word in title_l for word in BLOCK_WORDS)


def has_important_keyword(title):
    title_l = title.lower()
    return any(word in title_l for word in IMPORTANT_KEYWORDS)


def has_us_market_keyword(title):
    title_l = title.lower()
    return any(word in title_l for word in US_MARKET_KEYWORDS)


def extract_possible_ticker(text):
    if not text:
        return ""

    patterns = [
        r"\bNASDAQ:\s*([A-Z]{1,5})\b",
        r"\bNYSE:\s*([A-Z]{1,5})\b",
        r"\bAMEX:\s*([A-Z]{1,5})\b",
        r"\(([A-Z]{1,5})\)",
        r"\b([A-Z]{2,5})\b"
    ]

    bad_words = {
        "CEO", "CFO", "USA", "SEC", "FDA", "EPS", "ETF", "IPO",
        "AI", "US", "DJIA", "GDP", "CPI", "PCE", "FOMC", "THE",
        "AND", "FOR", "NEW", "NYSE", "NASDAQ"
    }

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            ticker = m.strip().upper()
            if ticker not in bad_words:
                return ticker

    return ""


# =========================
# 8) FETCH RSS
# =========================

def fetch_rss_news():
    items = []

    print("Fetching RSS news...", flush=True)

    for src in RSS_SOURCES:
        try:
            r = requests.get(
                src["url"],
                headers={
                    "User-Agent": "AlphaBot News Bot",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*"
                },
                timeout=15
            )

            if r.status_code != 200:
                print(f"RSS status error {src['name']}: {r.status_code}", flush=True)
                continue

            feed = feedparser.parse(r.text)

            count_before = len(items)

            for entry in feed.entries[:30]:
                title = clean_text(entry.get("title"))
                url = clean_text(entry.get("link"))
                published_at = parse_rss_time(entry)

                if not title or not url:
                    continue

                items.append({
                    "source": src["name"],
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "ticker": extract_possible_ticker(title),
                    "raw": ""
                })

            print(
                f"RSS OK {src['name']}: {len(items) - count_before} items",
                flush=True
            )

        except Exception as e:
            print(f"RSS error {src['name']}: {e}", flush=True)

    return items


# =========================
# 9) FETCH FINNHUB
# =========================

def fetch_finnhub_news():
    items = []

    if not FINNHUB_API_KEY:
        print("Finnhub skipped: missing API key", flush=True)
        return items

    print("Fetching Finnhub news...", flush=True)

    try:
        url = "https://finnhub.io/api/v1/news"
        params = {
            "category": "general",
            "token": FINNHUB_API_KEY
        }

        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            print(f"Finnhub status error: {r.status_code} | {r.text[:200]}", flush=True)
            return items

        data = r.json()

        if not isinstance(data, list):
            print("Finnhub returned non-list data", flush=True)
            return items

        for n in data[:50]:
            title = clean_text(n.get("headline"))
            news_url = clean_text(n.get("url"))
            summary = clean_text(n.get("summary"))
            source = clean_text(n.get("source")) or "Finnhub"

            ts = n.get("datetime")
            published_at = None

            if ts:
                try:
                    published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                except Exception:
                    published_at = None

            if not title or not news_url:
                continue

            full_text = f"{title} {summary}"

            items.append({
                "source": f"Finnhub / {source}",
                "title": title,
                "url": news_url,
                "published_at": published_at,
                "ticker": extract_possible_ticker(full_text),
                "raw": summary
            })

        print(f"Finnhub OK: {len(items)} items", flush=True)

    except Exception as e:
        print(f"Finnhub error: {e}", flush=True)

    return items


# =========================
# 10) FETCH SEC CURRENT FILINGS
# =========================

def fetch_sec_news():
    items = []

    print("Fetching SEC news...", flush=True)

    sec_feeds = [
        {
            "name": "SEC 8-K",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&owner=include&count=40&output=atom"
        },
        {
            "name": "SEC S-3",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=S-3&owner=include&count=40&output=atom"
        },
        {
            "name": "SEC 10-Q",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-Q&owner=include&count=40&output=atom"
        }
    ]

    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/atom+xml, application/xml, text/xml, */*"
    }

    for feed_info in sec_feeds:
        try:
            r = requests.get(feed_info["url"], headers=headers, timeout=15)

            if r.status_code != 200:
                print(f"SEC status error {feed_info['name']}: {r.status_code}", flush=True)
                continue

            feed = feedparser.parse(r.text)

            count_before = len(items)

            for entry in feed.entries[:25]:
                title = clean_text(entry.get("title"))
                url = clean_text(entry.get("link"))
                published_at = parse_rss_time(entry)

                if not title or not url:
                    continue

                items.append({
                    "source": feed_info["name"],
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "ticker": extract_possible_ticker(title),
                    "raw": ""
                })

            print(
                f"SEC OK {feed_info['name']}: {len(items) - count_before} items",
                flush=True
            )

        except Exception as e:
            print(f"SEC error {feed_info['name']}: {e}", flush=True)

    return items


# =========================
# 11) OPENROUTER AI ANALYSIS
# =========================

def analyze_with_ai(item):
    if not OPENROUTER_API_KEY:
        print("OpenRouter skipped: missing API key", flush=True)
        return None

    title = item.get("title", "")
    source = item.get("source", "")
    raw = item.get("raw", "")
    ticker = item.get("ticker", "")

    prompt = f"""
أنت محلل أخبار للأسهم الأمريكية فقط.

حلل الخبر التالي وارجع JSON فقط بدون شرح إضافي.

المطلوب:
- إذا الخبر لا يخص سهم أمريكي أو حدث قوي يؤثر على السوق الأمريكي، اجعل send=false.
- لا ترسل أخبار كريبتو أو فيديو أو مقالات رأي ضعيفة.
- لا تبالغ في التأثير.
- impact_score من 1 إلى 10.
- أرسل فقط الأخبار التي قد تحرك السهم أو السوق.
- اللغة العربية مختصرة وواضحة.

JSON format:
{{
  "send": true,
  "ticker": "RDW",
  "category": "Earnings / Guidance / SEC / Offering / FDA / Contract / Analyst / M&A / Macro / Other",
  "impact_score": 8,
  "direction": "positive / negative / mixed / neutral",
  "title_ar": "ترجمة العنوان للعربية",
  "summary_ar": "ملخص عربي قصير",
  "why_important_ar": "سبب أهمية الخبر",
  "trading_note_ar": "ملاحظة تداول مختصرة"
}}

الخبر:
Source: {source}
Ticker guess: {ticker}
Title: {title}
Extra: {raw}
"""

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2
            },
            timeout=25
        )

        if r.status_code != 200:
            print(f"OpenRouter status error: {r.status_code} | {r.text[:300]}", flush=True)
            return None

        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()

        content = content.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(content)
        return parsed

    except Exception as e:
        print(f"OpenRouter error: {e}", flush=True)
        return None


# =========================
# 12) SEND DECISION
# =========================

def ticker_cooldown_ok(state, ticker):
    if not ticker:
        return True

    ticker = ticker.upper()
    last = state.get("ticker_last_alert", {}).get(ticker)

    if not last:
        return True

    try:
        last_dt = datetime.fromisoformat(last)

        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        return now_utc() - last_dt >= timedelta(minutes=TICKER_COOLDOWN_MINUTES)

    except Exception:
        return True


def daily_limit_ok(state):
    daily = state.get("daily", {})

    if daily.get("date") != current_date_key():
        state["daily"] = {
            "date": current_date_key(),
            "count": 0
        }
        return True

    return int(daily.get("count", 0)) < MAX_DAILY_ALERTS


def should_send_alert(item, analysis, state):
    if not analysis:
        return False, "AI analysis failed"

    if not analysis.get("send"):
        return False, "AI decided not important"

    try:
        score = int(analysis.get("impact_score", 0))
    except Exception:
        score = 0

    if score < MIN_IMPACT_SCORE:
        return False, f"low score {score}"

    ticker = clean_text(analysis.get("ticker") or item.get("ticker", "")).upper()
    category = clean_text(analysis.get("category", "")).lower()

    if not ticker and "macro" not in category:
        return False, "no ticker"

    if not ticker_cooldown_ok(state, ticker):
        urgent_categories = ["offering", "fda", "m&a", "sec", "bankruptcy"]
        if not any(x in category for x in urgent_categories):
            return False, f"cooldown for {ticker}"

    if not daily_limit_ok(state):
        return False, "daily limit reached"

    return True, "ok"


# =========================
# 13) FORMAT ALERT
# =========================

def format_alert(item, analysis):
    ticker = clean_text(analysis.get("ticker") or item.get("ticker", "")).upper()
    category = clean_text(analysis.get("category", "Other"))
    direction = clean_text(analysis.get("direction", "mixed"))
    score = analysis.get("impact_score", "?")

    title = clean_text(item.get("title"))
    title_ar = clean_text(analysis.get("title_ar"))
    summary_ar = clean_text(analysis.get("summary_ar"))
    why = clean_text(analysis.get("why_important_ar"))
    trading_note = clean_text(analysis.get("trading_note_ar"))
    url = item.get("url")
    source = item.get("source")
    age = human_age(item.get("published_at"))

    if not ticker:
        ticker = "السوق الأمريكي"

    msg = f"""🚨 خبر مؤثر على سهم أمريكي

🏷️ السهم: {ticker}
📌 نوع الخبر: {category}
📊 التأثير المتوقع: {direction}
🔥 قوة الخبر: {score}/10
⏱️ وقت الخبر: {age}
📰 المصدر: {source}

العنوان:
{title}

🌍 الترجمة:
{title_ar}

🧠 لماذا الخبر مهم؟
{why}

📌 الملخص:
{summary_ar}

📉 ملاحظة تداول:
{trading_note}

🔗 الرابط:
{url}
"""

    return msg


# =========================
# 14) PROCESS NEWS
# =========================

def process_news_item(item, state):
    title = clean_text(item.get("title"))
    url = clean_text(item.get("url"))

    if not title or not url:
        return False

    if is_blocked(title):
        return False

    if not is_fresh_news(item.get("published_at")):
        return False

    source_name = item.get("source", "")

    if (
        not has_important_keyword(title)
        and not has_us_market_keyword(title)
        and "SEC" not in source_name
    ):
        return False

    news_id = make_news_id(item)

    if news_id in state.get("seen", []):
        return False

    analysis = analyze_with_ai(item)

    ok, reason = should_send_alert(item, analysis, state)

    if not ok:
        print(f"Skip: {reason} | {title}", flush=True)
        state["seen"].append(news_id)
        save_state(state)
        return False

    alert = format_alert(item, analysis)
    send_telegram(alert)

    ticker = clean_text(analysis.get("ticker") or item.get("ticker", "")).upper()

    if ticker:
        state.setdefault("ticker_last_alert", {})[ticker] = now_utc().isoformat()

    state.setdefault("daily", {})

    if state["daily"].get("date") != current_date_key():
        state["daily"] = {
            "date": current_date_key(),
            "count": 0
        }

    state["daily"]["count"] = int(state["daily"].get("count", 0)) + 1
    state["seen"].append(news_id)
    save_state(state)

    return True


# =========================
# 15) COLLECT NEWS
# =========================

def collect_all_news():
    all_items = []

    try:
        rss_items = fetch_rss_news()
        all_items.extend(rss_items)
        print(f"Collected RSS: {len(rss_items)}", flush=True)
    except Exception as e:
        print(f"collect RSS error: {e}", flush=True)

    try:
        finnhub_items = fetch_finnhub_news()
        all_items.extend(finnhub_items)
        print(f"Collected Finnhub: {len(finnhub_items)}", flush=True)
    except Exception as e:
        print(f"collect Finnhub error: {e}", flush=True)

    try:
        sec_items = fetch_sec_news()
        all_items.extend(sec_items)
        print(f"Collected SEC: {len(sec_items)}", flush=True)
    except Exception as e:
        print(f"collect SEC error: {e}", flush=True)

    all_items = [
        x for x in all_items
        if x.get("published_at") is not None
    ]

    all_items.sort(
        key=lambda x: x.get("published_at"),
        reverse=True
    )

    print(f"Total collected with dates: {len(all_items)}", flush=True)

    return all_items


# =========================
# 16) STARTUP CHECKS
# =========================

def startup_checks():
    print("===== AlphaBot Startup Checks =====", flush=True)
    print(f"VERSION: {VERSION}", flush=True)
    print(f"BOT_TOKEN: {'OK' if BOT_TOKEN else 'MISSING'}", flush=True)
    print(f"CHAT_IDS: {CHAT_IDS if CHAT_IDS else 'MISSING'}", flush=True)
    print(f"OPENROUTER_API_KEY: {'OK' if OPENROUTER_API_KEY else 'MISSING'}", flush=True)
    print(f"FINNHUB_API_KEY: {'OK' if FINNHUB_API_KEY else 'MISSING'}", flush=True)
    print(f"SEC_USER_AGENT: {SEC_USER_AGENT}", flush=True)
    print("===================================", flush=True)


# =========================
# 17) MAIN LOOP
# =========================

def run():
    startup_checks()
    startup_message()

    state = load_state()

    while True:
        try:
            print("Starting new cycle...", flush=True)

            news_items = collect_all_news()
            sent_count = 0

            for item in news_items:
                if sent_count >= MAX_ALERTS_PER_CYCLE:
                    break

                sent = process_news_item(item, state)

                if sent:
                    sent_count += 1
                    time.sleep(2)

            print(
                f"Cycle done. Sent: {sent_count}. Total items: {len(news_items)}",
                flush=True
            )

        except Exception as e:
            print(f"Main loop error: {e}", flush=True)

        time.sleep(CHECK_EVERY_SECONDS)


# =========================
# 18) START
# =========================

if __name__ == "__main__":
    run()