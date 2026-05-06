# AlphaBot Pro v5.2 Smart News
# RSS + Finnhub + SEC + OpenRouter + Telegram
# Low Price Stock Priority Mode

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

VERSION = "v5.2 Smart News"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "AlphaBot aktfaaksa@gmail.com")

# الآيدي القديم الموجود في كودك السابق
DEFAULT_EXTRA_CHAT_IDS = [6315087880]

CHECK_EVERY_SECONDS = 90
MAX_NEWS_AGE_MINUTES = 60

# وضع تفضيل الأسهم منخفضة السعر
LOW_PRICE_MODE = True
LOW_PRICE_MAX = 30.0
LOW_PRICE_MIN_SCORE = 6
BIG_STOCK_MIN_SCORE = 8
UNKNOWN_PRICE_MIN_SCORE = 7

MAX_ALERTS_PER_CYCLE = 3
MAX_DAILY_ALERTS = 80
TICKER_COOLDOWN_MINUTES = 45

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

PRICE_CACHE = {}


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

وضع السعر:
🔥 الأسهم تحت ${LOW_PRICE_MAX:.0f}: قوة {LOW_PRICE_MIN_SCORE}/10 أو أعلى
🚨 الأسهم فوق ${LOW_PRICE_MAX:.0f}: قوة {BIG_STOCK_MIN_SCORE}/10 أو أعلى
⚪ السعر غير معروف: قوة {UNKNOWN_PRICE_MIN_SCORE}/10 أو أعلى

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
        "AND", "FOR", "NEW", "NYSE", "NASDAQ", "CNBC"
    }

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            ticker = m.strip().upper()
            if ticker not in bad_words:
                return ticker

    return ""


def normalize_direction(direction):
    d = clean_text(direction).lower()

    if "positive" in d or "إيجابي" in d:
        return "إيجابي"
    if "negative" in d or "سلبي" in d:
        return "سلبي"
    if "mixed" in d or "مختلط" in d:
        return "مختلط"
    if "neutral" in d or "محايد" in d:
        return "محايد"

    return "غير واضح"


def normalize_category(category):
    c = clean_text(category)

    if not c:
        return "Other"

    c_l = c.lower()

    if "earning" in c_l:
        return "Earnings"
    if "guidance" in c_l:
        return "Guidance"
    if "offering" in c_l:
        return "Offering"
    if "fda" in c_l:
        return "FDA"
    if "contract" in c_l or "agreement" in c_l:
        return "Contract"
    if "analyst" in c_l or "upgrade" in c_l or "downgrade" in c_l:
        return "Analyst"
    if "m&a" in c_l or "merger" in c_l or "acquisition" in c_l:
        return "M&A"
    if "macro" in c_l:
        return "Macro"
    if "bankruptcy" in c_l:
        return "Bankruptcy"
    if "sec" in c_l or "10-q" in c_l or "10-k" in c_l or "8-k" in c_l:
        return "SEC"

    if "/" in c:
        return c.split("/")[0].strip()

    return c


# =========================
# 8) PRICE FROM FINNHUB
# =========================

def get_stock_price(ticker):
    ticker = clean_text(ticker).upper()

    if not ticker or not FINNHUB_API_KEY:
        return None

    if ticker in PRICE_CACHE:
        cached = PRICE_CACHE[ticker]
        cached_time = cached.get("time")
        if cached_time and now_utc() - cached_time < timedelta(minutes=10):
            return cached.get("price")

    try:
        url = "https://finnhub.io/api/v1/quote"
        params = {
            "symbol": ticker,
            "token": FINNHUB_API_KEY
        }

        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            print(f"Price error {ticker}: {r.status_code}", flush=True)
            return None

        data = r.json()
        price = data.get("c")

        if price is None:
            return None

        price = float(price)

        if price <= 0:
            return None

        PRICE_CACHE[ticker] = {
            "price": price,
            "time": now_utc()
        }

        return price

    except Exception as e:
        print(f"get_stock_price error {ticker}: {e}", flush=True)
        return None


def get_price_mode(price):
    if price is None:
        return "UNKNOWN"

    if price <= LOW_PRICE_MAX:
        return "LOW"

    return "BIG"


def get_required_score(price, category):
    category = normalize_category(category)

    urgent_categories = ["Offering", "FDA", "M&A", "Bankruptcy"]

    if category in urgent_categories:
        return LOW_PRICE_MIN_SCORE

    if price is None:
        return UNKNOWN_PRICE_MIN_SCORE

    if price <= LOW_PRICE_MAX:
        return LOW_PRICE_MIN_SCORE

    return BIG_STOCK_MIN_SCORE


# =========================
# 9) FETCH RSS
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

            print(f"RSS OK {src['name']}: {len(items) - count_before} items", flush=True)

        except Exception as e:
            print(f"RSS error {src['name']}: {e}", flush=True)

    return items


# =========================
# 10) FETCH FINNHUB
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
# 11) FETCH SEC CURRENT FILINGS
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
        },
        {
            "name": "SEC 10-K",
            "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&owner=include&count=40&output=atom"
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

            print(f"SEC OK {feed_info['name']}: {len(items) - count_before} items", flush=True)

        except Exception as e:
            print(f"SEC error {feed_info['name']}: {e}", flush=True)

    return items


# =========================
# 12) OPENROUTER AI ANALYSIS
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
- لا تعطِ توصية شراء أو بيع مباشرة.
- لا تستخدم عبارات مثل: اشترِ، بيع، ادخل، ينصح بالشراء.
- trading_note_ar يجب أن تكون مراقبة ومحايدة.
- اللغة العربية مختصرة وواضحة.

JSON format:
{{
  "send": true,
  "ticker": "RDW",
  "category": "Earnings",
  "impact_score": 8,
  "direction": "positive",
  "title_ar": "ترجمة العنوان للعربية",
  "summary_ar": "ملخص عربي قصير",
  "why_important_ar": "سبب أهمية الخبر",
  "trading_note_ar": "ملاحظة تداول فعلية ومحايدة مثل: راقب حجم التداول وردة فعل السعر"
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
# 13) SEND DECISION
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

    ticker = clean_text(analysis.get("ticker") or item.get("ticker", "")).upper()
    category = normalize_category(analysis.get("category", ""))

    if not ticker and category != "Macro":
        return False, "no ticker"

    price = None
    required_score = UNKNOWN_PRICE_MIN_SCORE
    price_mode = "UNKNOWN"

    if ticker and category != "Macro":
        price = get_stock_price(ticker)
        price_mode = get_price_mode(price)
        required_score = get_required_score(price, category)
    elif category == "Macro":
        required_score = BIG_STOCK_MIN_SCORE

    analysis["stock_price"] = price
    analysis["price_mode"] = price_mode
    analysis["required_score"] = required_score

    if score < required_score:
        return False, f"score {score} below required {required_score} | price {price}"

    if not ticker_cooldown_ok(state, ticker):
        urgent_categories = ["Offering", "FDA", "M&A", "Bankruptcy"]
        if category not in urgent_categories:
            return False, f"cooldown for {ticker}"

    if not daily_limit_ok(state):
        return False, "daily limit reached"

    return True, "ok"


# =========================
# 14) FORMAT ALERT
# =========================

def safe_trading_note(note):
    trading_note = clean_text(note)

    bad_trading_phrases = [
        "يمكن النظر في الشراء",
        "يمكن النظر في شراء",
        "ينصح بالشراء",
        "نوصي بالشراء",
        "شراء السهم",
        "اشتر",
        "ادخل",
        "الدخول",
        "buy",
        "consider buying",
        "ملاحظة تداول مختصرة",
        "بدون توصية شراء أو بيع",
        "محايدة بدون توصية",
        "يفضل مراقبة أداء السهم في الفترة القادمة"
    ]

    note_l = trading_note.lower()

    if not trading_note or any(p in note_l for p in bad_trading_phrases):
        return "راقب حركة السهم وحجم التداول، ولا تطارد بعد ارتفاع قوي إلا مع اختراق وثبات."

    return trading_note


def format_price_line(price, price_mode, required_score):
    if price is None:
        return f"💵 السعر: غير معروف | شرط الإرسال: {required_score}/10"

    if price_mode == "LOW":
        return f"💵 السعر: ${price:.2f} | 🔥 سهم منخفض السعر | شرط الإرسال: {required_score}/10"

    return f"💵 السعر: ${price:.2f} | 🚨 سهم كبير/مرتفع السعر | شرط الإرسال: {required_score}/10"


def format_alert(item, analysis):
    ticker = clean_text(analysis.get("ticker") or item.get("ticker", "")).upper()
    category = normalize_category(analysis.get("category", "Other"))
    direction = normalize_direction(analysis.get("direction", "mixed"))
    score = analysis.get("impact_score", "?")

    price = analysis.get("stock_price")
    price_mode = analysis.get("price_mode", "UNKNOWN")
    required_score = analysis.get("required_score", UNKNOWN_PRICE_MIN_SCORE)

    title = clean_text(item.get("title"))
    title_ar = clean_text(analysis.get("title_ar"))
    summary_ar = clean_text(analysis.get("summary_ar"))
    why = clean_text(analysis.get("why_important_ar"))
    trading_note = safe_trading_note(analysis.get("trading_note_ar"))

    url = item.get("url")
    source = item.get("source")
    age = human_age(item.get("published_at"))

    if not ticker:
        ticker = "السوق الأمريكي"

    price_line = format_price_line(price, price_mode, required_score)

    msg = f"""🚨 خبر مؤثر على سهم أمريكي

🏷️ السهم: {ticker}
📌 نوع الخبر: {category}
📊 التأثير المتوقع: {direction}
🔥 قوة الخبر: {score}/10
{price_line}
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
# 15) PROCESS NEWS
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

    # تقليل تكرار تقارير SEC العادية مثل 10-Q و10-K
    if source_name in ["SEC 10-Q", "SEC 10-K"]:
        title_l = title.lower()
        sec_urgent_words = [
            "bankruptcy", "chapter 11", "going concern",
            "offering", "s-3", "merger", "acquisition",
            "investigation", "material weakness",
            "restatement", "default", "delisting"
        ]

        if not any(w in title_l for w in sec_urgent_words):
            return False

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
# 16) COLLECT NEWS
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
# 17) STARTUP CHECKS
# =========================

def startup_checks():
    print("===== AlphaBot Startup Checks =====", flush=True)
    print(f"VERSION: {VERSION}", flush=True)
    print(f"BOT_TOKEN: {'OK' if BOT_TOKEN else 'MISSING'}", flush=True)
    print(f"CHAT_IDS: {CHAT_IDS if CHAT_IDS else 'MISSING'}", flush=True)
    print(f"OPENROUTER_API_KEY: {'OK' if OPENROUTER_API_KEY else 'MISSING'}", flush=True)
    print(f"FINNHUB_API_KEY: {'OK' if FINNHUB_API_KEY else 'MISSING'}", flush=True)
    print(f"SEC_USER_AGENT: {SEC_USER_AGENT}", flush=True)
    print(f"LOW_PRICE_MODE: {LOW_PRICE_MODE}", flush=True)
    print(f"LOW_PRICE_MAX: {LOW_PRICE_MAX}", flush=True)
    print("===================================", flush=True)


# =========================
# 18) MAIN LOOP
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
# 19) START
# =========================

if __name__ == "__main__":
    run()