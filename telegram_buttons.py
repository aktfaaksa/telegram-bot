# AlphaBot Pro v5.9.2
# telegram_buttons.py
# استقبال رمز السهم وإظهار أزرار تفاعلية Inline Buttons
#
# يعمل بنظام getUpdates داخل Thread مستقل
# حتى لا يؤثر أي خطأ هنا على دورة الأخبار الرئيسية.

import json
import re
import threading
import time
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


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _post("sendMessage", payload)


def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
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
    ticker = normalize_ticker(ticker)

    return {
        "inline_keyboard": [
            [
                {"text": "🔎 فحص الشرعية", "callback_data": f"sharia|{ticker}"},
                {"text": "➕ إضافة للمراقبة", "callback_data": f"add|{ticker}"},
            ],
            [
                {"text": "❌ حذف من المراقبة", "callback_data": f"remove|{ticker}"},
                {"text": "📰 آخر الأخبار", "callback_data": f"news|{ticker}"},
            ],
            [
                {"text": "📊 تقرير سريع", "callback_data": f"report|{ticker}"},
                {"text": "📋 عرض القائمة", "callback_data": "list|ALL"},
            ],
            [
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


def back_keyboard(ticker):
    ticker = normalize_ticker(ticker)
    return {
        "inline_keyboard": [
            [
                {"text": "⬅️ رجوع لخيارات السهم", "callback_data": f"back|{ticker}"},
                {"text": "إلغاء", "callback_data": "cancel|ALL"},
            ]
        ]
    }


def handle_text_message(message):
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not _allowed_chat(chat_id):
        print(f"Unauthorized chat ignored: {chat_id}", flush=True)
        return

    clean_text = str(text or "").strip()

    # v5.9.2: أوامر مباشرة لعرض القائمة
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
        edit_message(chat_id, message_id, format_watchlist())
        return

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
        edit_message(chat_id, message_id, f"{icon} {msg}\n\n{format_watchlist()}")
        return

    if action == "temp_add":
        note = {
            "sharia": "غير محسوم - إضافة مؤقتة بموافقة المستخدم",
            "purification": "غير متوفر",
        }
        ok, msg = add_ticker(ticker, note=note)
        icon = "⚠️" if ok else "❌"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\nملاحظة: الإضافة مؤقتة حتى اكتمال فحص الشرعية.\n\n{format_watchlist()}")
        return

    if action == "remove":
        ok, msg = remove_ticker(ticker)
        icon = "✅" if ok else "⚠️"
        edit_message(chat_id, message_id, f"{icon} {msg}\n\n{format_watchlist()}")
        return

    if action == "news":
        text = format_latest_news_for_ticker(
            ticker,
            collect_all_news_func=_runtime.get("collect_all_news_func"),
            limit=5
        )
        edit_message(chat_id, message_id, text, reply_markup=back_keyboard(ticker))
        return

    if action == "report":
        text = build_quick_report(
            ticker,
            get_stock_price_func=_runtime.get("get_stock_price_func"),
            collect_all_news_func=_runtime.get("collect_all_news_func"),
        )
        edit_message(chat_id, message_id, text, reply_markup=back_keyboard(ticker))
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
