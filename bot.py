# AlphaBot Pro v5.9.5.6 After-hours SEC Quiet Mode + Report Polish
# RSS + Small-Cap Newswires + Finnhub + SEC Advanced Filings + OpenRouter + Telegram
# Gemini Primary + GPT-4o-mini Fallback + Interactive Watchlist + Translated Company News
# SEC Priority Mode + S-1/S-3/F-1/F-3 Smart Filter + Scheduled Reports + Market Pulse

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

VERSION = "v5.9.5.6 After-hours SEC Quiet Mode + Report Polish"

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

# v5.9.4.1 Cost Control
# الحد الأقصى لعدد الأخبار التي يتم إرسالها إلى OpenRouter للتحليل في كل دورة
MAX_AI_ANALYSES_PER_CYCLE = 3

TICKER_COOLDOWN_MINUTES = 45
SEC_FORM_COOLDOWN_MINUTES = 60

STATE_FILE = "seen_news.json"
WATCHLIST_FILE = "watchlist.json"
ALERT_CONTEXT_FILE = "alert_context.json"


# =========================
# v5.9.5 Scheduled Reports + Smart Alerts
# =========================

SAUDI_TZ_OFFSET = 3
AI_MODE = os.getenv("AI_MODE", "minimal").lower()  # minimal / off

MARKET_PULSE_ENABLED = os.getenv("MARKET_PULSE_ENABLED", "true").lower() == "true"
SMART_SILENCE_ENABLED = os.getenv("SMART_SILENCE_ENABLED", "true").lower() == "true"
MARKET_PULSE_INTERVAL_MINUTES = 30
MARKET_OPEN_KSA = "16:30"
MARKET_CLOSE_KSA = "23:00"

MAX_MARKET_PULSE_ALERTS_PER_DAY = int(os.getenv("MAX_MARKET_PULSE_ALERTS_PER_DAY", "12"))
MAX_NEW_OPPORTUNITY_ALERTS_PER_DAY = int(os.getenv("MAX_NEW_OPPORTUNITY_ALERTS_PER_DAY", "5"))
MAX_SEC_ALERTS_PER_DAY = int(os.getenv("MAX_SEC_ALERTS_PER_DAY", "10"))

REPORT_TIMES_KSA = {
    "11:00": "🚨 تقرير 11:00 ص — رصد مبكر",
    "13:30": "🚨 تقرير 1:30 م — تحديث البري ماركت المبكر",
    "15:30": "🚨 تقرير 3:30 م — رادار البري ماركت الرئيسي",
    "16:10": "🚨 تقرير 4:10 م — خطة قبل الافتتاح",
    "17:00": "🚨 تقرير 5:00 م — تأكيد بعد الافتتاح",
    "19:00": "🚨 تقرير 7:00 م — متابعة منتصف الجلسة المبكرة",
    "21:00": "🚨 تقرير 9:00 م — فلتر ما قبل النصف الثاني",
    "22:45": "🚨 تقرير 10:45 م — فلتر آخر الجلسة",
    "23:30": "🚨 تقرير 11:30 م — ملخص الإغلاق وخطة اليوم التالي",
    "23:45": "🚨 تقرير 11:45 م — فحص الأخبار بعد الإغلاق",
}

# لا نعتمد على مطابقة الدقيقة بالضبط لأن دورة البوت كل 90 ثانية وقد تفوّت 11:00:00.
# لذلك نسمح بإرسال التقرير خلال نافذة قصيرة بعد وقته، مرة واحدة فقط يوميًا.
REPORT_SEND_WINDOW_MINUTES = int(os.getenv("REPORT_SEND_WINDOW_MINUTES", "20"))
MARKET_PULSE_WINDOW_MINUTES = int(os.getenv("MARKET_PULSE_WINDOW_MINUTES", "5"))

# v5.9.5.6 Cleanup / Quiet Mode settings
MARKET_PULSE_SKIP_AFTER_REPORT_MINUTES = int(os.getenv("MARKET_PULSE_SKIP_AFTER_REPORT_MINUTES", "10"))
AFTER_HOURS_QUIET_ENABLED = os.getenv("AFTER_HOURS_QUIET_ENABLED", "true").lower() == "true"
AFTER_HOURS_QUIET_START_KSA = os.getenv("AFTER_HOURS_QUIET_START_KSA", "23:45")
AFTER_HOURS_QUIET_END_KSA = os.getenv("AFTER_HOURS_QUIET_END_KSA", "09:00")

# Smart Radar price tiers
RADAR_STRONG_LOW_PRICE_MAX = float(os.getenv("RADAR_STRONG_LOW_PRICE_MAX", "5.0"))
RADAR_GOOD_PRICE_MAX = float(os.getenv("RADAR_GOOD_PRICE_MAX", "10.0"))
RADAR_MAX_LOW_PRICE = float(os.getenv("RADAR_MAX_LOW_PRICE", "30.0"))


STATUS_OPPORTUNITY = "🟢 فرصة مراقبة"
STATUS_MOMENTUM = "🔥 زخم قوي"
STATUS_WAIT = "🟡 انتظار"
STATUS_RISK = "🔴 خطر"
STATUS_WARNING = "⚠️ تحذير"
STATUS_NEUTRAL = "⚪ بدون إشارة"
STATUS_POSITION = "🔵 إدارة مركز"

OWNED_TICKERS = {
    "IQST": {
        "note": "سهم مملوك مؤقتًا — الهدف الرجوع لرأس المال ثم الخروج",
        "breakeven": 2.32,
    }
}

QUOTE_CACHE = {}

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

# =========================
# v5.9.4.1 PRIORITY FILTER SETTINGS
# =========================

S_REGISTRATION_FORMS = {"S-1", "S-3", "F-1", "F-3"}

S1_SMART_FILTER_KEYWORDS = [
    "common stock",
    "ordinary shares",
    "resale",
    "resale shares",
    "selling stockholder",
    "selling stockholders",
    "warrants",
    "pre-funded warrants",
    "units",
    "registered direct",
    "public offering",
    "offering",
    "at-the-market",
    "atm offering",
    "atm program",
    "convertible",
    "convertible note",
    "convertible notes",
    "convertible preferred",
    "securities purchase agreement",
    "prospectus supplement",
]

STRONG_8K_KEYWORDS = [
    "offering",
    "registered direct",
    "private placement",
    "securities purchase agreement",
    "merger",
    "acquisition",
    "bankruptcy",
    "chapter 11",
    "nasdaq compliance",
    "delisting",
    "reverse split",
    "material agreement",
    "definitive agreement",
    "asset purchase",
]

STRONG_10Q_10K_KEYWORDS = [
    "going concern",
    "substantial doubt",
    "restatement",
    "material weakness",
    "default",
    "liquidity",
    "bankruptcy",
    "chapter 11",
]

LOW_VALUE_LAW_KEYWORDS = [
    "investigation launched",
    "shareholder alert",
    "shareholder update",
    "investor alert",
    "investor update",
    "investors are encouraged to contact",
    "law firm",
    "class action investigation",
    "class action",
    "securities fraud investigation",
    "sued after",
    "hagens berman",
    "rosen law",
    "levi & korsinsky",
    "glancy prongay",
    "pomerantz",
    "bragar eagel",
]

REAL_LEGAL_ACTION_KEYWORDS = [
    "class action filed",
    "lawsuit filed",
    "sec investigation",
    "doj investigation",
    "subpoena",
    "charged by the sec",
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



def now_ksa():
    return now_utc() + timedelta(hours=SAUDI_TZ_OFFSET)


def current_ksa_date_key():
    return now_ksa().strftime("%Y-%m-%d")


def current_ksa_time_hhmm():
    return now_ksa().strftime("%H:%M")


def minutes_from_hhmm(value):
    try:
        h, m = value.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def is_market_time_ksa():
    current = minutes_from_hhmm(current_ksa_time_hhmm())
    start = minutes_from_hhmm(MARKET_OPEN_KSA)
    end = minutes_from_hhmm(MARKET_CLOSE_KSA)
    return start <= current <= end


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

def send_telegram(message, reply_markup=None):
    if not BOT_TOKEN:
        print("BOT_TOKEN missing", flush=True)
        return

    if not CHAT_IDS:
        print("CHAT_IDS missing", flush=True)
        return

    for chat_id in CHAT_IDS:
        try:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True
            }

            if reply_markup:
                payload["reply_markup"] = reply_markup

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=15
            )
        except Exception as e:
            print(f"Telegram send error to {chat_id}: {e}", flush=True)


def startup_message():
    msg = f"""✅ AlphaBot Connected

الإصدار: {VERSION}
الحالة: يعمل الآن
المصادر: RSS + Small-Cap Newswires + Finnhub + SEC Advanced + Telegram
وضع الإرسال: Scheduled Reports + Smart Alerts + SEC Priority Mode
OpenRouter: Minimal — للأخبار المهمة/الغامضة فقط

وضع السعر:
🔥 الأسهم تحت ${LOW_PRICE_MAX:.0f}: قوة {LOW_PRICE_MIN_SCORE}/10 أو أعلى
🚨 الأسهم فوق ${LOW_PRICE_MAX:.0f}: قوة {BIG_STOCK_MIN_SCORE}/10 أو أعلى
⚪ السعر غير معروف: قوة {UNKNOWN_PRICE_MIN_SCORE}/10 أو أعلى

مصادر الأسهم الصغيرة:
GlobeNewswire + PR Newswire + BusinessWire

وضع التكلفة v5.9.5:
✅ SEC أولوية أولى قبل OpenRouter
✅ S-1 / S-3 / F-1 / F-3 لا تدخل AI إلا مع كلمات طرح/تخفيف واضحة أو إذا السهم في watchlist
✅ ترتيب الأخبار حسب الأهمية قبل التحليل
✅ MAX_AI_ANALYSES_PER_CYCLE = {MAX_AI_ANALYSES_PER_CYCLE}
✅ Market Pulse كل 30 دقيقة وقت السوق بشرط وجود تغيير مهم
✅ Smart Silence عند عدم وجود تغيير
✅ تقارير ثابتة بتوقيت السعودية
✅ ألوان الحالات مفعلة
✅ تخفيض/تجاهل أخبار مكاتب المحاماة الضعيفة
✅ After-hours SEC Quiet Mode لتقليل ضوضاء SEC بعد الإغلاق
✅ Gemini 2.5 Flash Lite أساسي
✅ GPT-4o-mini احتياطي
✅ Claude غير مستخدم

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
        "scheduled_reports_sent": {},
        "last_market_pulse_at": "",
        "ticker_status": {},
        "ticker_levels": {},
        "muted_tickers": {},
        "last_alert_context": {},
        "daily": {
            "date": current_date_key(),
            "ksa_date": current_ksa_date_key(),
            "count": 0,
            "pulse_count": 0,
            "new_opportunity_count": 0,
            "sec_count": 0,
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
        state.setdefault("scheduled_reports_sent", {})
        state.setdefault("last_market_pulse_at", "")
        state.setdefault("ticker_status", {})
        state.setdefault("ticker_levels", {})
        state.setdefault("muted_tickers", {})
        state.setdefault("last_alert_context", {})
        state.setdefault("daily", {
            "date": current_date_key(),
            "ksa_date": current_ksa_date_key(),
            "count": 0,
            "pulse_count": 0,
            "new_opportunity_count": 0,
            "sec_count": 0,
        })

        if state["daily"].get("date") != current_date_key():
            old_scheduled = state.get("scheduled_reports_sent", {})
            today_ksa = current_ksa_date_key()
            state["scheduled_reports_sent"] = {k: v for k, v in old_scheduled.items() if str(k).startswith(today_ksa)}
            state["daily"] = {
                "date": current_date_key(),
                "ksa_date": today_ksa,
                "count": 0,
                "pulse_count": 0,
                "new_opportunity_count": 0,
                "sec_count": 0,
            }

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

    # v5.9.5.2 Ticker Fix:
    # لا نعتبر أي رمز ينتهي بحرف W أو Z أو R أو U تلقائيًا warrant/right/unit،
    # لأن هذا كسر رموزًا عادية مثل RDW وحولها إلى RD في تقارير القائمة.
    # نعتمد فقط على الصيغ الواضحة مثل RDW.WS أو RDW-WS أو RDW.WT أو RDW.WTA.
    if "-" in t or "." in t or "^" in t:
        return True

    explicit_warrant_suffixes = ["WS", "WT", "WTA"]

    for s in explicit_warrant_suffixes:
        if len(t) > len(s) and t.endswith(s):
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

    # v5.9.5.2 Ticker Fix:
    # لا نحذف W/Z مفردة من نهاية الرمز لأن رموزًا عادية مثل RDW قد تنتهي بهذه الأحرف.
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
# 7.5) WATCHLIST + v5.9.4.1 PRIORITY FILTER
# =========================

def load_watchlist_symbols():
    """
    قراءة قائمة المراقبة بدون تعديل watchlist.json.
    يدعم أكثر من صيغة محتملة للملف.
    """
    if not os.path.exists(WATCHLIST_FILE):
        return set()

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        symbols = []

        if isinstance(data, list):
            symbols = data

        elif isinstance(data, dict):
            if isinstance(data.get("symbols"), list):
                symbols = data.get("symbols")
            elif isinstance(data.get("watchlist"), list):
                symbols = data.get("watchlist")
            else:
                for key, value in data.items():
                    if isinstance(value, bool) and value:
                        symbols.append(key)
                    elif isinstance(value, dict):
                        symbols.append(key)
                    elif isinstance(value, str):
                        symbols.append(value)

        return {normalize_common_ticker(x) for x in symbols if normalize_common_ticker(x)}

    except Exception as e:
        print(f"load_watchlist_symbols error: {e}", flush=True)
        return set()


def clean_text_for_priority(item):
    parts = []

    for key in ["title", "summary", "description", "source", "sec_form", "form", "type", "raw"]:
        value = item.get(key)
        if value:
            parts.append(str(value))

    return " ".join(parts).lower()


def get_item_source_type(item):
    source = str(item.get("source", "")).lower()
    item_type = str(item.get("type", "")).lower()

    if "sec" in source or "sec" in item_type or item.get("sec_form") or item.get("form"):
        return "sec"

    if any(x in source for x in ["globenewswire", "pr newswire", "businesswire", "business wire"]):
        return "small_cap_news"

    if "finnhub" in source:
        return "finnhub"

    return "general_news"


def is_low_value_law_news(item):
    text_l = clean_text_for_priority(item)
    has_law_noise = any(keyword in text_l for keyword in LOW_VALUE_LAW_KEYWORDS)
    has_real_action = any(keyword in text_l for keyword in REAL_LEGAL_ACTION_KEYWORDS)

    return has_law_noise and not has_real_action


def has_s1_smart_filter_keyword(item):
    text_l = clean_text_for_priority(item)
    return any(keyword in text_l for keyword in S1_SMART_FILTER_KEYWORDS)


def is_watchlist_item(item):
    ticker = normalize_common_ticker(item.get("ticker", ""))
    if not ticker:
        return False

    return ticker in load_watchlist_symbols()


def ensure_sec_item_enriched_for_priority(item):
    """
    إثراء مجاني قبل AI لاستخراج نص الإفصاح.
    يستخدم فقط للفلترة الذكية، وليس لتحليل OpenRouter.
    """
    try:
        if is_sec_source(item.get("source", "")) and len(clean_text(item.get("raw", ""))) < 1200:
            return enrich_sec_item(item)
    except Exception as e:
        print(f"priority SEC enrich error: {e}", flush=True)

    return item


def is_s_registration_allowed_for_ai(item):
    """
    v5.9.4.1:
    S-1 / S-3 / F-1 / F-3 لا تدخل OpenRouter إلا إذا:
    1) السهم في watchlist
    2) أو في نص الإفصاح كلمات طرح/تخفيف واضحة
    """
    if is_watchlist_item(item):
        return True

    if has_s1_smart_filter_keyword(item):
        return True

    item = ensure_sec_item_enriched_for_priority(item)

    return has_s1_smart_filter_keyword(item)


def is_important_8k_for_ai(item):
    text_l = clean_text_for_priority(item)

    if any(keyword in text_l for keyword in STRONG_8K_KEYWORDS):
        return True

    item = ensure_sec_item_enriched_for_priority(item)
    text_l = clean_text_for_priority(item)

    return any(keyword in text_l for keyword in STRONG_8K_KEYWORDS)


def is_important_10q_10k_for_ai(item):
    text_l = clean_text_for_priority(item)

    if any(keyword in text_l for keyword in STRONG_10Q_10K_KEYWORDS):
        return True

    item = ensure_sec_item_enriched_for_priority(item)
    text_l = clean_text_for_priority(item)

    return any(keyword in text_l for keyword in STRONG_10Q_10K_KEYWORDS)


def is_form4_allowed_for_ai(item):
    item = ensure_sec_item_enriched_for_priority(item)
    return form4_has_open_market_purchase(item.get("raw", ""))


def has_important_small_cap_text(item):
    text_l = clean_text_for_priority(item)
    return any(word in text_l for word in SMALL_CAP_KEYWORDS) or any(word in text_l for word in IMPORTANT_KEYWORDS)


def get_news_priority(item):
    """
    يعطي كل خبر درجة أولوية قبل OpenRouter.
    الأخبار التي ترجع 0 أو أقل لا تدخل AI.
    """
    source_type = get_item_source_type(item)
    source_name = item.get("source", "")
    form = get_sec_form_from_item(item)
    ticker = normalize_common_ticker(item.get("ticker", ""))
    text_l = clean_text_for_priority(item)

    priority = 0

    # 1) تجاهل أخبار مكاتب المحاماة الضعيفة غالبًا
    if is_low_value_law_news(item):
        return -10

    # 2) تعزيز أسهم قائمة المراقبة
    if ticker and ticker in load_watchlist_symbols():
        priority += 30

    # 3) SEC هو الأساس في هذه النسخة
    if source_type == "sec":
        priority += 50

        # S-1 Smart Filter
        if form in S_REGISTRATION_FORMS:
            if not is_s_registration_allowed_for_ai(item):
                print(f"v5.9.5 S-1 Smart Filter skipped: {ticker or 'NO_TICKER'} | {form} | {item.get('title')}", flush=True)
                return 0
            priority += 35

        elif form in ["424B5", "424B3", "424B4", "EFFECT", "FWP", "SC 13D", "SC 13G", "DEF 14A", "PRE 14A", "NT 10-Q", "NT 10-K"]:
            priority += 40

        elif form == "8-K":
            if not is_important_8k_for_ai(item):
                return 0
            priority += 30

        elif form in ["10-Q", "10-K"]:
            if not is_important_10q_10k_for_ai(item):
                return 0
            priority += 25

        elif form == "4":
            if not is_form4_allowed_for_ai(item):
                return 0
            priority += 20

        else:
            return 0

    # 4) أخبار الأسهم الصغيرة لا تدخل إلا إذا فيها كلمات مهمة
    elif source_type == "small_cap_news":
        if not has_important_small_cap_text(item):
            return 0
        priority += 30

    # 5) Finnhub و RSS العام أولوية أقل
    else:
        if has_important_small_cap_text(item):
            priority += 15
        elif any(word in text_l for word in US_MARKET_KEYWORDS):
            priority += 5
        else:
            return 0

    # 6) تعزيزات إضافية
    if "offering" in text_l or "registered direct" in text_l:
        priority += 15

    if "resale" in text_l or "selling stockholder" in text_l or "selling stockholders" in text_l:
        priority += 12

    if "common stock" in text_l or "warrants" in text_l or "units" in text_l:
        priority += 10

    if "fda" in text_l or "clinical" in text_l:
        priority += 15

    if "delisting" in text_l or "nasdaq compliance" in text_l:
        priority += 15

    if "bankruptcy" in text_l or "chapter 11" in text_l:
        priority += 20

    if "reverse split" in text_l:
        priority += 10

    return priority


def sort_and_filter_news_items(news_items):
    prioritized = []

    for item in news_items:
        try:
            priority = get_news_priority(item)
            if priority > 0:
                item["_priority"] = priority
                prioritized.append(item)
        except Exception as e:
            print(f"Priority filter error: {e} | {item.get('title', '')}", flush=True)

    prioritized.sort(
        key=lambda x: (
            x.get("_priority", 0),
            x.get("published_at") or datetime(1970, 1, 1, tzinfo=timezone.utc)
        ),
        reverse=True
    )

    print(f"v5.9.5.6 Priority Filter: {len(news_items)} -> {len(prioritized)}", flush=True)

    for i, item in enumerate(prioritized[:10], start=1):
        print(
            f"Priority #{i}: {item.get('_priority')} | {item.get('source')} | {item.get('ticker')} | {item.get('title')[:90]}",
            flush=True
        )

    return prioritized


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

    # إذا تم إثراء النص مسبقًا أثناء فلتر الأولوية، لا نعيد تحميل صفحة SEC
    if len(clean_text(item.get("raw", ""))) >= 1200:
        return item

    if not is_important_sec_form_from_item(item) and get_sec_form_from_item(item) not in ["8-K", "10-Q", "10-K"]:
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

    # v5.9.5.6: إذا العنوان يحتوي رمزًا واضحًا مثل (IBRX) فهو أوثق من تخمين AI.
    title_ticker = extract_parenthetical_ticker_from_title(item.get("title", ""))
    if title_ticker:
        return title_ticker

    ai_ticker = normalize_common_ticker(analysis.get("ticker", ""))
    item_ticker = normalize_common_ticker(item.get("ticker", ""))

    # إذا الرمز متورط في كود منتج مثل AP-SA02 ولم يوجد official، لا نثق به
    combined = f"{item.get('title','')} {item.get('raw','')}"
    if ai_ticker and likely_product_code_conflict(ai_ticker, combined):
        return ""

    if item_ticker and likely_product_code_conflict(item_ticker, combined):
        item_ticker = ""

    return ai_ticker or item_ticker



# =========================
# v5.9.5.4 SMART RADAR FILTER
# =========================

def is_valid_common_ticker_symbol(ticker):
    """
    يمنع إرسال تنبيهات برمز غير واضح مثل اسم شركة كامل.
    نسمح بالرموز الأمريكية الشائعة فقط مثل CLIK / RDW / TLS.
    """
    t = normalize_common_ticker(ticker)
    if not t:
        return False
    if " " in t:
        return False
    return re.fullmatch(r"[A-Z][A-Z0-9]{0,4}", t) is not None


def is_watchlist_symbol(ticker):
    t = normalize_common_ticker(ticker)
    return bool(t and t in load_watchlist_symbols())


def text_has_strong_opportunity_words(item):
    text_l = clean_text_for_priority(item)
    strong_words = [
        "swings to profit", "swing to profit", "turns profitable", "profitability",
        "strong revenue growth", "record revenue", "record revenues", "revenue growth",
        "raises guidance", "raises outlook", "increases guidance", "increases revenue target",
        "updates revenue target", "revenue target", "annual revenue",
        "fda approval", "fda clearance", "fast track", "breakthrough therapy",
        "phase 3", "positive topline", "topline results", "clinical trial",
        "contract", "purchase order", "strategic partnership", "partnership",
        "acquisition", "merger", "buyout", "definitive agreement",
    ]
    return any(w in text_l for w in strong_words)



def text_has_positive_catalyst_words(item):
    """
    v5.9.5.6 Positive Catalyst Boost:
    يحافظ على فرص مثل CLIK: سعر منخفض + رمز مؤكد + خبر إيجابي واضح.
    """
    text_l = clean_text_for_priority(item)
    positive_words = [
        "swings to profit", "swing to profit", "turns profitable", "returns to profit",
        "profitability", "positive ebitda", "adjusted ebitda", "net income turns positive",
        "record revenue", "record revenues", "record sales",
        "strong revenue growth", "revenue growth", "revenues increased", "sales increased",
        "raises guidance", "raises outlook", "increases guidance", "increases outlook",
        "raises revenue target", "updates revenue target", "revenue target",
        "fda approval", "fda clearance", "fast track designation", "breakthrough therapy",
        "positive phase", "met primary endpoint", "topline results", "positive topline",
        "major contract", "awarded contract", "purchase order", "government contract",
        "strategic partnership", "commercial agreement", "deployment agreement",
        "non-dilutive funding", "grant", "government funding",
        "acquisition offer", "buyout proposal", "merger agreement", "definitive agreement",
    ]
    return any(w in text_l for w in positive_words)


def extract_parenthetical_ticker_from_title(title):
    """
    يلتقط رمزًا واضحًا داخل العنوان مثل ImmunityBio (IBRX).
    لا يلتقط CIK أو كلمات عامة.
    """
    title = clean_text(title).upper()
    if not title:
        return ""
    bad = {"CEO", "CFO", "FDA", "SEC", "USA", "NYSE", "NASDAQ", "AMEX", "OTC", "EPS", "IPO"}
    for m in re.findall(r"\(([A-Z]{1,5})\)", title):
        ticker = normalize_common_ticker(m)
        if ticker and ticker not in bad and is_valid_common_ticker_symbol(ticker):
            return ticker
    # عناوين مكاتب المحاماة غالبًا تبدأ هكذا: IBRX SHAREHOLDER UPDATE
    m = re.match(r"^([A-Z]{1,5})\s+(SHAREHOLDER|INVESTOR)\s+(ALERT|UPDATE)", title)
    if m:
        ticker = normalize_common_ticker(m.group(1))
        if ticker and ticker not in bad and is_valid_common_ticker_symbol(ticker):
            return ticker
    return ""


def is_law_firm_noise_item(item):
    text_l = clean_text_for_priority(item)
    return any(keyword in text_l for keyword in LOW_VALUE_LAW_KEYWORDS)


def is_debt_only_sec_item(item):
    """
    يخفف ضوضاء SEC خارج القائمة: سندات عادية/medium-term notes ليست مثل common stock أو warrants أو convertible.
    """
    text_l = clean_text_for_priority(item)
    debt_words = [
        "medium-term note", "medium term note", "notes due", "senior notes",
        "floating rate notes", "fixed rate notes", "debt securities", "sofr", "bond", "bonds"
    ]
    equity_or_convertible_words = [
        "convertible", "common stock", "ordinary shares", "warrant", "warrants",
        "units", "registered direct", "private placement", "at-the-market", "atm offering",
        "resale", "selling stockholder", "selling stockholders", "equity"
    ]
    return any(w in text_l for w in debt_words) and not any(w in text_l for w in equity_or_convertible_words)
def is_after_hours_quiet_time_ksa(hhmm=None):
    """
    وضع الهدوء الليلي: بعد الإغلاق وحتى الصباح، نخفف SEC خارج القائمة.
    يدعم نطاق يعبر منتصف الليل مثل 23:45 -> 09:00.
    """
    if not AFTER_HOURS_QUIET_ENABLED:
        return False
    hhmm = hhmm or current_ksa_time_hhmm()
    start = AFTER_HOURS_QUIET_START_KSA
    end = AFTER_HOURS_QUIET_END_KSA
    if start <= end:
        return start <= hhmm < end
    return hhmm >= start or hhmm < end


def sec_text_has_equity_or_convertible_terms(item):
    text_l = clean_text_for_priority(item)
    terms = [
        "common stock", "ordinary shares", "class a common", "class b common",
        "resale", "selling stockholder", "selling stockholders",
        "warrant", "warrants", "units", "ads", "american depositary shares",
        "registered direct", "private placement", "at-the-market", "atm offering", "atm program",
        "convertible", "convertible notes", "convertible senior notes",
    ]
    return any(t in text_l for t in terms)


def is_generic_registration_or_supplement(item):
    """
    S-3ASR/F-3/S-3/424B3 العامة أو supplement بدون طرح أسهم واضح تعتبر ضوضاء خارج القائمة، خصوصًا بعد الإغلاق.
    """
    form = get_sec_form_from_item(item)
    text_l = clean_text_for_priority(item)
    generic_words = [
        "shelf registration", "automatic shelf", "s-3asr", "prospectus supplement",
        "supplement no", "supplemental prospectus", "updates and supplements",
        "updates, amends and supplements", "base prospectus",
    ]
    return form in ["S-3", "F-3", "424B3"] and any(w in text_l for w in generic_words) and not sec_text_has_equity_or_convertible_terms(item)


def after_hours_sec_quiet_filter_ok(item, analysis, ticker, price, category, direction, score):
    """
    v5.9.5.6:
    بعد الإغلاق، خارج القائمة، لا نرسل إلا SEC الواضح والمهم.
    الهدف تقليل زحمة 12-2 صباحًا بدون فقد التحذيرات الجوهرية.
    """
    if not is_after_hours_quiet_time_ksa():
        return True, "not quiet hours"
    if not is_sec_source(item.get("source", "")):
        return True, "not SEC"
    if is_watchlist_symbol(ticker):
        return True, "watchlist ticker"

    form = get_sec_form_from_item(item)
    category_n = normalize_category(category)

    # مسموح دائمًا تقريبًا لأنه تحذير/إشارة مهمة.
    if category_n in ["Late Filing", "Nasdaq Compliance", "Proxy / Vote", "M&A", "Bankruptcy"]:
        return True, "quiet-hours important SEC category"

    # Form 4 لا يصل أصلًا إلا مع شراء داخلي واضح حسب فلتر سابق.
    if form == "4":
        return True, "quiet-hours insider purchase"

    # طرح أسهم/تخفيف واضح.
    if form in ["424B5", "424B3", "424B4", "S-1", "S-3", "F-1", "F-3", "EFFECT", "FWP"]:
        if is_debt_only_sec_item(item):
            return False, "quiet-hours debt-only SEC suppressed"
        if is_generic_registration_or_supplement(item) and score < 8:
            return False, "quiet-hours generic registration/supplement suppressed"
        if sec_text_has_equity_or_convertible_terms(item):
            # فوق 30$ خارج القائمة نحتاج قوة أعلى إلا إذا هو common/convertible واضح وقوي.
            try:
                p = float(price) if price is not None else None
            except Exception:
                p = None
            if p is not None and p > LOW_PRICE_MAX and score < 8:
                return False, "quiet-hours high-price SEC below 8/10 suppressed"
            return True, "quiet-hours equity/convertible SEC"
        # نماذج تسجيل بدون كلمات تخفيف واضحة بعد الإغلاق = غالبًا ضوضاء.
        return False, "quiet-hours SEC lacks equity/convertible terms"

    # 8-K العادي بعد الإغلاق خارج القائمة لا يمر إلا إذا قوي جدًا.
    if form == "8-K":
        if category_n in ["Offering / Prospectus", "M&A", "Nasdaq Compliance"] and score >= 8:
            return True, "quiet-hours strong 8-K"
        return False, "quiet-hours outside-watchlist 8-K suppressed"

    return False, "quiet-hours SEC suppressed"


def ksa_time_label_ar(dt=None):
    dt = dt or now_ksa()
    hour24 = int(dt.strftime("%H"))
    minute = dt.strftime("%M")
    suffix = "ص" if hour24 < 12 else "م"
    hour12 = hour24 % 12
    if hour12 == 0:
        hour12 = 12
    return f"{hour12}:{minute} {suffix}"


def last_scheduled_report_minutes_ago(state):
    try:
        raw = state.get("last_scheduled_report_time")
        if not raw:
            return None
        last = datetime.fromisoformat(raw)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now_utc() - last.astimezone(timezone.utc)).total_seconds() / 60
    except Exception:
        return None


def category_is_financial_results(category):
    c = clean_text(category).lower()
    return c in ["financial results", "earnings"] or "financial result" in c or "earning" in c


def category_is_urgent_or_high_signal(category):
    c = normalize_category(category)
    return c in [
        "Offering / Prospectus",
        "Registration Effective",
        "FDA / Clinical",
        "Contract / Partnership",
        "M&A",
        "Bankruptcy",
        "Nasdaq Compliance",
        "Guidance",
        "Late Filing",
        "Proxy / Vote",
    ]


def non_sec_ticker_is_official(item, ticker):
    """
    للأخبار الصحفية خارج SEC: لا نقبل رمزًا استنتجه AI فقط.
    لازم يكون الرمز مؤكدًا من نص الخبر مثل NASDAQ: CLIK.
    هذا يمنع أخطاء مثل ربط خبر NextVision بـ RDW.
    """
    if is_sec_source(item.get("source", "")):
        return True

    official = normalize_common_ticker(item.get("official_ticker", ""))
    ticker = normalize_common_ticker(ticker)
    return bool(official and official == ticker)


def smart_radar_filter_ok(item, analysis, ticker, price, category, direction, score):
    """
    فلتر الرادار العام:
    - لا يضيق على أسهم القائمة.
    - يحافظ على فرص مثل CLIK: رمز مؤكد + سعر منخفض + خبر إيجابي واضح.
    - يمنع الضوضاء: 8-K محايد، سعر غير معروف، رمز غير واضح، أو خبر غير أمريكي مرتبط غلط.
    - v5.9.5.6: يضيف وضع هدوء SEC بعد الإغلاق.
    """
    ticker = normalize_common_ticker(ticker)
    source_name = item.get("source", "")
    form = get_sec_form_from_item(item)

    if category == "Macro":
        return True, "macro item"

    if is_watchlist_symbol(ticker):
        return True, "watchlist ticker"

    if not is_valid_common_ticker_symbol(ticker):
        return False, f"outside watchlist with invalid/unreliable ticker: {ticker}"

    # خارج القائمة من أخبار صحفية: لازم الرمز مؤكد من نص الخبر.
    if not is_sec_source(source_name) and not non_sec_ticker_is_official(item, ticker):
        title_ticker = extract_parenthetical_ticker_from_title(item.get("title", ""))
        if title_ticker and title_ticker != ticker:
            return False, f"outside watchlist ticker mismatch title={title_ticker} extracted={ticker}"
        return False, f"outside watchlist non-SEC ticker not officially confirmed: {ticker}"

    # أخبار مكاتب المحاماة خارج القائمة غالبًا ضوضاء، حتى لو فيها lawsuit.
    if not is_sec_source(source_name) and is_law_firm_noise_item(item):
        title_ticker = extract_parenthetical_ticker_from_title(item.get("title", ""))
        if title_ticker and title_ticker != ticker:
            return False, f"law-firm ticker mismatch title={title_ticker} extracted={ticker}"
        if not (score >= 9 and text_has_positive_catalyst_words(item)):
            return False, "outside watchlist law-firm/investor-alert noise"

    # خارج القائمة وسعر غير معروف: لا نرسل إلا SEC شديد الأهمية جدًا.
    if price is None:
        if is_sec_source(source_name) and form in ["424B5", "424B3", "424B4", "EFFECT"] and score >= 8:
            return True, "very important SEC with unknown price"
        return False, "outside watchlist with unknown price"

    # SEC خارج القائمة: تنظيف عام + وضع الهدوء بعد الإغلاق.
    if is_sec_source(source_name):
        quiet_ok, quiet_reason = after_hours_sec_quiet_filter_ok(item, analysis, ticker, price, category, direction, score)
        if not quiet_ok:
            return False, quiet_reason

        if is_debt_only_sec_item(item) and score < 8:
            return False, "outside watchlist debt-only SEC noise"

        if is_generic_registration_or_supplement(item) and score < 8:
            return False, "outside watchlist generic registration/supplement noise"

        if form == "8-K" and category_is_financial_results(category):
            if direction != "إيجابي" or score < 8:
                return False, "outside watchlist neutral/low-score 8-K financial results"

        if direction in ["محايد", "مختلط", "غير واضح"] and score < 8 and not category_is_urgent_or_high_signal(category):
            return False, "outside watchlist neutral SEC below 8/10"

        # الأسهم/الشركات فوق 30$ خارج القائمة تحتاج خبر أقوى، حتى لا تتحول الرادارات لأسهم كبيرة.
        try:
            p = float(price) if price is not None else None
        except Exception:
            p = None
        if p is not None and p > LOW_PRICE_MAX and score < 8:
            return False, "outside watchlist high-price SEC below 8/10"

        return True, "important SEC passed smart radar"

    # أخبار الرادار العام خارج القائمة: اسمح بفرص CLIK وما يشبهها.
    price_float = None
    try:
        price_float = float(price)
    except Exception:
        price_float = None

    strong_text = text_has_strong_opportunity_words(item) or text_has_positive_catalyst_words(item)
    low_price = price_float is not None and price_float <= RADAR_MAX_LOW_PRICE
    good_price = price_float is not None and price_float <= RADAR_GOOD_PRICE_MAX
    very_low_price = price_float is not None and price_float <= RADAR_STRONG_LOW_PRICE_MAX

    if direction == "إيجابي" and very_low_price and strong_text and score >= 6:
        return True, "outside watchlist sub-$5 positive catalyst"

    if direction == "إيجابي" and good_price and strong_text and score >= 7:
        return True, "outside watchlist sub-$10 positive catalyst"

    if direction == "إيجابي" and very_low_price and score >= 6 and normalize_category(category) in ["Guidance", "Financial Results", "Contract / Partnership", "FDA / Clinical", "M&A"]:
        return True, "outside watchlist very-low-price positive event"

    if category_is_urgent_or_high_signal(category) and direction == "إيجابي" and low_price and score >= 7:
        return True, "outside watchlist high-signal positive event"

    if score >= 8 and low_price:
        return True, "outside watchlist high-score low-price event"

    return False, "outside watchlist did not pass smart radar filter"

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

    radar_ok, radar_reason = smart_radar_filter_ok(item, analysis, ticker, price, category, normalize_direction(analysis.get("direction", "")), score)
    if not radar_ok:
        return False, radar_reason

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
        return f"💵 آخر سعر متاح: غير معروف | شرط الإرسال: {required_score}/10"

    if price < 0.01:
        price_text = f"${price:.6f}"
    else:
        price_text = f"${price:.2f}"

    if price_mode == "LOW":
        return f"💵 آخر سعر متاح: {price_text} | 🔥 سهم منخفض السعر | شرط الإرسال: {required_score}/10"

    return f"💵 آخر سعر متاح: {price_text} | 🚨 سهم كبير/مرتفع السعر | شرط الإرسال: {required_score}/10"


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

    priority_line = ""
    if item.get("_priority") is not None:
        priority_line = f"⚙️ أولوية v5.9.5.6: {item.get('_priority')}\n"

    msg = f"""{label}

🏷️ السهم: {ticker}
⭐ حالة القائمة: {'داخل القائمة الخاصة' if is_watchlist_symbol(ticker) else 'خارج القائمة / رادار عام'}
{sec_line}{official_line}📌 نوع الخبر: {category}
📊 التأثير المتوقع: {direction}
🔥 قوة الخبر: {score}/10
{price_line}
{priority_line}⏱️ وقت الخبر: {age}
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

    # v5.9.4.1:
    # إذا وصل الخبر من فلتر الأولوية وفيه _priority فهو مسموح يدخل المرحلة التالية.
    # هذا يمنع فلاتر العنوان القديمة من حذف SEC 8-K / 10-Q / S-1 بعد إثراء النص.
    if is_sec_source(source_name) and item.get("_priority", 0) > 0:
        pass
    else:
        if source_name in ["SEC 10-Q", "SEC 10-K"]:
            combined_l = f"{title} {item.get('raw', '')}".lower()
            if not any(w in combined_l for w in SEC_URGENT_WORDS):
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

    # v5.9.4.1 Cost Control
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
    ticker = normalize_common_ticker(analysis.get("ticker") or item.get("ticker", ""))
    record_alert_context(state, item, analysis)
    send_telegram(alert, reply_markup=make_alert_buttons(ticker))

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

    # v5.9.4.1: SEC أولاً ثم باقي المصادر، وبعدها ترتيب نهائي حسب الأولوية
    try:
        sec_items = fetch_sec_news()
        all_items.extend(sec_items)
        print(f"Collected SEC: {len(sec_items)}", flush=True)
    except Exception as e:
        print(f"collect SEC error: {e}", flush=True)

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
        rss_items = fetch_rss_news()
        all_items.extend(rss_items)
        print(f"Collected RSS: {len(rss_items)}", flush=True)
    except Exception as e:
        print(f"collect RSS error: {e}", flush=True)

    all_items = [
        x for x in all_items
        if x.get("published_at") is not None
    ]

    all_items = sort_and_filter_news_items(all_items)

    print(f"Total collected after priority filter: {len(all_items)}", flush=True)

    return all_items



# =========================
# 16.5) v5.9.5 SCHEDULED REPORTS + MARKET PULSE
# =========================

def get_stock_quote(ticker):
    """
    Finnhub quote موسع للتقارير والـ Market Pulse.
    لا يغير وظيفة get_stock_price القديمة حتى لا نكسر منطق الأخبار الحالي.
    """
    ticker = normalize_common_ticker(ticker)

    if not ticker or not FINNHUB_API_KEY:
        return None

    cached = QUOTE_CACHE.get(ticker)
    if cached and cached.get("time") and now_utc() - cached["time"] < timedelta(minutes=5):
        return cached.get("quote")

    try:
        r = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": FINNHUB_API_KEY},
            timeout=10
        )

        if r.status_code != 200:
            print(f"Quote error {ticker}: {r.status_code}", flush=True)
            return None

        data = r.json()
        current = data.get("c")

        if current is None or float(current) <= 0:
            return None

        quote = {
            "price": float(data.get("c") or 0),
            "change": float(data.get("d") or 0),
            "change_percent": float(data.get("dp") or 0),
            "previous_close": float(data.get("pc") or 0),
            "open": float(data.get("o") or 0),
            "high": float(data.get("h") or 0),
            "low": float(data.get("l") or 0),
        }

        QUOTE_CACHE[ticker] = {"quote": quote, "time": now_utc()}
        return quote

    except Exception as e:
        print(f"get_stock_quote error {ticker}: {e}", flush=True)
        return None


def price_text_from_quote(quote):
    if not quote or quote.get("price") is None:
        return "غير معروف"

    price = quote.get("price")
    change_percent = quote.get("change_percent", 0)
    sign = "+" if change_percent > 0 else ""

    if price < 0.01:
        price_text = f"${price:.6f}"
    else:
        price_text = f"${price:.2f}"

    return f"{price_text} | {sign}{change_percent:.2f}%"


def get_latest_ticker_context(state, ticker):
    ticker = normalize_common_ticker(ticker)
    return state.get("last_alert_context", {}).get(ticker, {})


def classify_watchlist_ticker(ticker, state=None):
    ticker = normalize_common_ticker(ticker)
    quote = get_stock_quote(ticker)
    context = get_latest_ticker_context(state or {}, ticker)

    status = STATUS_NEUTRAL
    reason = "لا يوجد خبر أو زخم واضح حاليًا"
    decision = "مراقبة فقط"
    alert_type = "neutral"

    if ticker in OWNED_TICKERS:
        status = STATUS_POSITION
        reason = OWNED_TICKERS[ticker].get("note", "سهم مملوك — إدارة مركز")
        decision = "إدارة مركز — راقب مستويات الخروج والدعم"
        alert_type = "position"

    if context:
        last_category = context.get("category", "")
        last_direction = context.get("direction", "")
        last_age = context.get("age", "")
        if last_category:
            reason = f"آخر محفز: {last_category} | التأثير: {last_direction} | {last_age}"
            if last_direction == "سلبي":
                status = STATUS_RISK
                decision = "حذر — راقب ردة فعل السعر ولا تطارد"
                alert_type = "risk"
            elif last_direction == "إيجابي" and status != STATUS_POSITION:
                status = STATUS_OPPORTUNITY
                decision = "فرصة مراقبة مشروطة بالثبات والفوليوم"
                alert_type = "opportunity"

    if quote:
        dp = quote.get("change_percent", 0)
        price = quote.get("price", 0)
        high = quote.get("high", 0)
        low = quote.get("low", 0)
        previous_close = quote.get("previous_close", 0)

        if ticker in OWNED_TICKERS:
            breakeven = float(OWNED_TICKERS[ticker].get("breakeven", 0) or 0)
            if breakeven and price >= breakeven * 0.97:
                status = STATUS_POSITION
                reason = f"اقترب من منطقة رأس المال {breakeven:.2f}"
                decision = "راقب الاختراق أو الرفض عند منطقة رأس المال"
                alert_type = "near_target"

        elif dp <= -6:
            status = STATUS_RISK
            reason = f"هبوط قوي {dp:.2f}%"
            decision = "تجنب مؤقت حتى تظهر إشارة ثبات"
            alert_type = "risk"

        elif dp >= 20:
            status = STATUS_WARNING
            reason = f"ارتفاع قوي جدًا {dp:.2f}% — احتمال مطاردة مرتفع"
            decision = "لا تطارد؛ انتظر تهدئة أو رجوع لمستوى دعم"
            alert_type = "do_not_chase"

        elif dp >= 10:
            status = STATUS_MOMENTUM
            reason = f"زخم سعري قوي {dp:.2f}%"
            decision = "مراقبة فقط؛ الدخول لا يكون إلا مع ثبات وفوليوم"
            alert_type = "momentum"

        elif dp >= 4 and status not in [STATUS_RISK, STATUS_WARNING, STATUS_POSITION]:
            status = STATUS_OPPORTUNITY
            reason = f"تحسن سعري واضح {dp:.2f}%"
            decision = "فرصة مراقبة بشرط استمرار الزخم"
            alert_type = "opportunity"

        elif -2 <= dp <= 2 and not context and status != STATUS_POSITION:
            status = STATUS_NEUTRAL
            reason = "حركة هادئة قرب الإغلاق السابق"
            decision = "بدون إشارة قوية"
            alert_type = "neutral"

        levels = []
        if low:
            levels.append(f"دعم تقريبي {low:.2f}")
        if high:
            levels.append(f"مقاومة تقريبيّة {high:.2f}")
        if previous_close:
            levels.append(f"إغلاق سابق {previous_close:.2f}")
        levels_text = " | ".join(levels) if levels else "غير متوفر"
    else:
        levels_text = "غير متوفر"

    return {
        "ticker": ticker,
        "quote": quote,
        "price_text": price_text_from_quote(quote),
        "status": status,
        "reason": reason,
        "decision": decision,
        "levels": levels_text,
        "alert_type": alert_type,
    }


def build_market_summary_line(scheduled_hhmm=None):
    """
    وصف مختصر لحالة المرحلة الزمنية. مؤشرات السوق الفعلية ستأتي لاحقًا في v5.9.6.
    """
    hhmm = scheduled_hhmm or current_ksa_time_hhmm()
    if hhmm in ["23:30", "23:45"] or hhmm >= "23:00":
        return "بعد الإغلاق — التركيز على أخبار After-hours، إفصاحات SEC، وأي حركة غير طبيعية بعد السوق."
    if is_market_time_ksa():
        return "السوق مفتوح الآن — استخدم Nasdaq / S&P / VIX كفلتر للحذر قبل الدخول."
    if hhmm < MARKET_OPEN_KSA:
        return "قبل الافتتاح — التركيز على البري ماركت، الأخبار، وإفصاحات SEC."
    return "خارج وقت السوق الرسمي — التركيز على الأخبار وإفصاحات SEC."


def build_watchlist_section(state, compact=False):
    watchlist = sorted(load_watchlist_symbols())
    lines = []

    if not watchlist:
        return ["⭐ القائمة الخاصة", "لا توجد أسهم في watchlist.json"]

    lines.append("⭐ القائمة الخاصة")

    for i, ticker in enumerate(watchlist, start=1):
        data = classify_watchlist_ticker(ticker, state=state)

        if compact:
            lines.append(f"{ticker}: {data['status']} — {data['reason']}")
        else:
            lines.append(
                f"{i}) {ticker} — {data['status']}\n"
                f"آخر سعر متاح: {data['price_text']}\n"
                f"السبب: {data['reason']}\n"
                f"المستويات: {data['levels']}\n"
                f"القرار: {data['decision']}"
            )

    return lines


def get_top_watchlist_ideas(state, limit=3, include_neutral_if_empty=True):
    priority = {
        STATUS_MOMENTUM: 1,
        STATUS_OPPORTUNITY: 2,
        STATUS_POSITION: 3,
        STATUS_RISK: 4,
        STATUS_WARNING: 5,
        STATUS_WAIT: 6,
        STATUS_NEUTRAL: 99,
    }
    ideas = []

    for ticker in sorted(load_watchlist_symbols()):
        data = classify_watchlist_ticker(ticker, state=state)
        ideas.append(data)

    ideas.sort(key=lambda x: priority.get(x.get("status"), 99))
    active = [x for x in ideas if x.get("status") != STATUS_NEUTRAL]

    if active:
        return active[:limit]

    if include_neutral_if_empty:
        return ideas[:limit]

    return []


def build_tomorrow_plan(state):
    lines = ["📌 خطة الغد المختصرة"]
    active = get_top_watchlist_ideas(state, limit=3, include_neutral_if_empty=False)

    if active:
        for data in active:
            lines.append(
                f"{data['ticker']}: {data['status']}\n"
                f"المستويات: {data['levels']}\n"
                f"الخطة: {data['decision']}"
            )
        neutral_count = 0
        for ticker in sorted(load_watchlist_symbols()):
            d = classify_watchlist_ticker(ticker, state=state)
            if d.get("status") == STATUS_NEUTRAL:
                neutral_count += 1
        if neutral_count:
            lines.append(f"⚪ البقية: {neutral_count} أسهم بدون إشارة قوية حاليًا.")
    else:
        lines.append("لا توجد إشارات قوية لخطة الغد حاليًا؛ الأفضل انتظار خبر/زخم جديد.")

    return lines


def build_top_watchlist_section(state, limit=3):
    lines = ["🔥 أهم 3 للمتابعة الآن"]
    top = get_top_watchlist_ideas(state, limit=limit, include_neutral_if_empty=False)

    if not top:
        lines.append("لا يوجد سهم بإشارة قوية حاليًا.")
        return lines

    for i, data in enumerate(top, start=1):
        lines.append(f"{i}) {data['ticker']} — {data['status']} | {data['decision']}")

    if len(top) < limit:
        lines.append(f"{len(top) + 1}) لا يوجد سهم إضافي بإشارة قوية")

    return lines


def build_after_hours_news_report(report_title, state, scheduled_hhmm=None):
    """
    تقرير 11:45 م: فحص أخبار/SEC بعد الإغلاق، وليس تكرارًا كاملاً لخطة 11:30.
    """
    lines = [
        report_title,
        f"📅 {now_ksa().strftime('%Y-%m-%d')} | 🇸🇦 توقيت السعودية",
        "",
        "📊 حالة السوق العامة",
        build_market_summary_line(scheduled_hhmm),
        "",
        "📰 فحص بعد الإغلاق",
        "أي خبر أو إفصاح SEC مهم بعد الإغلاق سيصل كتنبيه منفصل. هذا التقرير يراجع حالة القائمة وخطة المتابعة فقط.",
        "",
        "⭐ القائمة الخاصة",
    ]

    for ticker in sorted(load_watchlist_symbols()):
        data = classify_watchlist_ticker(ticker, state=state)
        lines.append(f"{ticker}: {data['status']} — {data['reason']}")

    lines.extend(["", *build_top_watchlist_section(state, limit=3)])
    lines.extend([
        "",
        "📌 متابعة الغد",
        "راقب أي خبر بعد الإغلاق أو SEC جديد لأنه قد يغيّر خطة الغد قبل البري ماركت.",
        "",
        "🎨 مفتاح الألوان:",
        "🟢 فرصة | 🔥 زخم | 🟡 انتظار | 🔴 خطر | ⚠️ تحذير | ⚪ بدون إشارة | 🔵 إدارة مركز",
    ])
    return "\n\n".join(lines)
def build_scheduled_report(report_title, state, scheduled_hhmm=None):
    hhmm = scheduled_hhmm or current_ksa_time_hhmm()

    if hhmm == "23:45":
        return build_after_hours_news_report(report_title, state, scheduled_hhmm=hhmm)

    compact = hhmm in ["19:00", "21:00", "22:45"]

    lines = [
        report_title,
        f"📅 {now_ksa().strftime('%Y-%m-%d')} | 🇸🇦 توقيت السعودية",
        "",
        "📊 حالة السوق العامة",
        build_market_summary_line(hhmm),
    ]

    if not is_market_time_ksa():
        lines.append("ملاحظة السعر: الأسعار المعروضة هي آخر سعر متاح من Finnhub وقد لا تمثل سعر البري ماركت/After-hours الحقيقي.")

    lines.append("")

    lines.extend(build_watchlist_section(state, compact=compact))

    lines.extend(["", *build_top_watchlist_section(state, limit=3)])

    if hhmm == "23:30":
        lines.extend(["", *build_tomorrow_plan(state)])

    lines.extend([
        "",
        "⚠️ قواعد سريعة",
        "لا مطاردة بعد ارتفاع قوي. الأفضل انتظار ثبات وفوليوم أو رجوع لمنطقة دعم.",
        "",
        "🎨 مفتاح الألوان:",
        "🟢 فرصة | 🔥 زخم | 🟡 انتظار | 🔴 خطر | ⚠️ تحذير | ⚪ بدون إشارة | 🔵 إدارة مركز",
    ])

    return "\n\n".join(lines)


def should_send_scheduled_report(state):
    """
    يرسل التقرير إذا دخلنا نافذة وقته بتوقيت السعودية.
    السبب: دورة البوت كل 90 ثانية تقريبًا، ومطابقة HH:MM بالضبط قد تجعل التقرير يفوت.
    يرجع: (scheduled_hhmm, report_title) أو None.
    """
    current_minutes = minutes_from_hhmm(current_ksa_time_hhmm())
    date_key = current_ksa_date_key()
    sent = state.setdefault("scheduled_reports_sent", {})

    # تنظيف مفاتيح قديمة حتى لا يكبر ملف الحالة
    try:
        state["scheduled_reports_sent"] = {
            k: v for k, v in sent.items() if str(k).startswith(date_key + "|")
        }
        sent = state["scheduled_reports_sent"]
    except Exception:
        pass

    for scheduled_hhmm, title in sorted(REPORT_TIMES_KSA.items(), key=lambda x: minutes_from_hhmm(x[0])):
        scheduled_minutes = minutes_from_hhmm(scheduled_hhmm)
        diff = current_minutes - scheduled_minutes

        if 0 <= diff <= REPORT_SEND_WINDOW_MINUTES:
            report_key = f"{date_key}|{scheduled_hhmm}"

            if sent.get(report_key):
                continue

            sent[report_key] = True
            print(
                f"Scheduled report due: {scheduled_hhmm} | current {current_ksa_time_hhmm()} KSA | {title}",
                flush=True,
            )
            return scheduled_hhmm, title

    return None


def maybe_send_scheduled_report(state):
    scheduled = should_send_scheduled_report(state)

    if not scheduled:
        return False

    scheduled_hhmm, report_title = scheduled
    msg = build_scheduled_report(report_title, state, scheduled_hhmm=scheduled_hhmm)
    send_telegram(msg)
    state["last_scheduled_report_time"] = now_utc().isoformat()
    state["last_scheduled_report_hhmm"] = scheduled_hhmm
    print(f"Scheduled report sent: {scheduled_hhmm} | {report_title}", flush=True)
    save_state(state)
    return True


def should_run_market_pulse(state):
    if not MARKET_PULSE_ENABLED:
        return False

    if not is_market_time_ksa():
        return False

    report_age = last_scheduled_report_minutes_ago(state)
    if report_age is not None and 0 <= report_age < MARKET_PULSE_SKIP_AFTER_REPORT_MINUTES:
        print(f"Market Pulse skipped: scheduled report sent {report_age:.1f} minutes ago", flush=True)
        return False

    now_dt = now_ksa()
    current_minutes = minutes_from_hhmm(now_dt.strftime("%H:%M"))

    # تشغيل حول :00 و :30 بنافذة بسيطة، بدل شرط الدقيقة المطابقة بالضبط.
    slot_start = (current_minutes // MARKET_PULSE_INTERVAL_MINUTES) * MARKET_PULSE_INTERVAL_MINUTES
    if current_minutes - slot_start > MARKET_PULSE_WINDOW_MINUTES:
        return False

    pulse_key = f"{current_ksa_date_key()}|{slot_start}"
    if state.get("last_market_pulse_at") == pulse_key:
        return False

    daily = state.setdefault("daily", {})
    if int(daily.get("pulse_count", 0)) >= MAX_MARKET_PULSE_ALERTS_PER_DAY:
        return False

    state["last_market_pulse_at"] = pulse_key
    print(f"Market Pulse window: slot {slot_start} | current {now_dt.strftime('%H:%M')} KSA", flush=True)
    return True


def detect_watchlist_changes(state):
    changes = []
    statuses = state.setdefault("ticker_status", {})

    for ticker in sorted(load_watchlist_symbols()):
        data = classify_watchlist_ticker(ticker, state=state)
        old_status = statuses.get(ticker)
        new_status = data["status"]

        if old_status and old_status != new_status:
            reason = data["reason"]
            decision = data["decision"]

            if old_status == STATUS_RISK and new_status == STATUS_NEUTRAL:
                reason = "خرج من حالة الخطر اللحظي، لكن لا توجد إشارة إيجابية واضحة بعد."
                decision = "لا دخول؛ مراقبة فقط حتى يظهر ثبات وفوليوم."

            elif old_status == STATUS_OPPORTUNITY and new_status == STATUS_NEUTRAL:
                reason = "خرج من حالة المتابعة الإيجابية، والزخم لم يعد كافيًا حاليًا."
                decision = "إلغاء المتابعة النشطة مؤقتًا؛ مراقبة فقط."

            elif old_status == STATUS_MOMENTUM and new_status in [STATUS_OPPORTUNITY, STATUS_NEUTRAL]:
                reason = "الزخم القوي بدأ يهدأ؛ نراقب الثبات بدل المطاردة."
                decision = "لا مطاردة؛ انتظر ثباتًا جديدًا أو رجوعًا لمستوى دعم."

            changes.append({
                "ticker": ticker,
                "old": old_status,
                "new": new_status,
                "reason": reason,
                "decision": decision,
                "levels": data["levels"],
            })

        # أول تشغيل: نحفظ الحالة ولا نرسل تنبيه تغير حتى لا يزعجك برسالة طويلة.
        statuses[ticker] = new_status

    return changes


def build_market_pulse_message(changes, state):
    if not changes:
        if SMART_SILENCE_ENABLED:
            return ""
        return f"⚡ تحديث {ksa_time_label_ar()} — لا يوجد تغيير مهم\nالأفضل: انتظار."

    lines = [
        f"⚡ تحديث {ksa_time_label_ar()} — نبض السوق",
        "",
        "🔔 تغيرات مهمة في القائمة:",
    ]

    for ch in changes[:5]:
        lines.append(
            f"{ch['ticker']}\n"
            f"من: {ch['old']}\n"
            f"إلى: {ch['new']}\n"
            f"السبب: {ch['reason']}\n"
            f"المستويات: {ch['levels']}\n"
            f"القرار: {ch['decision']}"
        )

    top = get_top_watchlist_ideas(state, limit=3)
    if top:
        lines.extend(["", "🔥 أهم 3 الآن:"])
        for i, data in enumerate(top, start=1):
            lines.append(f"{i}) {data['ticker']} — {data['status']}")

    return "\n\n".join(lines)


def maybe_send_market_pulse(state):
    if not should_run_market_pulse(state):
        return False

    changes = detect_watchlist_changes(state)
    msg = build_market_pulse_message(changes, state)

    if not msg:
        save_state(state)
        return False

    send_telegram(msg)
    state.setdefault("daily", {})["pulse_count"] = int(state.get("daily", {}).get("pulse_count", 0)) + 1
    save_state(state)
    return True


def record_alert_context(state, item, analysis):
    try:
        ticker = normalize_common_ticker(analysis.get("ticker") or item.get("ticker", ""))
        if not ticker:
            return

        context = {
            "ticker": ticker,
            "title": clean_text(item.get("title", ""))[:180],
            "category": normalize_category(analysis.get("category", "")),
            "direction": normalize_direction(analysis.get("direction", "")),
            "score": analysis.get("impact_score", ""),
            "source": item.get("source", ""),
            "sec_form": get_sec_form_from_item(item),
            "cik": get_cik_from_item(item),
            "price": analysis.get("stock_price"),
            "price_mode": analysis.get("price_mode"),
            "required_score": analysis.get("required_score"),
            "watchlist": is_watchlist_symbol(ticker),
            "why": clean_text(analysis.get("why_important_ar", ""))[:500],
            "summary": clean_text(analysis.get("summary_ar", ""))[:500],
            "url": item.get("url", ""),
            "age": human_age(item.get("published_at")),
            "time": now_utc().isoformat(),
        }
        state.setdefault("last_alert_context", {})[ticker] = context

        # ملف مستقل تقرأه أزرار telegram_buttons.py لشرح سبب التنبيه الحقيقي.
        try:
            alert_context = {}
            if os.path.exists(ALERT_CONTEXT_FILE):
                with open(ALERT_CONTEXT_FILE, "r", encoding="utf-8") as f:
                    alert_context = json.load(f)
            if not isinstance(alert_context, dict):
                alert_context = {}
            alert_context[ticker] = context
            # احتفظ بآخر 200 رمز فقط.
            if len(alert_context) > 200:
                alert_context = dict(list(alert_context.items())[-200:])
            with open(ALERT_CONTEXT_FILE, "w", encoding="utf-8") as f:
                json.dump(alert_context, f, ensure_ascii=False, indent=2)
        except Exception as file_error:
            print(f"alert_context write error: {file_error}", flush=True)

        if is_sec_source(item.get("source", "")):
            daily = state.setdefault("daily", {})
            daily["sec_count"] = int(daily.get("sec_count", 0)) + 1

    except Exception as e:
        print(f"record_alert_context error: {e}", flush=True)


def make_alert_buttons(ticker):
    """
    v5.9.5.3 Alert Buttons Fix
    يجب أن تكون callback_data بنفس الصيغة التي يدعمها telegram_buttons.py:
    action|TICKER
    وليس action:TICKER، حتى تعمل أزرار التنبيهات التلقائية.
    """
    ticker = normalize_common_ticker(ticker)
    if not ticker:
        return None

    return {
        "inline_keyboard": [
            [
                {"text": "❓ السبب", "callback_data": f"reason|{ticker}"},
                {"text": "📊 تقرير", "callback_data": f"report_menu|{ticker}"},
            ],
            [
                {"text": "📰 الأخبار", "callback_data": f"news_menu|{ticker}"},
                {"text": "📄 SEC", "callback_data": f"sec_menu|{ticker}"},
            ],
            [
                {"text": "⭐ مراقبة", "callback_data": f"watch_menu|{ticker}"},
                {"text": "🔕 تجاهل", "callback_data": f"mute_menu|{ticker}"},
            ],
        ]
    }


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
    print(f"MAX_AI_ANALYSES_PER_CYCLE: {MAX_AI_ANALYSES_PER_CYCLE}", flush=True)
    print("SEC_PRIORITY_MODE: ON", flush=True)
    print("S1_SMART_FILTER: ON", flush=True)
    print("LAW_FIRM_NOISE_FILTER: ON", flush=True)
    print("CLAUDE: OFF", flush=True)
    print("SMALL_CAP_SOURCES: ON", flush=True)
    print("SEC_ADVANCED_FORMS: ON", flush=True)
    print("SEC_CIK_TO_COMMON_TICKER: ON", flush=True)
    print("SEC_CIK_FORM_COOLDOWN: ON", flush=True)
    print("FORM_4_PURCHASE_FILTER: ON", flush=True)
    print("OFFICIAL_NEWS_TICKER_EXTRACTION: ON", flush=True)
    print("PRODUCT_CODE_TICKER_BLOCK: ON", flush=True)
    print(f"AI_MODE: {AI_MODE}", flush=True)
    print(f"MARKET_PULSE_ENABLED: {MARKET_PULSE_ENABLED}", flush=True)
    print(f"SMART_SILENCE_ENABLED: {SMART_SILENCE_ENABLED}", flush=True)
    print("SCHEDULED_REPORTS_KSA: ON", flush=True)
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

            maybe_send_scheduled_report(state)
            maybe_send_market_pulse(state)

            news_items = collect_all_news()
            sent_count = 0

            # v5.9.4.1 Cost Control
            # عداد تحليلات OpenRouter في هذه الدورة فقط
            ai_counter = {"count": 0}

            for item in news_items:
                if sent_count >= MAX_ALERTS_PER_CYCLE:
                    break

                # v5.9.4.1 Cost Control
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
