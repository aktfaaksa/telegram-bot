# AlphaBot Pro v5.9.1
# stock_news.py
# آخر الأخبار لسهم محدد عبر Finnhub Company News مع fallback خفيف

import os
import requests
from datetime import datetime, timezone, timedelta

from watchlist_storage import normalize_ticker


FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


def _clean(text):
    if not text:
        return ""
    return " ".join(str(text).split())


def _age_text(dt):
    if not dt:
        return "وقت غير معروف"

    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

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


def _date_range(days=7):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days)
    return start.isoformat(), today.isoformat()


def fetch_finnhub_company_news(ticker, days=7, limit=5):
    """
    جلب أخبار السهم مباشرة من Finnhub Company News.
    هذا أسرع وأدق من جمع كل أخبار السوق ثم البحث داخلها.
    """
    ticker = normalize_ticker(ticker)

    if not ticker:
        return []

    if not FINNHUB_API_KEY:
        print("Finnhub company news skipped: FINNHUB_API_KEY missing", flush=True)
        return []

    start_date, end_date = _date_range(days)

    try:
        url = "https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": ticker,
            "from": start_date,
            "to": end_date,
            "token": FINNHUB_API_KEY,
        }

        r = requests.get(url, params=params, timeout=12)

        if r.status_code != 200:
            print(f"Finnhub company news error {ticker}: {r.status_code} | {r.text[:200]}", flush=True)
            return []

        data = r.json()

        if not isinstance(data, list):
            return []

        items = []

        for n in data[:limit]:
            title = _clean(n.get("headline"))
            url = _clean(n.get("url"))
            source = _clean(n.get("source")) or "Finnhub"
            summary = _clean(n.get("summary"))
            ts = n.get("datetime")

            published_at = None
            if ts:
                try:
                    published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                except Exception:
                    published_at = None

            if not title:
                continue

            items.append({
                "ticker": ticker,
                "title": title,
                "url": url,
                "source": source,
                "summary": summary,
                "published_at": published_at,
            })

        return items

    except Exception as e:
        print(f"fetch_finnhub_company_news error {ticker}: {e}", flush=True)
        return []


def format_company_news(ticker, days=7, limit=5):
    ticker = normalize_ticker(ticker)

    if not ticker:
        return "رمز السهم غير صحيح."

    items = fetch_finnhub_company_news(ticker, days=days, limit=limit)

    if not items:
        return f"""📰 آخر الأخبار لـ {ticker}:

لا توجد أخبار حديثة واضحة لهذا السهم من Finnhub Company News خلال آخر {days} أيام.

ملاحظة:
هذا لا يعني عدم وجود أخبار نهائيًا، بل لا توجد نتيجة واضحة من مصدر Finnhub Company News حاليًا."""

    lines = [f"📰 آخر الأخبار لـ {ticker} خلال آخر {days} أيام:", ""]

    for i, item in enumerate(items, 1):
        title = _clean(item.get("title"))
        source = _clean(item.get("source"))
        url = _clean(item.get("url"))
        summary = _clean(item.get("summary"))
        age = _age_text(item.get("published_at"))

        lines.append(f"{i}. {title}")
        lines.append(f"المصدر: {source}")
        lines.append(f"الوقت: {age}")

        if summary:
            short_summary = summary[:220].strip()
            if len(summary) > 220:
                short_summary += "..."
            lines.append(f"الملخص: {short_summary}")

        if url:
            lines.append(f"الرابط: {url}")

        lines.append("")

    return "\n".join(lines).strip()


def format_latest_news_for_ticker(ticker, collect_all_news_func=None, limit=5):
    """
    الدالة الرئيسية التي يستخدمها زر آخر الأخبار.
    في v5.9.1 نعتمد أولًا على Finnhub Company News.
    collect_all_news_func أبقيناه للتوافق فقط ولا نعتمد عليه افتراضيًا.
    """
    ticker = normalize_ticker(ticker)

    if not ticker:
        return "رمز السهم غير صحيح."

    return format_company_news(ticker, days=7, limit=limit)