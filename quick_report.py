# AlphaBot Pro v5.9
# quick_report.py
# تقرير سريع لسهم محدد

from watchlist_storage import normalize_ticker, is_in_watchlist
from sharia_checker import check_sharia
from stock_news import format_latest_news_for_ticker


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

    report = f"""📊 تقرير سريع: {ticker}

💵 السعر الحالي: {_format_price(price)}
📋 حالة القائمة: {"موجود في قائمة المراقبة" if in_wl else "غير موجود في قائمة المراقبة"}

🕌 الشرعية:
الحالة: {sharia.get("label", "غير معروف")}
المصدر: {sharia.get("source", "غير متوفر")}
نسبة التطهير: {sharia.get("purification", "غير متوفر")}

📌 ملاحظة:
هذا تقرير سريع للمراقبة فقط، وليس توصية شراء أو بيع.
"""

    # نضيف أحدث خبر واحد فقط حتى لا تصير الرسالة طويلة
    try:
        news_text = format_latest_news_for_ticker(
            ticker,
            collect_all_news_func=collect_all_news_func,
            limit=1
        )
        report += "\n\n" + news_text
    except Exception as e:
        print(f"quick_report news error {ticker}: {e}", flush=True)

    return report
