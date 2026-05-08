# AlphaBot Pro v5.9.3 Cost Optimization
# RSS + Small-Cap Newswires + Finnhub + SEC Advanced Filings + OpenRouter + Telegram
# Gemini Primary + GPT-4o-mini Fallback + Interactive Watchlist + Translated Company News

import os
import re
import json
import time
import hashlib
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

# v5.9 Interactive Watchlist
try:
    from telegram_buttons import start_buttons_polling
except Exception as e:
    start_buttons_polling = None
    print(f"telegram_buttons import error: {e}", flush=True)


# =========================
# 1) SETTINGS
# =========================

VERSION = "v5.9.3 Cost Optimization"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# v5.9.3 Cost Optimization
# Gemini هو الأساسي لتقليل التكلفة، و GPT-4o-mini احتياطي فقط عند فشل Gemini أو فشل JSON
OPENROUTER_PRIMARY_MODEL = os.getenv("OPENROUTER_PRIMARY_MODEL", "google/gemini-2.5-flash-lite")
OPENROUTER_FALLBACK_MODEL = os.getenv("OPENROUTER_FALLBACK_MODEL", "openai/gpt-4o-mini")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "AlphaBot aktfaaksa@gmail.com")

DEFAULT_EXTRA_CHAT_IDS = [6315087880]

CHECK_EVERY_SECONDS = 90
MAX_NEWS_AGE_MINUTES = 60

LOW_PRICE_MODE = True
LOW_PRICE_MAX = 30.0
LOW_PRICE_MIN_SCORE = 6
BIG_STOCK_MIN_SCORE = 8
UNKNOWN_PRICE_MIN_SCORE = 7

MAX_ALERTS_PER_CYCLE = 3
MAX_DAILY_ALERTS = 80

# v5.9.3 Cost Control
# الحد الأقصى لعدد الأخبار التي يتم إرسالها إلى OpenRouter للتحليل في كل دورة
MAX_AI_ANALYSES_PER_CYCLE = 5

TICKER_COOLDOWN_MINUTES = 45
SEC_FORM_COOLDOWN_MINUTES = 60

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

SMALL_CAP_RSS_SOURCES = [
    {
        "name": "GlobeNewswire Press Releases",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/72-Press%20Releases/feedTitle/GlobeNewswire%20-%20Press%20Releases"
    },
    {
        "name": "GlobeNewswire Stock Market News",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/39-Stock%20Market%20News/feedTitle/GlobeNewswire%20-%20Stock%20Market%20News"
    },
    {
        "name": "GlobeNewswire Partnerships",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/56-Partnerships/feedTitle/GlobeNewswire%20-%20Partnerships"
    },
    {
        "name": "GlobeNewswire M&A",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/27-Mergers%20And%20Acquisitions/feedTitle/GlobeNewswire%20-%20Mergers%20And%20Acquisitions"
    },
    {
        "name": "PR Newswire All News",
        "url": "https://www.prnewswire.com/rss/news-releases-list.rss"
    },
    {
        "name": "BusinessWire News",
        "url": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeGVtRXQ=="
    }
]

SEC_FORMS = [
    "8-K", "S-1", "S-3", "F-1", "F-3", "424B5", "424B3", "424B4",
    "EFFECT", "FWP", "4", "SC 13D", "SC 13G", "DEF 14A", "PRE 14A",
    "NT 10-Q", "NT 10-K", "10-Q", "10-K"
]

SEC_IMPORTANT_FORMS = [
    "424B5", "424B3", "424B4", "S-1", "S-3", "F-1", "F-3",
    "EFFECT", "FWP", "4", "SC 13D", "SC 13G", "DEF 14A", "PRE 14A",
    "NT 10-Q", "NT 10-K"
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
    "offering", "public offering", "registered direct", "private placement",
    "bankruptcy", "chapter 11", "investigation", "sec investigation",
    "contract", "agreement", "partnership", "order",
    "downgrade", "upgrade", "price target",
    "8-k", "10-q", "10-k", "s-3", "s-1", "424b5", "424b3", "424b4",
    "form 4", "13d", "13g", "effect", "fwp"
]

SMALL_CAP_KEYWORDS = [
    "offering", "registered direct", "private placement", "at-the-market", "atm offering",
    "fda", "approval", "clearance", "rejection", "complete response letter",
    "clinical trial", "phase 1", "phase 2", "phase 3", "trial results", "topline results",
    "contract", "purchase order", "strategic partnership", "partnership", "agreement",
    "merger", "acquisition", "nasdaq compliance", "compliance", "delisting",
    "reverse split", "stock split", "warrant", "debt financing", "credit facility",
    "bankruptcy", "chapter 11", "going concern", "material weakness", "restatement"
]

SEC_URGENT_WORDS = [
    "common stock", "ordinary shares", "offering", "public offering", "registered direct",
    "private placement", "at-the-market", "atm", "warrant", "units",
    "prospectus supplement", "424b5", "424b3", "424b4", "effect",
    "free writing prospectus", "form 4", "insider", "beneficial ownership",
    "13d", "13g", "late filing", "nt 10-q", "nt 10-k", "delisting",
    "reverse split", "increase authorized shares", "nasdaq compliance", "material weakness",
    "going concern", "bankruptcy", "chapter 11", "restatement", "default"
]

US_MARKET_KEYWORDS = [
    "fed", "federal reserve", "cpi", "inflation", "jobs report",
    "payrolls", "interest rates", "treasury yields", "pce"
]

PRICE_CACHE = {}
SEC_TICKER_MAP = None


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
المصادر: RSS + Small-Cap Newswires + Finnhub + SEC Advanced + OpenRouter
وضع الإرسال: الأخبار والإفصاحات المؤثرة فقط

وضع السعر:
🔥 الأسهم تحت ${LOW_PRICE_MAX:.0f}: قوة {LOW_PRICE_MIN_SCORE}/10 أو أعلى
🚨 الأسهم فوق ${LOW_PRICE_MAX:.0f}: قوة {BIG_STOCK_MIN_SCORE}/10 أو أعلى
⚪ السعر غير معروف: قوة {UNKNOWN_PRICE_MIN_SCORE}/10 أو أعلى

مصادر الأسهم الصغيرة:
GlobeNewswire + PR Newswire + BusinessWire

دقة رمز السهم:
✅ استخراج الرمز الرسمي من نص الخبر مثل NYSE American: ARMP
✅ منع التقاط رموز المنتجات مثل AP-SA02 كرمز سهم
✅ التحقق بالسعر من Finnhub عند الإمكان
✅ أخبار SEC تعتمد على CIK والسهم العادي قدر الإمكان

تنظيف SEC:
✅ قراءة النموذج الحقيقي من العنوان
✅ تحويل CIK إلى رمز السهم العادي عند الإمكان
✅ تجنب رموز Warrants / Preferred قدر الإمكان
✅ منع تكرار نفس CIK + نفس نموذج SEC
✅ Form 4 لا يرسل إلا مع شراء داخلي واضح

منع التكرار:
نفس الشركة CIK + نفس نموذج SEC لا يتكرر خلال {SEC_FORM_COOLDOWN_MINUTES} دقيقة

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
        "sec_form_last_alert": {},
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
        state.setdefault("sec_form_last_alert", {})
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
    url = clean_text(item.get("url", ""))

    if url:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    raw = f"{item.get('ticker','')}|{item.get('title','')}"
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
# 7) BASIC FILTERS + TICKERS
# =========================

def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#039;", "'", text)
    return clean_text(text)


def is_blocked(title):
    title_l = title.lower()
    return any(word in title_l for word in BLOCK_WORDS)


def has_important_keyword(title):
    title_l = title.lower()
    return any(word in title_l for word in IMPORTANT_KEYWORDS)


def has_small_cap_keyword(title):
    title_l = title.lower()
    return any(word in title_l for word in SMALL_CAP_KEYWORDS)


def has_sec_urgent_keyword(text):
    text_l = text.lower()
    return any(word in text_l for word in SEC_URGENT_WORDS)


def has_us_market_keyword(title):
    title_l = title.lower()
    return any(word in title_l for word in US_MARKET_KEYWORDS)


def is_small_cap_source(source_name):
    s = source_name.lower()
    return (
        "globenewswire" in s
        or "pr newswire" in s
        or "businesswire" in s
        or "business wire" in s
    )


def is_sec_source(source_name):
    return source_name.upper().startswith("SEC ")


def canonical_sec_form(form):
    form = clean_text(form).upper()
    form = form.replace("/A", "")
    form = form.replace("FORM ", "")

    if form in ["4", "FORM 4"]:
        return "4"

    return form


def extract_sec_form_from_title(title):
    title = clean_text(title)

    if not title:
        return ""

    match = re.match(r"^\s*([A-Z0-9/ -]+?)\s*[-–]\s*", title, flags=re.IGNORECASE)

    if not match:
        return ""

    form = canonical_sec_form(match.group(1))
    known = [canonical_sec_form(x) for x in SEC_FORMS]

    if form in known:
        return form

    return ""


def get_sec_form_from_item(item):
    if not item:
        return ""

    if item.get("sec_form"):
        return canonical_sec_form(item.get("sec_form"))

    title_form = extract_sec_form_from_title(item.get("title", ""))
    if title_form:
        return title_form

    source = item.get("source", "")
    if is_sec_source(source):
        return canonical_sec_form(source.replace("SEC ", ""))

    return ""


def get_sec_form_from_source(source_name):
    if not is_sec_source(source_name):
        return ""
    return canonical_sec_form(source_name.replace("SEC ", ""))


def is_important_sec_form_from_item(item):
    form = get_sec_form_from_item(item)
    return form in [canonical_sec_form(x) for x in SEC_IMPORTANT_FORMS]


def extract_cik(text):
    if not text:
        return ""

    patterns = [
        r"\((\d{10})\)",
        r"/data/(\d+)/",
        r"CIK[=: ]+(\d{1,10})"
    ]

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            try:
                return str(int(m.group(1)))
            except Exception:
                return m.group(1).lstrip("0")

    return ""


def get_cik_from_item(item):
    if not item:
        return ""

    if item.get("cik"):
        return str(item.get("cik"))

    return extract_cik(f"{item.get('title','')} {item.get('url','')} {item.get('raw','')}")


def is_warrant_or_right_ticker(ticker):
    t = clean_text(ticker).upper()

    if not t:
        return False

    if "-" in t or "." in t or "^" in t:
        return True

    suffixes = ["WS", "WT", "WTA", "W", "Z", "R", "U"]

    for s in suffixes:
        if len(t) > 2 and t.endswith(s):
            return True

    return False


def ticker_quality_score(ticker):
    t = clean_text(ticker).upper()

    if not t:
        return -100

    score = 100

    if "-" in t or "." in t or "^" in t:
        score -= 60

    if is_warrant_or_right_ticker(t):
        score -= 40

    if len(t) <= 4:
        score += 10

    if len(t) > 5:
        score -= 20

    return score


def normalize_common_ticker(ticker, available_tickers=None):
    t = clean_text(ticker).upper()

    if available_tickers:
        candidates = [clean_text(x).upper() for x in available_tickers if clean_text(x)]
        normal_candidates = [x for x in candidates if not is_warrant_or_right_ticker(x)]

        if normal_candidates:
            normal_candidates.sort(key=ticker_quality_score, reverse=True)
            return normal_candidates[0]

        candidates.sort(key=ticker_quality_score, reverse=True)
        return candidates[0] if candidates else ""

    if not t:
        return ""

    if "-" in t:
        return t.split("-")[0]

    if "." in t:
        return t.split(".")[0]

    if len(t) > 2 and t.endswith("WS"):
        return t[:-2]

    if len(t) > 2 and t.endswith("WT"):
        return t[:-2]

    if len(t) > 1 and t.endswith("W"):
        return t[:-1]

    if len(t) > 1 and t.endswith("Z"):
        return t[:-1]

    return t


def load_sec_ticker_map():
    global SEC_TICKER_MAP

    if SEC_TICKER_MAP is not None:
        return SEC_TICKER_MAP

    SEC_TICKER_MAP = {}
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate"
    }

    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=headers,
            timeout=15
        )

        if r.status_code != 200:
            print(f"SEC ticker map status error: {r.status_code}", flush=True)
            return SEC_TICKER_MAP

        data = r.json()

        for _, row in data.items():
            cik = str(int(row.get("cik_str")))
            ticker = clean_text(row.get("ticker")).upper()

            if cik and ticker:
                SEC_TICKER_MAP.setdefault(cik, [])
                if ticker not in SEC_TICKER_MAP[cik]:
                    SEC_TICKER_MAP[cik].append(ticker)

        print(f"SEC ticker map loaded: {len(SEC_TICKER_MAP)} CIKs", flush=True)

    except Exception as e:
        print(f"SEC ticker map error: {e}", flush=True)

    return SEC_TICKER_MAP


def get_ticker_from_cik(cik):
    if not cik:
        return ""

    mapping = load_sec_ticker_map()
    tickers = mapping.get(str(int(cik)), [])

    if not tickers:
        return ""

    return normalize_common_ticker("", tickers)


def remove_product_codes(text):
    """
    يمنع التقاط رموز منتجات مثل AP-SA02 على أنها ticker.
    """
    if not text:
        return ""

    text = re.sub(r"\b[A-Z]{1,6}-[A-Z0-9]{2,}\b", " ", text)
    text = re.sub(r"\b[A-Z]{1,6}-\d+[A-Z0-9-]*\b", " ", text)
    return text


def extract_official_ticker(text):
    """
    أدق طريقة للأخبار الصحفية: يلتقط الرمز الرسمي من نص مثل:
    (NYSE American: ARMP), Nasdaq: NVDA, NYSE: DIS, OTCQB: ABCD
    """
    if not text:
        return ""

    patterns = [
        r"\bNYSE\s+American\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bNYSE\s+AMERICAN\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bNYSE\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bNASDAQ\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bNasdaq\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bAMEX\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bOTCQB\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bOTCQX\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bOTC\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\((?:NYSE\s+American|NYSE|NASDAQ|Nasdaq|AMEX|OTCQB|OTCQX|OTC)\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\)",
        r"\bTicker\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        r"\bSymbol\s*[:：]\s*([A-Z][A-Z0-9.\-]{0,9})\b"
    ]

    bad = {"USA", "SEC", "FDA", "IPO", "ETF"}

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            ticker = normalize_common_ticker(m)
            if ticker and ticker not in bad:
                return ticker

    return ""


def extract_possible_ticker(text):
    if not text:
        return ""

    official = extract_official_ticker(text)
    if official:
        return official

    text = remove_product_codes(text)

    patterns = [
        r"\bNASDAQ:\s*([A-Z]{1,5})\b",
        r"\bNYSE:\s*([A-Z]{1,5})\b",
        r"\bAMEX:\s*([A-Z]{1,5})\b",
        r"\(([A-Z]{1,5})\)",
        r"\bTicker:\s*([A-Z]{1,5})\b",
        r"\bSymbol:\s*([A-Z]{1,5})\b",
        r"\b([A-Z]{2,5})\b"
    ]

    bad_words = {
        "CEO", "CFO", "USA", "SEC", "FDA", "EPS", "ETF", "IPO",
        "AI", "US", "DJIA", "GDP", "CPI", "PCE", "FOMC", "THE",
        "AND", "FOR", "NEW", "NYSE", "NASDAQ", "CNBC", "PR", "RSS",
        "FORM", "SC", "DEF", "PRE", "NT", "INC", "CORP", "LTD", "LLC",
        "GLOBAL", "HOLDINGS", "PHARMACEUTICAL", "SERVICES", "TRUST"
    }

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            ticker = normalize_common_ticker(m)
            if ticker not in bad_words:
                return ticker

    return ""


def extract_ticker_for_sec(title, url=""):
    cik = extract_cik(f"{title} {url}")

    if cik:
        ticker = get_ticker_from_cik(cik)
        if ticker:
            return ticker

    return extract_possible_ticker(title)


def likely_product_code_conflict(ticker, text):
    """
    مثال: AP-SA02 لا يعني أن AP هو رمز سهم.
    إذا الرمز جاء كجزء من كود منتج ولم يوجد رمز رسمي، نرفضه.
    """
    ticker = clean_text(ticker).upper()
    if not ticker or not text:
        return False

    text_upper = text.upper()
    pattern = rf"\b{re.escape(ticker)}-[A-Z0-9]{{2,}}\b"
    return re.search(pattern, text_upper) is not None


def make_sec_form_cooldown_key(item, ticker, form):
    cik = get_cik_from_item(item)
    form = canonical_sec_form(form)
    ticker = normalize_common_ticker(ticker)

    if cik and form:
        return f"CIK:{cik}|{form}"

    if ticker and form:
        return f"TICKER:{ticker}|{form}"

    return ""


def sec_form_cooldown_ok(state, item, ticker, form):
    key = make_sec_form_cooldown_key(item, ticker, form)

    if not key:
        return True

    last = state.get("sec_form_last_alert", {}).get(key)

    if not last:
        return True

    try:
        last_dt = datetime.fromisoformat(last)

        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        return now_utc() - last_dt >= timedelta(minutes=SEC_FORM_COOLDOWN_MINUTES)

    except Exception:
        return True


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

    if "offering" in c_l or "private placement" in c_l or "424b" in c_l:
        return "Offering / Prospectus"
    if "effect" in c_l:
        return "Registration Effective"
    if "form 4" in c_l or "insider" in c_l:
        return "Insider / Form 4"
    if "13d" in c_l or "13g" in c_l or "ownership" in c_l:
        return "Ownership"
    if "nt 10-q" in c_l or "nt 10-k" in c_l or "late filing" in c_l:
        return "Late Filing"
    if "proxy" in c_l or "14a" in c_l or "reverse split" in c_l:
        return "Proxy / Vote"
    if "earning" in c_l:
        return "Earnings"
    if "guidance" in c_l:
        return "Guidance"
    if "fda" in c_l or "clinical" in c_l or "phase" in c_l:
        return "FDA / Clinical"
    if "contract" in c_l or "agreement" in c_l or "partnership" in c_l:
        return "Contract / Partnership"
    if "analyst" in c_l or "upgrade" in c_l or "downgrade" in c_l:
        return "Analyst"
    if "m&a" in c_l or "merger" in c_l or "acquisition" in c_l:
        return "M&A"
    if "macro" in c_l:
        return "Macro"
    if "bankruptcy" in c_l:
        return "Bankruptcy"
    if "compliance" in c_l or "delisting" in c_l:
        return "Nasdaq Compliance"
    if "sec" in c_l or "10-q" in c_l or "10-k" in c_l or "8-k" in c_l:
        return "SEC"

    if "/" in c:
        return c.split("/")[0].strip()

    return c


# =========================
# 8) PRICE FROM FINNHUB
# =========================

def get_stock_price(ticker):
    ticker = normalize_common_ticker(ticker)

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


def get_required_score(price, category, item):
    category = normalize_category(category)
    form = get_sec_form_from_item(item)

    urgent_categories = [
        "Offering / Prospectus",
        "Registration Effective",
        "FDA / Clinical",
        "M&A",
        "Bankruptcy",
        "Nasdaq Compliance",
        "Late Filing",
        "Proxy / Vote"
    ]

    if category in ["Insider / Form 4", "Ownership"]:
        return LOW_PRICE_MIN_SCORE if price is not None and price <= LOW_PRICE_MAX else UNKNOWN_PRICE_MIN_SCORE

    if form in [canonical_sec_form(x) for x in SEC_IMPORTANT_FORMS]:
        if price is not None and price <= LOW_PRICE_MAX:
            return LOW_PRICE_MIN_SCORE
        if price is None:
            return UNKNOWN_PRICE_MIN_SCORE
        return BIG_STOCK_MIN_SCORE

    if category in urgent_categories:
        return LOW_PRICE_MIN_SCORE

    if price is None:
        return UNKNOWN_PRICE_MIN_SCORE

    if price <= LOW_PRICE_MAX:
        return LOW_PRICE_MIN_SCORE

    return BIG_STOCK_MIN_SCORE


# =========================
# 9) RSS
# =========================

def fetch_rss_group(sources, group_name, limit_per_source=30):
    items = []

    print(f"Fetching {group_name}...", flush=True)

    for src in sources:
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
                print(f"{group_name} status error {src['name']}: {r.status_code}", flush=True)
                continue

            feed = feedparser.parse(r.text)
            count_before = len(items)

            for entry in feed.entries[:limit_per_source]:
                title = clean_text(entry.get("title"))
                url = clean_text(entry.get("link"))
                published_at = parse_rss_time(entry)
                summary = clean_text(entry.get("summary") or entry.get("description") or "")

                if not title or not url:
                    continue

                combined = f"{title} {summary}"
                official = extract_official_ticker(combined)

                items.append({
                    "source": src["name"],
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "ticker": official or extract_possible_ticker(combined),
                    "official_ticker": official,
                    "raw": summary,
                    "sec_form": "",
                    "cik": ""
                })

            print(f"{group_name} OK {src['name']}: {len(items) - count_before} items", flush=True)

        except Exception as e:
            print(f"{group_name} error {src['name']}: {e}", flush=True)

    return items


def fetch_rss_news():
    return fetch_rss_group(RSS_SOURCES, "RSS", limit_per_source=30)


def fetch_small_cap_news():
    return fetch_rss_group(SMALL_CAP_RSS_SOURCES, "SmallCap RSS", limit_per_source=25)


# =========================
# 10) FINNHUB
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
            official = extract_official_ticker(full_text)

            items.append({
                "source": f"Finnhub / {source}",
                "title": title,
                "url": news_url,
                "published_at": published_at,
                "ticker": official or extract_possible_ticker(full_text),
                "official_ticker": official,
                "raw": summary,
                "sec_form": "",
                "cik": ""
            })

        print(f"Finnhub OK: {len(items)} items", flush=True)

    except Exception as e:
        print(f"Finnhub error: {e}", flush=True)

    return items


# =========================
# 11) SEC
# =========================

def fetch_sec_news():
    items = []

    print("Fetching SEC advanced filings...", flush=True)

    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/atom+xml, application/xml, text/xml, */*"
    }

    for form_type in SEC_FORMS:
        try:
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "action": "getcurrent",
                "type": form_type,
                "owner": "include",
                "count": "40",
                "output": "atom"
            }

            r = requests.get(url, params=params, headers=headers, timeout=15)

            if r.status_code != 200:
                print(f"SEC status error {form_type}: {r.status_code}", flush=True)
                continue

            feed = feedparser.parse(r.text)
            count_before = len(items)

            for entry in feed.entries[:25]:
                title = clean_text(entry.get("title"))
                filing_url = clean_text(entry.get("link"))
                published_at = parse_rss_time(entry)

                if not title or not filing_url:
                    continue

                actual_form = extract_sec_form_from_title(title) or canonical_sec_form(form_type)
                cik = extract_cik(f"{title} {filing_url}")
                source_name = f"SEC {actual_form}"
                ticker_guess = extract_ticker_for_sec(title, filing_url)

                items.append({
                    "source": source_name,
                    "title": title,
                    "url": filing_url,
                    "published_at": published_at,
                    "ticker": ticker_guess,
                    "official_ticker": ticker_guess,
                    "raw": f"SEC filing form {actual_form}",
                    "sec_form": actual_form,
                    "cik": cik
                })

            print(f"SEC OK {form_type}: {len(items) - count_before} items", flush=True)

        except Exception as e:
            print(f"SEC error {form_type}: {e}", flush=True)

    return items


def find_sec_doc_links(index_html, base_url):
    links = []
    hrefs = re.findall(r'href="([^"]+)"', index_html, flags=re.IGNORECASE)

    for href in hrefs:
        full = urljoin(base_url, href)
        lower = full.lower()

        if "/archives/edgar/data/" not in lower:
            continue

        if "ixviewer" in lower or "xsl" in lower:
            continue

        if lower.endswith("-index.htm") or lower.endswith("-index.html"):
            continue

        if "filingsummary.xml" in lower:
            continue

        if lower.endswith(".xml") or lower.endswith(".htm") or lower.endswith(".html"):
            if full not in links:
                links.append(full)

    return links[:3]


def form4_has_open_market_purchase(raw):
    if not raw:
        return False

    raw_l = raw.lower()

    purchase_patterns = [
        "<transactioncode>p</transactioncode>",
        "<transactioncode>p",
        "transaction code p",
        ">p</transactioncode>",
        "open market purchase"
    ]

    return any(p in raw_l for p in purchase_patterns)


def enrich_sec_item(item):
    if not is_sec_source(item.get("source", "")):
        return item

    if not is_important_sec_form_from_item(item):
        return item

    url = item.get("url", "")
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code != 200:
            return item

        index_html = r.text
        index_text = strip_html(index_html)
        doc_texts = []
        links = find_sec_doc_links(index_html, url)

        for link in links:
            try:
                dr = requests.get(link, headers=headers, timeout=10)

                if dr.status_code != 200:
                    continue

                if link.lower().endswith(".xml"):
                    doc_texts.append(dr.text[:3500])
                else:
                    doc_texts.append(strip_html(dr.text)[:3500])

            except Exception:
                continue

        combined = "SEC index text:\n" + index_text[:2000]

        if doc_texts:
            combined += "\n\nSEC document text:\n" + "\n\n".join(doc_texts)

        item["raw"] = combined[:7000]

    except Exception as e:
        print(f"SEC enrich error: {e}", flush=True)

    return item


def enrich_non_sec_item(item):
    """
    للأخبار الصحفية: نحاول قراءة الصفحة نفسها لاستخراج الرمز الرسمي مثل (NYSE American: ARMP).
    هذا يمنع أخطاء مثل AP-SA02 -> AP.
    """
    if is_sec_source(item.get("source", "")):
        return item

    url = item.get("url", "")

    if not url:
        return item

    # إذا عندنا رمز رسمي بالفعل لا نحتاج تحميل الصفحة إلا إذا raw قصير جداً.
    if item.get("official_ticker") and len(item.get("raw", "")) > 300:
        return item

    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": "AlphaBot News Bot",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
            timeout=12
        )

        if r.status_code != 200:
            return item

        text = strip_html(r.text)
        official = extract_official_ticker(text)

        if official:
            item["official_ticker"] = official
            item["ticker"] = official

        if text:
            existing = clean_text(item.get("raw", ""))
            item["raw"] = (existing + "\n\nArticle text:\n" + text[:4000]).strip()[:6000]

    except Exception as e:
        print(f"Non-SEC enrich error: {e}", flush=True)

    return item


# =========================
# 12) OPENROUTER AI
# =========================

def _extract_json_from_ai_content(content):
    content = clean_text(content)
    content = content.replace("```json", "").replace("```", "").strip()

    # إذا رجع النموذج كلامًا حول JSON نحاول استخراج أول كائن JSON
    start = content.find("{")
    end = content.rfind("}")

    if start != -1 and end != -1 and end > start:
        content = content[start:end + 1]

    return json.loads(content)


def _call_openrouter_model(model_name, prompt):
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model_name,
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
        raise RuntimeError(f"OpenRouter status error for {model_name}: {r.status_code} | {r.text[:300]}")

    data = r.json()
    content = data["choices"][0]["message"]["content"].strip()
    return _extract_json_from_ai_content(content)


def analyze_with_ai(item):
    if not OPENROUTER_API_KEY:
        print("OpenRouter skipped: missing API key", flush=True)
        return None

    title = item.get("title", "")
    source = item.get("source", "")
    raw = item.get("raw", "")
    ticker = item.get("ticker", "")
    official_ticker = item.get("official_ticker", "")
    sec_form = get_sec_form_from_item(item)
    cik = get_cik_from_item(item)

    prompt = f"""
أنت محلل أخبار وإفصاحات SEC للأسهم الأمريكية فقط.

حلل الخبر أو الإفصاح التالي وارجع JSON فقط بدون شرح إضافي.

المطلوب:
- إذا الخبر لا يخص سهم أمريكي أو حدث قوي يؤثر على السوق الأمريكي، اجعل send=false.
- لا تختر رمز سهم من اسم منتج أو علاج. مثال: AP-SA02 ليس رمز سهم، ولا يعني AP.
- إذا وجدت رمزًا رسميًا داخل النص مثل NYSE American: ARMP أو NASDAQ: RDW، استخدمه فقط.
- إذا Official ticker موجود، استخدمه كما هو.
- ركز على الأخبار التي قد تحرك السهم فعلياً.
- ركز أكثر على الأسهم منخفضة السعر والشركات الصغيرة إذا الخبر عن: offering, FDA, contract, clinical trial, Nasdaq compliance, delisting, reverse split.
- حلل إفصاحات SEC بذكاء:
  424B5 / 424B3 / 424B4:
    common stock أو warrants أو units أو ATM أو registered direct = سلبي غالباً بسبب تخفيف محتمل.
    debt securities أو preferred stock = محايد إلى سلبي محدود حسب السياق.
  S-1 / S-3 / F-1 / F-3:
    تسجيل أوراق مالية = مراقبة / احتمال تمويل.
  EFFECT:
    التسجيل أصبح فعالاً = مهم، وقد يسمح بطرح أو بيع أوراق مالية.
  Form 4:
    لا تعتبره إيجابيًا إلا إذا كان هناك شراء داخلي واضح Open Market Purchase أو transaction code P.
    البيع أو المنح أو الخيارات أو التعويضات = محايد غالباً أو تجاهل.
  SC 13D:
    دخول مالك كبير أو ناشط = مهم / إيجابي أو مراقبة.
  SC 13G:
    ملكية كبيرة سلبية أو مؤسسية = مراقبة.
  NT 10-Q / NT 10-K:
    تأخير تقرير مالي = سلبي / تحذيري.
  DEF 14A / PRE 14A:
    انتبه لـ reverse split أو زيادة الأسهم المصرح بها.
- لا ترسل أخبار كريبتو أو فيديو أو مقالات رأي ضعيفة.
- لا تبالغ في التأثير.
- impact_score من 1 إلى 10.
- لا تعطِ توصية شراء أو بيع مباشرة.
- لا تستخدم عبارات مثل: اشترِ، بيع، ادخل، ينصح بالشراء.
- trading_note_ar يجب أن تكون مراقبة ومحايدة.
- اللغة العربية مختصرة وواضحة.

JSON format:
{{
  "send": true,
  "ticker": "RDW",
  "category": "Offering / Prospectus",
  "impact_score": 7,
  "direction": "negative",
  "title_ar": "ترجمة العنوان للعربية",
  "summary_ar": "ملخص عربي قصير",
  "why_important_ar": "سبب أهمية الخبر أو الإفصاح",
  "trading_note_ar": "ملاحظة تداول فعلية ومحايدة مثل: راقب حجم التداول وردة فعل السعر"
}}

الخبر:
Source: {source}
SEC Form: {sec_form}
CIK: {cik}
Ticker guess: {ticker}
Official ticker: {official_ticker}
Title: {title}
Extra: {raw}
"""

    models_to_try = [OPENROUTER_PRIMARY_MODEL]

    if OPENROUTER_FALLBACK_MODEL and OPENROUTER_FALLBACK_MODEL not in models_to_try:
        models_to_try.append(OPENROUTER_FALLBACK_MODEL)

    for model_name in models_to_try:
        try:
            parsed = _call_openrouter_model(model_name, prompt)
            print(f"OpenRouter analysis OK using {model_name}", flush=True)
            return parsed

        except Exception as e:
            print(f"OpenRouter analysis failed using {model_name}: {e}", flush=True)

            # إذا فشل Gemini نجرب GPT-4o-mini، أما إذا فشل الاحتياطي نرجع None
            continue

    return None


# =========================
# 13) SEND DECISION
# =========================

def ticker_cooldown_ok(state, ticker):
    if not ticker:
        return True

    ticker = normalize_common_ticker(ticker)
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


def resolve_final_ticker(item, analysis):
    # 1) SEC: استخدم CIK إلى السهم العادي
    if is_sec_source(item.get("source", "")):
        ticker = normalize_common_ticker(item.get("ticker") or analysis.get("ticker", ""))
        return ticker

    # 2) الأخبار الصحفية: الرمز الرسمي داخل النص هو الأعلى أولوية
    official = normalize_common_ticker(item.get("official_ticker", ""))
    if official:
        return official

    ai_ticker = normalize_common_ticker(analysis.get("ticker", ""))
    item_ticker = normalize_common_ticker(item.get("ticker", ""))

    # إذا الرمز متورط في كود منتج مثل AP-SA02 ولم يوجد official، لا نثق به
    combined = f"{item.get('title','')} {item.get('raw','')}"
    if ai_ticker and likely_product_code_conflict(ai_ticker, combined):
        return ""

    if item_ticker and likely_product_code_conflict(item_ticker, combined):
        item_ticker = ""

    return ai_ticker or item_ticker


def should_send_alert(item, analysis, state):
    if not analysis:
        return False, "AI analysis failed"

    if not analysis.get("send"):
        return False, "AI decided not important"

    try:
        score = int(analysis.get("impact_score", 0))
    except Exception:
        score = 0

    ticker = resolve_final_ticker(item, analysis)
    category = normalize_category(analysis.get("category", ""))
    sec_form = get_sec_form_from_item(item)

    if not ticker and category != "Macro":
        return False, "no reliable ticker"

    if is_sec_source(item.get("source", "")) and sec_form:
        if not sec_form_cooldown_ok(state, item, ticker, sec_form):
            return False, f"SEC CIK/form cooldown for {ticker} {sec_form}"

    if sec_form == "4":
        raw = item.get("raw", "")

        if not form4_has_open_market_purchase(raw):
            return False, "Form 4 without clear open-market purchase"

    price = None
    required_score = UNKNOWN_PRICE_MIN_SCORE
    price_mode = "UNKNOWN"

    if ticker and category != "Macro":
        price = get_stock_price(ticker)
        price_mode = get_price_mode(price)
        required_score = get_required_score(price, category, item)
    elif category == "Macro":
        required_score = BIG_STOCK_MIN_SCORE

    analysis["ticker"] = ticker
    analysis["stock_price"] = price
    analysis["price_mode"] = price_mode
    analysis["required_score"] = required_score

    # حماية إضافية: إذا خبر صحفي وليس SEC ولا يوجد official ticker ولا سعر، لا نرسله بثقة
    if not is_sec_source(item.get("source", "")):
        if not item.get("official_ticker") and price is None and category != "Macro":
            return False, "non-SEC ticker not verified by official text or Finnhub price"

    if score < required_score:
        return False, f"score {score} below required {required_score} | price {price}"

    if not ticker_cooldown_ok(state, ticker):
        urgent_categories = [
            "Offering / Prospectus",
            "Registration Effective",
            "FDA / Clinical",
            "M&A",
            "Bankruptcy",
            "Nasdaq Compliance",
            "Late Filing",
            "Proxy / Vote"
        ]

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

    if price < 0.01:
        price_text = f"${price:.6f}"
    else:
        price_text = f"${price:.2f}"

    if price_mode == "LOW":
        return f"💵 السعر: {price_text} | 🔥 سهم منخفض السعر | شرط الإرسال: {required_score}/10"

    return f"💵 السعر: {price_text} | 🚨 سهم كبير/مرتفع السعر | شرط الإرسال: {required_score}/10"


def format_alert(item, analysis):
    ticker = normalize_common_ticker(analysis.get("ticker") or item.get("ticker", ""))
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
    form = get_sec_form_from_item(item)
    cik = get_cik_from_item(item)

    if not ticker:
        ticker = "السوق الأمريكي"

    price_line = format_price_line(price, price_mode, required_score)

    label = "🚨 خبر مؤثر على سهم أمريكي"

    if price_mode == "LOW":
        label = "🔥 خبر سهم منخفض السعر"

    if is_sec_source(source):
        if direction == "سلبي":
            label = "🔴 إفصاح SEC مهم"
        elif direction == "إيجابي":
            label = "🟢 إفصاح SEC مهم"
        else:
            label = "🟡 إفصاح SEC مهم"

    sec_line = ""
    if form:
        sec_line += f"📄 نموذج SEC: {form}\n"
    if cik:
        sec_line += f"🆔 CIK: {cik}\n"

    official_line = ""
    if item.get("official_ticker") and not is_sec_source(source):
        official_line = "✅ الرمز مؤكد من نص الخبر\n"

    msg = f"""{label}

🏷️ السهم: {ticker}
{sec_line}{official_line}📌 نوع الخبر: {category}
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

def process_news_item(item, state, ai_counter=None):
    title = clean_text(item.get("title"))
    url = clean_text(item.get("url"))

    if not title or not url:
        return False

    if is_blocked(title):
        return False

    if not is_fresh_news(item.get("published_at")):
        return False

    source_name = item.get("source", "")
    source_form = get_sec_form_from_item(item)

    if source_name in ["SEC 10-Q", "SEC 10-K"]:
        title_l = title.lower()
        if not any(w in title_l for w in SEC_URGENT_WORDS):
            return False

    if is_sec_source(source_name) and source_form in [canonical_sec_form(x) for x in SEC_IMPORTANT_FORMS]:
        pass
    elif is_small_cap_source(source_name):
        if not has_small_cap_keyword(title) and not has_important_keyword(title):
            return False
    else:
        if (
            not has_important_keyword(title)
            and not has_us_market_keyword(title)
            and "SEC" not in source_name
        ):
            return False

    news_id = make_news_id(item)

    if news_id in state.get("seen", []):
        return False

    if is_sec_source(source_name):
        item = enrich_sec_item(item)
    else:
        item = enrich_non_sec_item(item)

    # v5.9.3 Cost Control
    # لا نرسل أكثر من عدد محدد من الأخبار إلى OpenRouter في كل دورة
    if ai_counter is not None:
        current_count = int(ai_counter.get("count", 0))

        if current_count >= MAX_AI_ANALYSES_PER_CYCLE:
            print(
                f"AI analysis limit reached this cycle: {current_count}/{MAX_AI_ANALYSES_PER_CYCLE} | {title}",
                flush=True
            )
            return False

        ai_counter["count"] = current_count + 1

    analysis = analyze_with_ai(item)

    ok, reason = should_send_alert(item, analysis, state)

    if not ok:
        print(f"Skip: {reason} | {title}", flush=True)
        state["seen"].append(news_id)
        save_state(state)
        return False

    alert = format_alert(item, analysis)
    send_telegram(alert)

    ticker = normalize_common_ticker(analysis.get("ticker") or item.get("ticker", ""))
    sec_form = get_sec_form_from_item(item)

    if ticker:
        state.setdefault("ticker_last_alert", {})[ticker] = now_utc().isoformat()

    if sec_form:
        key = make_sec_form_cooldown_key(item, ticker, sec_form)
        if key:
            state.setdefault("sec_form_last_alert", {})[key] = now_utc().isoformat()

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
        small_items = fetch_small_cap_news()
        all_items.extend(small_items)
        print(f"Collected SmallCap RSS: {len(small_items)}", flush=True)
    except Exception as e:
        print(f"collect SmallCap RSS error: {e}", flush=True)

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
    print(f"SEC_FORM_COOLDOWN_MINUTES: {SEC_FORM_COOLDOWN_MINUTES}", flush=True)
    print("SMALL_CAP_SOURCES: ON", flush=True)
    print("SEC_ADVANCED_FORMS: ON", flush=True)
    print("SEC_CIK_TO_COMMON_TICKER: ON", flush=True)
    print("SEC_CIK_FORM_COOLDOWN: ON", flush=True)
    print("FORM_4_PURCHASE_FILTER: ON", flush=True)
    print("OFFICIAL_NEWS_TICKER_EXTRACTION: ON", flush=True)
    print("PRODUCT_CODE_TICKER_BLOCK: ON", flush=True)
    print("===================================", flush=True)


# =========================
# 18) MAIN LOOP
# =========================

def run():
    startup_checks()
    startup_message()

    # =========================
    # v5.9 Interactive Watchlist
    # تشغيل الأزرار في مسار مستقل حتى لا تتأثر دورة الأخبار
    # =========================
    try:
        if start_buttons_polling:
            start_buttons_polling(
                bot_token=BOT_TOKEN,
                chat_ids=CHAT_IDS,
                get_stock_price_func=get_stock_price,
                collect_all_news_func=collect_all_news,
                analyze_with_ai_func=analyze_with_ai,
                normalize_common_ticker_func=normalize_common_ticker,
                send_telegram_func=send_telegram
            )
            print("Interactive Watchlist polling started", flush=True)
        else:
            print("Interactive Watchlist disabled: telegram_buttons not available", flush=True)
    except Exception as e:
        print(f"Interactive Watchlist startup error: {e}", flush=True)

    state = load_state()

    while True:
        try:
            print("Starting new cycle...", flush=True)

            news_items = collect_all_news()
            sent_count = 0

            # v5.9.3 Cost Control
            # عداد تحليلات OpenRouter في هذه الدورة فقط
            ai_counter = {"count": 0}

            for item in news_items:
                if sent_count >= MAX_ALERTS_PER_CYCLE:
                    break

                # v5.9.3 Cost Control
                # إذا وصلنا حد تحليلات OpenRouter نوقف معالجة باقي أخبار هذه الدورة لتخفيف اللوق والوقت
                if ai_counter.get("count", 0) >= MAX_AI_ANALYSES_PER_CYCLE:
                    print(
                        f"AI limit reached, stopping news processing for this cycle: {ai_counter.get('count', 0)}/{MAX_AI_ANALYSES_PER_CYCLE}",
                        flush=True
                    )
                    break

                sent = process_news_item(item, state, ai_counter=ai_counter)

                if sent:
                    sent_count += 1
                    time.sleep(2)

            print(
                f"Cycle done. Sent: {sent_count}. AI analyses: {ai_counter.get('count', 0)}/{MAX_AI_ANALYSES_PER_CYCLE}. Total items: {len(news_items)}",
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
