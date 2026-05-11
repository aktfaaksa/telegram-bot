# AlphaBot Pro v5.9.5
# telegram_buttons.py
# واجهة أزرار مختصرة: 6 أزرار رئيسية + قوائم فرعية منظمة
# متوافق مع AlphaBot v5.9.5 Scheduled Reports + Smart Alerts
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
MAX_TELEGRAM_TEXT = 3900

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
    v5.9.5: ستة أزرار رئيسية فقط.
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


def build_reason_text(ticker):
    ticker = normalize_ticker(ticker)
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


def build_sec_text(ticker, important_only=False):
    ticker = normalize_ticker(ticker)
    items = _collect_items_safe()
    sec_items = []

    important_forms = [
        "424B5", "424B3", "424B4", "S-1", "S-3", "F-1", "F-3",
        "EFFECT", "FWP", "4", "SC 13D", "SC 13G", "DEF 14A", "PRE 14A",
        "NT 10-Q", "NT 10-K", "8-K"
    ]

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
        return f"📄 SEC — {ticker}\n\nلا توجد إفصاحات SEC مطابقة الآن ضمن البيانات الحالية."

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
