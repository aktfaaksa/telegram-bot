# AlphaBot Pro v5.9
# stock_news.py
# آخر الأخبار لسهم محدد بدون التأثير على دورة الأخبار الرئيسية

from datetime import datetime, timezone
from watchlist_storage import normalize_ticker


def _clean(text):
    if not text:
        return ""
    return " ".join(str(text).split())


def _age_text(dt):
    if not dt:
        return "وقت غير معروف"

    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        minutes = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)

        if minutes < 1:
            return "الآن"
        if minutes < 60:
            return f"قبل {minutes} دقيقة"

        hours = minutes // 60
        if hours < 24:
            return f"قبل {hours} ساعة"

        days = hours // 24
        return f"قبل {days} يوم"
    except Exception:
        return "وقت غير معروف"


def format_latest_news_for_ticker(ticker, collect_all_news_func=None, limit=5):
    ticker = normalize_ticker(ticker)

    if not ticker:
        return "رمز السهم غير صحيح."

    if not collect_all_news_func:
        return f"📰 آخر الأخبار لـ {ticker}:\n\nخدمة الأخبار غير متاحة حاليًا."

    try:
        items = collect_all_news_func()
    except Exception as e:
        print(f"format_latest_news_for_ticker collect error: {e}", flush=True)
        return f"📰 آخر الأخبار لـ {ticker}:\n\nتعذر جلب الأخبار الآن."

    matched = []

    for item in items:
        item_ticker = normalize_ticker(
            item.get("official_ticker")
            or item.get("ticker")
            or ""
        )

        title = _clean(item.get("title"))
        raw = _clean(item.get("raw"))
        combined = f" {title} {raw} ".upper()

        if item_ticker == ticker or f" {ticker} " in combined or f"NASDAQ: {ticker}" in combined or f"NYSE: {ticker}" in combined:
            matched.append(item)

    matched = matched[:limit]

    if not matched:
        return f"""📰 آخر الأخبار لـ {ticker}:

لا توجد أخبار حديثة واضحة لهذا السهم من مصادر البوت الحالية.

ملاحظة:
هذا لا يعني عدم وجود أخبار نهائيًا، بل لا توجد نتيجة حديثة داخل مصادر AlphaBot الحالية."""

    lines = [f"📰 آخر الأخبار لـ {ticker}:", ""]

    for i, item in enumerate(matched, 1):
        source = _clean(item.get("source"))
        title = _clean(item.get("title"))
        url = _clean(item.get("url"))
        age = _age_text(item.get("published_at"))

        lines.append(f"{i}. {title}")
        lines.append(f"المصدر: {source}")
        lines.append(f"الوقت: {age}")
        if url:
            lines.append(f"الرابط: {url}")
        lines.append("")

    return "\n".join(lines).strip()
