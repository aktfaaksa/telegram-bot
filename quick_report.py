# AlphaBot Pro v5.9.2
# quick_report.py
# تقرير سريع وخفيف للسهم بدون جلب أخبار ثقيلة

from watchlist_storage import normalize_ticker, is_in_watchlist
from sharia_checker import check_sharia


def _format_price(price):
    if price is None:
        return "غير متوفر"

    try:
        price = float(price)
        if price < 0.01:
            return f"${price:.6f}"
        return f"${price:.2f}"
    except Exception:
        return "غير متوفر"


def build_quick_report(
    ticker,
    get_stock_price_func=None,
    collect_all_news_func=None,
):
    ticker = normalize_ticker(ticker)

    if not ticker:
        return "رمز السهم غير صحيح."

    price = None

    if get_stock_price_func:
        try:
            price = get_stock_price_func(ticker)
        except Exception as e:
            print(f"quick_report price error {ticker}: {e}", flush=True)

    sharia = check_sharia(ticker)
    in_wl = is_in_watchlist(ticker)

    status = sharia.get("status", "unknown")
    label = sharia.get("label", "غير معروف")
    source = sharia.get("source", "غير متوفر")
    purification = sharia.get("purification", "غير متوفر")
    note = sharia.get("note", "")

    if status == "compliant":
        sharia_icon = "✅"
    elif status == "non_compliant":
        sharia_icon = "❌"
    elif status == "unknown":
        sharia_icon = "⚠️"
    else:
        sharia_icon = "ℹ️"

    report = f"""📊 تقرير سريع: {ticker}

💵 السعر الحالي: {_format_price(price)}
📋 حالة القائمة: {"موجود في قائمة المراقبة" if in_wl else "غير موجود في قائمة المراقبة"}

🕌 الشرعية:
{sharia_icon} الحالة: {label}
المصدر: {source}
نسبة التطهير: {purification}

📌 ملاحظة:
{note or "هذا تقرير سريع للمراقبة فقط، وليس توصية شراء أو بيع."}

📰 لعرض الأخبار المترجمة:
اضغط زر "آخر الأخبار" من خيارات السهم.
"""

    return report
