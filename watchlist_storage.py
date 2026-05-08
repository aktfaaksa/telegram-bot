# AlphaBot Pro v5.9
# watchlist_storage.py
# تخزين قائمة المراقبة في ملف مستقل وخفيف

import json
import os
from datetime import datetime, timezone

WATCHLIST_FILE = os.getenv("WATCHLIST_FILE", "watchlist.json")

DEFAULT_WATCHLIST = [
    "CRMD",
    "CRML",
    "UAMY",
    "ANNA",
    "ELAB",
    "TMC",
    "RDW",
    "RKLB",
    "SOUN",
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_ticker(ticker):
    if not ticker:
        return ""
    ticker = str(ticker).strip().upper()
    ticker = ticker.replace("$", "")
    return "".join(ch for ch in ticker if ch.isalnum() or ch in [".", "-"])[:12]


def default_data():
    return {
        "version": "v5.9",
        "updated_at": _now_iso(),
        "watchlist": DEFAULT_WATCHLIST[:],
        "notes": {
            "RKLB": {
                "sharia": "متوافق حسب فلتر بنك البلاد وبنك الراجحي",
                "purification": "2.54%",
            },
            "SOUN": {
                "sharia": "متوافق حسب فلتر بنك البلاد وبنك الراجحي",
                "purification": "4.34%",
            },
        },
    }


def load_watchlist_data():
    if not os.path.exists(WATCHLIST_FILE):
        data = default_data()
        save_watchlist_data(data)
        return data

    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("watchlist data is not dict")

        data.setdefault("version", "v5.9")
        data.setdefault("updated_at", _now_iso())
        data.setdefault("watchlist", DEFAULT_WATCHLIST[:])
        data.setdefault("notes", {})

        cleaned = []
        for t in data.get("watchlist", []):
            nt = normalize_ticker(t)
            if nt and nt not in cleaned:
                cleaned.append(nt)

        data["watchlist"] = cleaned
        return data

    except Exception as e:
        print(f"load_watchlist_data error: {e}", flush=True)
        data = default_data()
        save_watchlist_data(data)
        return data


def save_watchlist_data(data):
    try:
        data["updated_at"] = _now_iso()

        tmp = WATCHLIST_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp, WATCHLIST_FILE)
        return True

    except Exception as e:
        print(f"save_watchlist_data error: {e}", flush=True)
        return False


def get_watchlist():
    data = load_watchlist_data()
    return data.get("watchlist", [])


def is_in_watchlist(ticker):
    ticker = normalize_ticker(ticker)
    return ticker in get_watchlist()


def add_ticker(ticker, note=None):
    ticker = normalize_ticker(ticker)
    if not ticker:
        return False, "رمز السهم غير صحيح"

    data = load_watchlist_data()
    wl = data.setdefault("watchlist", [])

    if ticker in wl:
        return True, f"{ticker} موجود مسبقًا في قائمة المراقبة"

    wl.append(ticker)

    if note:
        data.setdefault("notes", {})[ticker] = note

    ok = save_watchlist_data(data)
    if not ok:
        return False, "تعذر حفظ قائمة المراقبة"

    return True, f"تمت إضافة {ticker} إلى قائمة المراقبة"


def remove_ticker(ticker):
    ticker = normalize_ticker(ticker)
    if not ticker:
        return False, "رمز السهم غير صحيح"

    data = load_watchlist_data()
    wl = data.setdefault("watchlist", [])

    if ticker not in wl:
        return False, f"{ticker} غير موجود في قائمة المراقبة"

    data["watchlist"] = [x for x in wl if x != ticker]

    ok = save_watchlist_data(data)
    if not ok:
        return False, "تعذر حفظ قائمة المراقبة"

    return True, f"تم حذف {ticker} من قائمة المراقبة"


def format_watchlist():
    wl = get_watchlist()

    if not wl:
        return "📋 قائمة المراقبة فارغة."

    lines = ["📋 قائمة المراقبة الحالية:", ""]
    for i, ticker in enumerate(wl, 1):
        lines.append(f"{i}. {ticker}")

    return "\n".join(lines)
