# AlphaBot Pro v5.9.7.1 Daily Opportunities Buttons
# telegram_buttons.py
# واجهة أزرار مختصرة + زر فرص اليوم + قوائم فرعية منظمة
# متوافق مع AlphaBot v5.9.7 Daily Opportunities Manual Mode
# يعمل بنظام getUpdates داخل Thread مستقل حتى لا يؤثر على دورة الأخبار الرئيسية.

import json
import os
import re
import threading
import time
from datetime import datetime, timezone, timedelta

import requests

from watchlist_storage import (
    normalize_ticker,
    add_ticker,
    remove_ticker,
    format_watchlist,
    is_in_watchlist,
)
from sharia_checker import check_sharia
from quick_report import build_quick_report
from stock_news import format_latest_news_for_ticker


POLL_INTERVAL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 20
BUTTONS_STATE_FILE = "telegram_buttons_state.json"
ALERT_CONTEXT_FILE = "alert_context.json"
MAX_TELEGRAM_TEXT = 3900
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "AlphaBot aktfaaksa@gmail.com")
DAILY_OPPORTUNITIES_FILE = os.getenv("DAILY_OPPORTUNITIES_FILE", "/data/daily_opportunities.json")
_SEC_TICKER_CACHE = None


_runtime = {
    "bot_token": None,
    "chat_ids": [],
    "get_stock_price_func": None,
    "collect_all_news_func": None,
    "analyze_with_ai_func": None,
    "normalize_common_ticker_func": None,
    "send_telegram_func": None,
    "offset": None,
    "running": False,
}


def _api_url(method):
    return f"https://api.telegram.org/bot{_runtime['bot_token']}/{method}"


def _allowed_chat(chat_id):
    allowed = _runtime.get("chat_ids") or []
    try:
        return int(chat_id) in [int(x) for x in allowed]
    except Exception:
        return False


def _post(method, payload):
    try:
        r = requests.post(
            _api_url(method),
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS
        )
        if r.status_code != 200:
            print(f"Telegram API {method} error: {r.status_code} | {r.text[:300]}", flush=True)
            return None
        return r.json()
    except Exception as e:
        print(f"Telegram API {method} exception: {e}", flush=True)
        return None


def _truncate(text):
    text = str(text or "")
    if len(text) <= MAX_TELEGRAM_TEXT:
        return text
    return text[:MAX_TELEGRAM_TEXT - 80] + "\n\n… تم اختصار النص لطوله."


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": _truncate(text),
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _post("sendMessage", payload)


def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": _truncate(text),
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _post("editMessageText", payload)


def answer_callback(callback_query_id, text=None):
    payload = {
        "callback_query_id": callback_query_id,
    }

    if text:
        payload["text"] = text
        payload["show_alert"] = False

    return _post("answerCallbackQuery", payload)


# =========================
# State helpers for buttons
# =========================

def load_buttons_state():
    default = {
        "muted": {},
        "last_reason": {},
    }
    if not os.path.exists(BUTTONS_STATE_FILE):
        return default
    try:
        with open(BUTTONS_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("muted", {})
        data.setdefault("last_reason", {})
        return data
    except Exception as e:
        print(f"load_buttons_state error: {e}", flush=True)
        return default


def save_buttons_state(state):
    try:
        with open(BUTTONS_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"save_buttons_state error: {e}", flush=True)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _ksa_date_key():
    return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d")


def _ensure_parent_dir(path):
    try:
        parent = os.path.dirname(os.path.abspath(path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
    except Exception as e:
        print(f"ensure parent dir error {path}: {e}", flush=True)


def default_daily_opportunities_data():
    return {
        "date": _ksa_date_key(),
        "updated_at": _now_iso(),
        "items": [],
    }


def load_daily_opportunities():
    """
    فرص اليوم محفوظة في Railway Volume عبر DAILY_OPPORTUNITIES_FILE.
    هذا الملف مستقل تمامًا عن watchlist.json.
    """
    if not os.path.exists(DAILY_OPPORTUNITIES_FILE):
        data = default_daily_opportunities_data()
        save_daily_opportunities(data)
        return data

    try:
        with open(DAILY_OPPORTUNITIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("daily opportunities data is not dict")

        data.setdefault("date", _ksa_date_key())
        data.setdefault("updated_at", _now_iso())
        data.setdefault("items", [])

        cleaned = []
        seen = set()
        for item in data.get("items", []):
            if isinstance(item, str):
                ticker = normalize_ticker(item)
                row = {}
            elif isinstance(item, dict):
                ticker = normalize_ticker(item.get("ticker", ""))
                row = dict(item)
            else:
                continue

            if not ticker or ticker in seen:
                continue

            row["ticker"] = ticker
            row.setdefault("status", "🟢 أولوية")
            row.setdefault("state", "نشطة اليوم")
            row.setdefault("reason", "مرشح من فلتر Investing Pro+ + شرعي")
            row.setdefault("decision", "مراقبة قوية، لا مطاردة.")
            row.setdefault("added_at", _now_iso())
            cleaned.append(row)
            seen.add(ticker)

        data["items"] = cleaned
        return data

    except Exception as e:
        print(f"load_daily_opportunities error: {e} | file={DAILY_OPPORTUNITIES_FILE}", flush=True)
        data = default_daily_opportunities_data()
        save_daily_opportunities(data)
        return data


def save_daily_opportunities(data):
    try:
        _ensure_parent_dir(DAILY_OPPORTUNITIES_FILE)
        data["updated_at"] = _now_iso()
        data.setdefault("date", _ksa_date_key())
        data.setdefault("items", [])

        tmp = DAILY_OPPORTUNITIES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp, DAILY_OPPORTUNITIES_FILE)
        return True
    except Exception as e:
        print(f"save_daily_opportunities error: {e} | file={DAILY_OPPORTUNITIES_FILE}", flush=True)
        return False


def get_daily_opportunity_items():
    return load_daily_opportunities().get("items", [])


def is_in_daily_opportunities(ticker):
    ticker = normalize_ticker(ticker)
    return any(normalize_ticker(x.get("ticker", "")) == ticker for x in get_daily_opportunity_items())


def add_daily_opportunity(ticker, status="🟢 أولوية", reason=None, decision=None, state_label="نشطة اليوم"):
    ticker = normalize_ticker(ticker)
    if not ticker:
        return False, "رمز السهم غير صحيح"

    data = load_daily_opportunities()
    items = data.setdefault("items", [])

    for item in items:
        if normalize_ticker(item.get("ticker", "")) == ticker:
            return True, f"{ticker} موجود مسبقًا في فرص اليوم"

    items.append({
        "ticker": ticker,
        "status": status or "🟢 أولوية",
        "state": state_label or "نشطة اليوم",
        "reason": reason or "مرشح من فلتر Investing Pro+ + شرعي",
        "decision": decision or "مراقبة قوية، لا مطاردة.",
        "added_at": _now_iso(),
    })

    if not save_daily_opportunities(data):
        return False, "تعذر حفظ فرص اليوم"

    return True, f"تمت إضافة {ticker} إلى فرص اليوم"


def remove_daily_opportunity(ticker):
    ticker = normalize_ticker(ticker)
    if not ticker:
        return False, "رمز السهم غير صحيح"

    data = load_daily_opportunities()
    items = data.setdefault("items", [])
    before = len(items)
    data["items"] = [x for x in items if normalize_ticker(x.get("ticker", "")) != ticker]

    if len(data["items"]) == before:
        return False, f"{ticker} غير موجود في فرص اليوم"

    if not save_daily_opportunities(data):
        return False, "تعذر حفظ فرص اليوم"

    return True, f"تم حذف {ticker} من فرص اليوم"


def clear_daily_opportunities():
    data = load_daily_opportunities()
    count = len(data.get("items", []))
    data["date"] = _ksa_date_key()
    data["items"] = []

    if not save_daily_opportunities(data):
        return False, "تعذر مسح فرص اليوم"

    return True, f"تم مسح فرص اليوم ({count} سهم)"


def format_daily_opportunities_list():
    data = load_daily_opportunities()
    items = data.get("items", [])

    if not items:
        return "🔥 فرص اليوم من فلتر Investing Pro+\n\nلا توجد فرص يومية مضافة حاليًا."

    lines = [
        "🔥 فرص اليوم من فلتر Investing Pro+",
        f"📅 تاريخ القائمة: {data.get('date', _ksa_date_key())}",
        f"📌 العدد: {len(items)}",
        "",
    ]

    for i, item in enumerate(items, start=1):
        ticker = normalize_ticker(item.get("ticker", ""))
        status = item.get("status", "🟢 أولوية")
        state_label = item.get("state", "نشطة اليوم")
        reason = item.get("reason", "مرشح من فلتر Investing Pro+ + شرعي")
        lines.append(f"{i}. {ticker} — {status} — {state_label}\nالسبب: {reason}")

    lines.append("")
    lines.append(f"المصدر: {DAILY_OPPORTUNITIES_FILE}")
    return "\n\n".join(lines)


def set_mute(ticker, minutes, label):
    ticker = normalize_ticker(ticker)
    state = load_buttons_state()
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    state.setdefault("muted", {})[ticker] = {
        "until": until.isoformat(),
        "label": label,
    }
    save_buttons_state(state)
    return until


# =========================
# Keyboard helpers
# =========================

def is_ticker_message(text):
    if not text:
        return False

    text = text.strip().upper().replace("$", "")

    # منع الأوامر
    if text.startswith("/"):
        return False

    # رمز واحد فقط مثل RDW أو BRK.B أو BRK-B
    return re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", text) is not None


def main_keyboard(ticker):
    """
    v5.9.7.1: الأزرار الرئيسية + زر فرص اليوم مستقل عن قائمة المراقبة.
    """
    ticker = normalize_ticker(ticker)

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
                {"text": "🔥 فرص اليوم", "callback_data": f"daily_menu|{ticker}"},
            ],
            [
                {"text": "🔕 تجاهل", "callback_data": f"mute_menu|{ticker}"},
            ],
        ]
    }


def back_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ]
        ]
    }


def report_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "📊 تقرير سريع", "callback_data": f"report|{ticker}"},
                {"text": "💵 السعر", "callback_data": f"price|{ticker}"},
            ],
            [
                {"text": "🎯 المستويات", "callback_data": f"levels|{ticker}"},
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
            ],
        ]
    }


def news_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "🕐 آخر الأخبار", "callback_data": f"news|{ticker}"},
                {"text": "🧾 مختصر", "callback_data": f"news_summary|{ticker}"},
            ],
            [
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ],
        ]
    }


def sec_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "📄 آخر SEC", "callback_data": f"sec_latest|{ticker}"},
                {"text": "⚠️ المهم فقط", "callback_data": f"sec_important|{ticker}"},
            ],
            [
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ],
        ]
    }


def watch_keyboard(ticker):
    ticker = normalize_ticker(ticker)

    if is_in_watchlist(ticker):
        return {
            "inline_keyboard": [
                [
                    {"text": "🎯 المستويات", "callback_data": f"levels|{ticker}"},
                    {"text": "➖ حذف", "callback_data": f"remove|{ticker}"},
                ],
                [
                    {"text": "📋 القائمة", "callback_data": "list|ALL"},
                    {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
                ],
            ]
        }

    return {
        "inline_keyboard": [
            [
                {"text": "🧾 فحص الشرعية", "callback_data": f"sharia|{ticker}"},
                {"text": "➕ إضافة", "callback_data": f"add|{ticker}"},
            ],
            [
                {"text": "📋 القائمة", "callback_data": "list|ALL"},
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
            ],
        ]
    }


def daily_opportunities_keyboard(ticker):
    ticker = normalize_ticker(ticker)

    if is_in_daily_opportunities(ticker):
        return {
            "inline_keyboard": [
                [
                    {"text": "➖ حذف من فرص اليوم", "callback_data": f"daily_remove|{ticker}"},
                    {"text": "📋 فرص اليوم", "callback_data": "daily_list|ALL"},
                ],
                [
                    {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
                    {"text": "إلغاء", "callback_data": "cancel|ALL"},
                ],
            ]
        }

    return {
        "inline_keyboard": [
            [
                {"text": "🧾 فحص الشرعية", "callback_data": f"daily_sharia|{ticker}"},
                {"text": "➕ إضافة لفرص اليوم", "callback_data": f"daily_add|{ticker}"},
            ],
            [
                {"text": "📋 فرص اليوم", "callback_data": "daily_list|ALL"},
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
            ],
        ]
    }


def confirm_daily_add_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "✅ نعم، أضفه لفرص اليوم", "callback_data": f"confirm_daily_add|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ]
        ]
    }


def mute_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "ساعة", "callback_data": f"mute_1h|{ticker}"},
                {"text": "اليوم", "callback_data": f"mute_today|{ticker}"},
            ],
            [
                {"text": "⬅️ رجوع", "callback_data": f"back|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ],
        ]
    }


def confirm_add_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "✅ نعم، أضفه", "callback_data": f"confirm_add|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ]
        ]
    }


def temporary_add_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "⚠️ إضافة مؤقتة", "callback_data": f"temp_add|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ]
        ]
    }


# =========================
# Content builders
# =========================

def get_price_text(ticker):
    ticker = normalize_ticker(ticker)
    get_price = _runtime.get("get_stock_price_func")
    if not get_price:
        return "السعر: غير متاح — دالة السعر غير مرتبطة."
    try:
        price = get_price(ticker)
        if price is None:
            return f"💵 {ticker}: السعر غير معروف حاليًا."
        if float(price) < 0.01:
            return f"💵 {ticker}: ${float(price):.6f}"
        return f"💵 {ticker}: ${float(price):.2f}"
    except Exception as e:
        return f"تعذر جلب السعر لـ {ticker}: {e}"



def load_alert_context():
    if not os.path.exists(ALERT_CONTEXT_FILE):
        return {}
    try:
        with open(ALERT_CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"load_alert_context error: {e}", flush=True)
        return {}


def format_context_price(context):
    price = context.get("price")
    try:
        if price is None:
            return "السعر: غير معروف"
        p = float(price)
        if p < 0.01:
            return f"آخر سعر متاح: ${p:.6f}"
        return f"آخر سعر متاح: ${p:.2f}"
    except Exception:
        return "السعر: غير معروف"


def build_alert_context_reason_text(ticker, context):
    ticker = normalize_ticker(ticker)
    watch_state = "داخل القائمة الخاصة" if context.get("watchlist") else "خارج القائمة / رادار عام"
    sec_form = context.get("sec_form") or "-"
    category = context.get("category") or "غير محدد"
    direction = context.get("direction") or "غير واضح"
    score = context.get("score") or "?"
    required = context.get("required_score") or "?"
    source = context.get("source") or "غير معروف"
    title = context.get("title") or "-"
    why = context.get("why") or "تم إرسال التنبيه لأنه اجتاز فلتر الخبر/الإفصاح المهم."
    summary = context.get("summary") or ""
    price_line = format_context_price(context)

    return f"""❓ سبب تنبيه {ticker}

الحالة: {watch_state}
{price_line}

📄 نموذج SEC: {sec_form}
📌 نوع الخبر: {category}
📊 التأثير: {direction}
🔥 القوة: {score}/10 | شرط الإرسال: {required}/10
📰 المصدر: {source}

العنوان:
{title}

لماذا أرسله البوت؟
{why}

الملخص:
{summary}

القرار:
مراقبة فقط، ولا إضافة للقائمة إلا بعد فحص الشرعية ووضوح السعر/الفوليوم.
"""

def build_reason_text(ticker):
    ticker = normalize_ticker(ticker)

    # إذا كان هناك تنبيه تلقائي محفوظ لهذا السهم، اعرض سبب التنبيه الحقيقي.
    alert_context = load_alert_context().get(ticker)
    if alert_context:
        return build_alert_context_reason_text(ticker, alert_context)

    exists = "موجود في قائمة المراقبة" if is_in_watchlist(ticker) else "غير موجود في قائمة المراقبة"
    price_line = get_price_text(ticker)

    status = "⚪ بدون إشارة"
    reason = "تم فتح بطاقة السهم عند الطلب، وليس بسبب تنبيه تلقائي محفوظ في هذه الرسالة."

    if is_in_watchlist(ticker):
        status = "🟡 مراقبة"
        reason = "السهم ضمن قائمتك الخاصة، لذلك تظهر له خيارات المتابعة والتقرير والأخبار وSEC."

    if ticker == "IQST":
        status = "🔵 إدارة مركز"
        reason = "السهم مضاف كمركز مملوك مؤقتًا، والتركيز يكون على الرجوع لرأس المال وخطة الخروج."

    return f"""❓ سبب ظهور {ticker}

الحالة: {exists}
{price_line}

التصنيف الحالي: {status}
السبب:
{reason}

متى يرسل البوت تنبيه تلقائي؟
- خبر قوي
- SEC مهم
- تغير حالة السهم
- كسر مقاومة أو فقد دعم
- فوليوم أو حركة غير طبيعية
- قرب هدف أو دعم مهم
"""


def build_levels_text(ticker):
    ticker = normalize_ticker(ticker)
    price_line = get_price_text(ticker)

    if ticker == "IQST":
        return f"""🎯 مستويات {ticker}

{price_line}

مستويات خاصة:
- 2.05 مقاومة أولى / منطقة متابعة
- 2.32 هدف الرجوع لرأس المال حسب خطتك

القرار:
🔵 إدارة مركز — راقب الاختراق أو الرفض عند المستويات المهمة.
"""

    return f"""🎯 مستويات {ticker}

{price_line}

ملاحظة:
المستويات الدقيقة تحتاج ربط مصدر فني/شموع لاحقًا.
حاليًا استخدم زر التقرير السريع لعرض المتاح من السعر والأخبار.

القرار:
🟡 مراقبة فقط حتى يظهر كسر مستوى أو خبر/فوليوم واضح.
"""


def _normalize_for_match(value):
    fn = _runtime.get("normalize_common_ticker_func")
    try:
        if fn:
            return fn(value)
    except Exception:
        pass
    return normalize_ticker(value)


def _item_matches_ticker(item, ticker):
    ticker = normalize_ticker(ticker)
    fields = [
        str(item.get("ticker", "")),
        str(item.get("official_ticker", "")),
        str(item.get("title", "")),
        str(item.get("source", "")),
    ]

    direct = [_normalize_for_match(fields[0]), _normalize_for_match(fields[1])]
    if ticker in direct:
        return True

    text = " ".join(fields).upper()
    return re.search(rf"\b{re.escape(ticker)}\b", text) is not None


def _item_age_text(item):
    published = item.get("published_at")
    if not published:
        return "وقت غير معروف"
    try:
        if isinstance(published, str):
            published = datetime.fromisoformat(published)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        minutes = int((datetime.now(timezone.utc) - published).total_seconds() / 60)
        if minutes < 1:
            return "الآن"
        if minutes < 60:
            return f"قبل {minutes} دقيقة"
        return f"قبل {minutes // 60} ساعة"
    except Exception:
        return "وقت غير معروف"


def _collect_items_safe():
    collect = _runtime.get("collect_all_news_func")
    if not collect:
        return []
    try:
        items = collect()
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"collect items from buttons error: {e}", flush=True)
        return []


def _sec_headers():
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    }


def _load_sec_ticker_cache():
    """
    تحميل خريطة SEC الرسمية: ticker -> CIK.
    هذه أفضل من الاعتماد على آخر دورة أخبار، لذلك زر SEC يعطي نتيجة مباشرة للسهم.
    """
    global _SEC_TICKER_CACHE
    if _SEC_TICKER_CACHE is not None:
        return _SEC_TICKER_CACHE

    _SEC_TICKER_CACHE = {}
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_sec_headers(),
            timeout=15,
        )
        if r.status_code != 200:
            print(f"SEC ticker cache status error: {r.status_code}", flush=True)
            return _SEC_TICKER_CACHE

        data = r.json()
        for _, row in data.items():
            ticker = normalize_ticker(row.get("ticker", ""))
            cik = str(int(row.get("cik_str"))).zfill(10)
            title = str(row.get("title", "")).strip()
            if ticker and cik:
                _SEC_TICKER_CACHE[ticker] = {"cik": cik, "title": title}

        print(f"SEC ticker cache loaded in buttons: {len(_SEC_TICKER_CACHE)} tickers", flush=True)
    except Exception as e:
        print(f"SEC ticker cache error in buttons: {e}", flush=True)

    return _SEC_TICKER_CACHE


def _get_sec_company_for_ticker(ticker):
    ticker = normalize_ticker(ticker)
    return _load_sec_ticker_cache().get(ticker)


def _get_sec_submissions_for_ticker(ticker):
    company = _get_sec_company_for_ticker(ticker)
    if not company:
        return None, []

    cik = company.get("cik")
    try:
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=_sec_headers(),
            timeout=15,
        )
        if r.status_code != 200:
            print(f"SEC submissions status error {ticker}: {r.status_code}", flush=True)
            return company, []

        data = r.json()
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", []) or []
        filing_dates = recent.get("filingDate", []) or []
        report_dates = recent.get("reportDate", []) or []
        accessions = recent.get("accessionNumber", []) or []
        docs = recent.get("primaryDocument", []) or []
        descriptions = recent.get("primaryDocDescription", []) or []

        filings = []
        for i, form in enumerate(forms[:40]):
            form = str(form or "").strip().upper()
            accession = str(accessions[i] if i < len(accessions) else "").strip()
            accession_no_dash = accession.replace("-", "")
            doc = str(docs[i] if i < len(docs) else "").strip()
            url = ""
            if accession and doc:
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dash}/{doc}"
            filings.append({
                "form": form,
                "filing_date": str(filing_dates[i] if i < len(filing_dates) else ""),
                "report_date": str(report_dates[i] if i < len(report_dates) else ""),
                "description": str(descriptions[i] if i < len(descriptions) else "").strip(),
                "url": url,
            })
        return company, filings
    except Exception as e:
        print(f"SEC submissions error {ticker}: {e}", flush=True)
        return company, []


def build_sec_text(ticker, important_only=False):
    ticker = normalize_ticker(ticker)
    important_forms = {
        "424B5", "424B3", "424B4", "S-1", "S-3", "F-1", "F-3",
        "EFFECT", "FWP", "4", "SC 13D", "SC 13G", "DEF 14A", "PRE 14A",
        "NT 10-Q", "NT 10-K", "8-K", "10-Q", "10-K"
    }

    # v5.9.5.1: البحث المباشر من SEC حسب ticker/CIK بدل الاعتماد على آخر دورة أخبار فقط.
    company, filings = _get_sec_submissions_for_ticker(ticker)

    if company:
        if important_only:
            filings = [f for f in filings if f.get("form") in important_forms]

        if not filings:
            return f"""📄 SEC — {ticker}

الشركة: {company.get('title', ticker)}
CIK: {company.get('cik', 'غير معروف')}

لا توجد إفصاحات SEC مهمة مطابقة ضمن آخر الإفصاحات الأخيرة."""

        title = company.get("title", ticker)
        cik = company.get("cik", "")
        lines = [
            f"📄 SEC — {ticker}",
            f"الشركة: {title}",
            f"CIK: {cik}",
            "",
            "آخر الإفصاحات:" if not important_only else "الإفصاحات المهمة:",
        ]

        for f in filings[:7]:
            form = f.get("form", "")
            filing_date = f.get("filing_date", "") or "تاريخ غير معروف"
            report_date = f.get("report_date", "")
            desc = f.get("description", "")
            url = f.get("url", "")

            note = ""
            if form in {"424B5", "424B3", "424B4", "S-1", "S-3", "F-1", "F-3", "EFFECT", "FWP"}:
                note = "\n⚠️ ملاحظة: راقب احتمال طرح/تخفيف أو تفعيل تسجيل حسب تفاصيل الإفصاح."
            elif form == "4":
                note = "\nℹ️ ملاحظة: Form 4 يحتاج تمييز شراء داخلي فعلي من بيع/منح." 
            elif form in {"10-Q", "10-K", "8-K"}:
                note = "\nℹ️ ملاحظة: راقب البنود المهمة داخل الإفصاح."

            item_text = f"• {form} | تاريخ الإيداع: {filing_date}"
            if report_date:
                item_text += f" | فترة التقرير: {report_date}"
            if desc:
                item_text += f"\n{desc}"
            if url:
                item_text += f"\n{url}"
            item_text += note
            lines.append(item_text)

        return "\n\n".join(lines)

    # fallback: لو لم نجد ticker في SEC mapping، نستخدم آخر بيانات البوت الحالية.
    items = _collect_items_safe()
    sec_items = []

    for item in items:
        source = str(item.get("source", ""))
        if not source.upper().startswith("SEC"):
            continue
        if not _item_matches_ticker(item, ticker):
            continue
        form = str(item.get("sec_form", "") or source.replace("SEC", "")).strip().upper()
        if important_only and form not in important_forms:
            continue
        sec_items.append(item)

    if not sec_items:
        return f"📄 SEC — {ticker}\n\nلم أجد السهم في خريطة SEC الرسمية، ولا توجد إفصاحات مطابقة ضمن بيانات البوت الحالية."

    lines = [f"📄 SEC — {ticker}", ""]
    for item in sec_items[:5]:
        form = str(item.get("sec_form", "") or item.get("source", "")).replace("SEC", "").strip()
        title = str(item.get("title", "")).strip()
        age = _item_age_text(item)
        url = str(item.get("url", "")).strip()
        lines.append(f"• {form} | {age}\n{title}\n{url}")

    return "\n\n".join(lines)

def build_news_summary_text(ticker):
    ticker = normalize_ticker(ticker)
    items = _collect_items_safe()
    matched = []

    for item in items:
        if _item_matches_ticker(item, ticker):
            matched.append(item)

    if not matched:
        return f"📰 أخبار {ticker}\n\nلا توجد أخبار مطابقة حاليًا ضمن البيانات الحالية."

    lines = [f"📰 مختصر أخبار {ticker}", ""]
    for item in matched[:5]:
        source = str(item.get("source", "غير معروف"))
        title = str(item.get("title", "")).strip()
        age = _item_age_text(item)
        lines.append(f"• {source} | {age}\n{title}")
    return "\n\n".join(lines)


# =========================
# Handlers
# =========================

def handle_text_message(message):
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not _allowed_chat(chat_id):
        print(f"Unauthorized chat ignored: {chat_id}", flush=True)
        return

    clean_text = str(text or "").strip()

    # أوامر فرص اليوم — مستقلة عن قائمة المراقبة الدائمة
    parts = clean_text.split()
    command = parts[0].lower() if parts else ""

    if command == "/today_add":
        if len(parts) < 2:
            send_message(chat_id, "استخدم الأمر بهذا الشكل:\n/today_add SYMBOL")
            return
        ticker = normalize_ticker(parts[1])
        ok, msg = add_daily_opportunity(ticker)
        send_message(chat_id, ("✅ " if ok else "⚠️ ") + msg + "\n\n" + format_daily_opportunities_list())
        return

    if command == "/today_remove":
        if len(parts) < 2:
            send_message(chat_id, "استخدم الأمر بهذا الشكل:\n/today_remove SYMBOL")
            return
        ticker = normalize_ticker(parts[1])
        ok, msg = remove_daily_opportunity(ticker)
        send_message(chat_id, ("✅ " if ok else "⚠️ ") + msg + "\n\n" + format_daily_opportunities_list())
        return

    if command == "/today_list":
        send_message(chat_id, format_daily_opportunities_list())
        return

    if command == "/today_clear":
        ok, msg = clear_daily_opportunities()
        send_message(chat_id, ("✅ " if ok else "⚠️ ") + msg + "\n\n" + format_daily_opportunities_list())
        return

    # أوامر مباشرة لعرض القائمة
    if clean_text.lower() in ["/list", "list"] or clean_text in ["القائمة", "قائمة", "عرض القائمة"]:
        send_message(chat_id, format_watchlist())
        return

    # تجاهل أي نص ليس رمز سهم
    if not is_ticker_message(clean_text):
        return

    ticker = normalize_ticker(clean_text)
    exists = "موجود في قائمة المراقبة" if is_in_watchlist(ticker) else "غير موجود في قائمة المراقبة"

    msg = f"""🏷️ السهم: {ticker}

الحالة: {exists}

اختر الإجراء المطلوب:"""

    send_message(chat_id, msg, reply_markup=main_keyboard(ticker))


def handle_callback(callback):
    callback_id = callback.get("id")
    message = callback.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    data = callback.get("data", "")

    if not _allowed_chat(chat_id):
        answer_callback(callback_id, "غير مصرح")
        return

    answer_callback(callback_id)

    try:
        action, ticker = data.split("|", 1)
    except Exception:
        return

    ticker = normalize_ticker(ticker)

    if action == "cancel":
        edit_message(chat_id, message_id, "تم الإلغاء.")
        return

    if action == "back":
        msg = f"""🏷️ السهم: {ticker}

اختر الإجراء المطلوب:"""
        edit_message(chat_id, message_id, msg, reply_markup=main_keyboard(ticker))
        return

    if action == "list":
        edit_message(chat_id, message_id, format_watchlist(), reply_markup=back_keyboard(ticker))
        return

    # Main v5.9.5 buttons
    if action == "reason":
        edit_message(chat_id, message_id, build_reason_text(ticker), reply_markup=back_keyboard(ticker))
        return

    if action == "report_menu":
        edit_message(chat_id, message_id, f"📊 تقرير {ticker}\n\nاختر نوع التقرير:", reply_markup=report_keyboard(ticker))
        return

    if action == "news_menu":
        edit_message(chat_id, message_id, f"📰 أخبار {ticker}\n\nاختر نوع العرض:", reply_markup=news_keyboard(ticker))
        return

    if action == "sec_menu":
        edit_message(chat_id, message_id, f"📄 SEC — {ticker}\n\nاختر نوع الإفصاحات:", reply_markup=sec_keyboard(ticker))
        return

    if action == "watch_menu":
        exists = "موجود في القائمة" if is_in_watchlist(ticker) else "غير موجود في القائمة"
        edit_message(chat_id, message_id, f"⭐ مراقبة {ticker}\n\nالحالة: {exists}", reply_markup=watch_keyboard(ticker))
        return

    if action == "mute_menu":
        edit_message(chat_id, message_id, f"🔕 تجاهل {ticker}\n\nاختر مدة التجاهل:", reply_markup=mute_keyboard(ticker))
        return

    # Daily Opportunities actions
    if action == "daily_menu":
        exists = "موجود في فرص اليوم" if is_in_daily_opportunities(ticker) else "غير موجود في فرص اليوم"
        msg = f"""🔥 فرص اليوم — {ticker}

الحالة: {exists}

هذه القائمة مستقلة عن قائمة المراقبة الدائمة.
لا تضف السهم هنا إلا بعد فلتر Investing Pro+ وفحص الشرعية."""
        edit_message(chat_id, message_id, msg, reply_markup=daily_opportunities_keyboard(ticker))
        return

    if action == "daily_list":
        edit_message(chat_id, message_id, format_daily_opportunities_list(), reply_markup=back_keyboard(ticker))
        return

    if action == "daily_sharia":
        result = check_sharia(ticker)
        edit_message(chat_id, message_id, result.get("message", "تعذر فحص الشرعية."), reply_markup=daily_opportunities_keyboard(ticker))
        return

    if action == "daily_add":
        result = check_sharia(ticker)
        status = result.get("status")

        if status == "non_compliant":
            msg = f"""❌ لا يمكن إضافة {ticker} إلى فرص اليوم.

السبب:
السهم غير متوافق حسب الفحص المحفوظ.

لم يتم إضافة السهم."""
            edit_message(chat_id, message_id, msg, reply_markup=back_keyboard(ticker))
            return

        if status == "compliant":
            msg = f"""✅ {ticker} متوافق حسب الفحص المحفوظ.

هل تريد إضافته إلى فرص اليوم؟

ملاحظة: لن تتم إضافته إلى قائمة المراقبة الدائمة."""
            edit_message(chat_id, message_id, msg, reply_markup=confirm_daily_add_keyboard(ticker))
            return

        msg = f"""⚠️ شرعية {ticker} غير محسومة.

حسب قاعدة فرص اليوم، لا نضيف السهم لهذا القسم إلا بعد فحص الشرعية.
استخدم زر فحص الشرعية أو افحصه خارجيًا قبل الإضافة."""
        edit_message(chat_id, message_id, msg, reply_markup=daily_opportunities_keyboard(ticker))
        return

    if action == "confirm_daily_add":
        ok, msg = add_daily_opportunity(ticker)
        icon = "✅" if ok else "⚠️"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\n{format_daily_opportunities_list()}", reply_markup=back_keyboard(ticker))
        return

    if action == "daily_remove":
        ok, msg = remove_daily_opportunity(ticker)
        icon = "✅" if ok else "⚠️"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\n{format_daily_opportunities_list()}", reply_markup=back_keyboard(ticker))
        return

    # Report sub-actions
    if action == "report":
        text = build_quick_report(
            ticker,
            get_stock_price_func=_runtime.get("get_stock_price_func"),
            collect_all_news_func=_runtime.get("collect_all_news_func"),
        )
        edit_message(chat_id, message_id, text, reply_markup=back_keyboard(ticker))
        return

    if action == "price":
        edit_message(chat_id, message_id, get_price_text(ticker), reply_markup=back_keyboard(ticker))
        return

    if action == "levels":
        edit_message(chat_id, message_id, build_levels_text(ticker), reply_markup=back_keyboard(ticker))
        return

    # News sub-actions
    if action == "news":
        text = format_latest_news_for_ticker(
            ticker,
            collect_all_news_func=_runtime.get("collect_all_news_func"),
            limit=5
        )
        edit_message(chat_id, message_id, text, reply_markup=back_keyboard(ticker))
        return

    if action == "news_summary":
        edit_message(chat_id, message_id, build_news_summary_text(ticker), reply_markup=back_keyboard(ticker))
        return

    # SEC sub-actions
    if action == "sec_latest":
        edit_message(chat_id, message_id, build_sec_text(ticker, important_only=False), reply_markup=back_keyboard(ticker))
        return

    if action == "sec_important":
        edit_message(chat_id, message_id, build_sec_text(ticker, important_only=True), reply_markup=back_keyboard(ticker))
        return

    # Existing watchlist actions preserved
    if action == "sharia":
        result = check_sharia(ticker)
        edit_message(chat_id, message_id, result.get("message", "تعذر فحص الشرعية."), reply_markup=back_keyboard(ticker))
        return

    if action == "add":
        result = check_sharia(ticker)

        if result.get("status") == "compliant":
            msg = f"""✅ السهم {ticker} متوافق حسب الفحص المحفوظ.

هل تريد إضافته إلى قائمة المراقبة؟"""
            edit_message(chat_id, message_id, msg, reply_markup=confirm_add_keyboard(ticker))
            return

        if result.get("status") == "non_compliant":
            msg = f"""❌ لا يمكن إضافة {ticker} إلى قائمة المراقبة.

السبب:
السهم غير متوافق حسب الفحص المحفوظ.

لم يتم إضافة السهم."""
            edit_message(chat_id, message_id, msg, reply_markup=back_keyboard(ticker))
            return

        # unknown
        msg = f"""⚠️ شرعية {ticker} غير محسومة.

لا يمكن إضافته إضافة دائمة الآن.
يمكن إضافته مؤقتًا فقط بموافقتك الصريحة.

هل تريد إضافته مؤقتًا للمراقبة؟"""
        edit_message(chat_id, message_id, msg, reply_markup=temporary_add_keyboard(ticker))
        return

    if action == "confirm_add":
        ok, msg = add_ticker(ticker)
        icon = "✅" if ok else "⚠️"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\n{format_watchlist()}", reply_markup=back_keyboard(ticker))
        return

    if action == "temp_add":
        note = {
            "sharia": "غير محسوم - إضافة مؤقتة بموافقة المستخدم",
            "purification": "غير متوفر",
        }
        ok, msg = add_ticker(ticker, note=note)
        icon = "⚠️" if ok else "❌"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\nملاحظة: الإضافة مؤقتة حتى اكتمال فحص الشرعية.\n\n{format_watchlist()}", reply_markup=back_keyboard(ticker))
        return

    if action == "remove":
        ok, msg = remove_ticker(ticker)
        icon = "✅" if ok else "⚠️"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\n{format_watchlist()}", reply_markup=back_keyboard(ticker))
        return

    # Mute sub-actions
    if action == "mute_1h":
        until = set_mute(ticker, 60, "ساعة")
        edit_message(
            chat_id,
            message_id,
            f"🔕 تم تسجيل تجاهل {ticker} لمدة ساعة.\n\nينتهي تقريبًا: {until.strftime('%H:%M UTC')}\n\nملاحظة: إذا أردت أن يمنع هذا تنبيهات الملف الرئيسي أيضًا، يجب ربط mute في main.py لاحقًا.",
            reply_markup=back_keyboard(ticker)
        )
        return

    if action == "mute_today":
        until = set_mute(ticker, 18 * 60, "اليوم")
        edit_message(
            chat_id,
            message_id,
            f"🔕 تم تسجيل تجاهل {ticker} لبقية اليوم.\n\nملاحظة: إذا أردت أن يمنع هذا تنبيهات الملف الرئيسي أيضًا، يجب ربط mute في main.py لاحقًا.",
            reply_markup=back_keyboard(ticker)
        )
        return


def polling_loop():
    print("Telegram buttons polling loop started", flush=True)

    while _runtime.get("running"):
        try:
            payload = {
                "timeout": 15,
                "allowed_updates": ["message", "callback_query"],
            }

            if _runtime.get("offset") is not None:
                payload["offset"] = _runtime["offset"]

            r = requests.get(
                _api_url("getUpdates"),
                params=payload,
                timeout=REQUEST_TIMEOUT_SECONDS + 5
            )

            if r.status_code != 200:
                print(f"getUpdates error: {r.status_code} | {r.text[:300]}", flush=True)
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            data = r.json()

            if not data.get("ok"):
                print(f"getUpdates not ok: {data}", flush=True)
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            for update in data.get("result", []):
                _runtime["offset"] = update.get("update_id", 0) + 1

                try:
                    if "message" in update:
                        handle_text_message(update["message"])
                    elif "callback_query" in update:
                        handle_callback(update["callback_query"])
                except Exception as e:
                    print(f"update handling error: {e}", flush=True)

        except Exception as e:
            print(f"polling_loop error: {e}", flush=True)
            time.sleep(POLL_INTERVAL_SECONDS)


def start_buttons_polling(
    bot_token,
    chat_ids,
    get_stock_price_func=None,
    collect_all_news_func=None,
    analyze_with_ai_func=None,
    normalize_common_ticker_func=None,
    send_telegram_func=None,
):
    if not bot_token:
        print("Buttons polling skipped: BOT_TOKEN missing", flush=True)
        return False

    if _runtime.get("running"):
        print("Buttons polling already running", flush=True)
        return True

    _runtime["bot_token"] = bot_token
    _runtime["chat_ids"] = chat_ids or []
    _runtime["get_stock_price_func"] = get_stock_price_func
    _runtime["collect_all_news_func"] = collect_all_news_func
    _runtime["analyze_with_ai_func"] = analyze_with_ai_func
    _runtime["normalize_common_ticker_func"] = normalize_common_ticker_func
    _runtime["send_telegram_func"] = send_telegram_func
    _runtime["running"] = True

    t = threading.Thread(target=polling_loop, daemon=True)
    t.start()

    return True
