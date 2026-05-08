# AlphaBot Pro v5.9.3
# stock_news.py
# آخر الأخبار لسهم محدد عبر Finnhub Company News
# مع ترجمة عربية مجانية باستخدام deep-translator بدون OpenRouter

import os
import requests
from datetime import datetime, timezone, timedelta

from watchlist_storage import normalize_ticker


FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

_TRANSLATION_CACHE = {}


def _clean(text):
    if not text:
        return ""
    text = str(text)
    text = (
        text.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#039;", "'")
        .replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return " ".join(text.split())


def _contains_arabic(text):
    if not text:
        return False
    return any("\u0600" <= ch <= "\u06FF" for ch in str(text))


def translate_to_ar(text, max_chars=320):
    """
    ترجمة مجانية عبر deep-translator.
    لا تستخدم OpenRouter ولا تضيف تكلفة على OpenRouter.
    إذا فشلت الترجمة نرجع نصًا فارغًا حتى لا يتوقف البوت.
    """
    text = _clean(text)

    if not text:
        return ""

    if _contains_arabic(text):
        return text

    # نقلل طول النص حتى تكون الترجمة أسرع وأثبت
    text = text[:max_chars].strip()

    cache_key = text
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    try:
        from deep_translator import GoogleTranslator

        translated = GoogleTranslator(source="auto", target="ar").translate(text)
        translated = _clean(translated)

        if translated and translated.lower() != text.lower():
            _TRANSLATION_CACHE[cache_key] = translated
            return translated

    except Exception as e:
        print(f"translation error: {e}", flush=True)

    return ""


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


def format_company_news(ticker, days=7, limit=5, translate=True):
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

        title_ar = translate_to_ar(title, max_chars=220) if translate else ""
        summary_short = summary[:260].strip() if summary else ""
        if summary and len(summary) > 260:
            summary_short += "..."

        summary_ar = translate_to_ar(summary_short, max_chars=320) if translate and summary_short else ""

        lines.append(f"{i}. {title}")

        if title_ar:
            lines.append(f"🌍 الترجمة: {title_ar}")

        lines.append(f"المصدر: {source}")
        lines.append(f"الوقت: {age}")

        if summary_short:
            lines.append(f"الملخص: {summary_short}")

        if summary_ar:
            lines.append(f"🌍 ترجمة الملخص: {summary_ar}")

        if url:
            lines.append(f"الرابط: {url}")

        lines.append("")

    lines.append("ملاحظة: الترجمة مجانية عبر deep-translator ولا تستخدم OpenRouter.")
    return "\n".join(lines).strip()


def format_latest_news_for_ticker(ticker, collect_all_news_func=None, limit=5):
    """
    الدالة الرئيسية التي يستخدمها زر آخر الأخبار.
    في v5.9.2:
    - مصدر الأخبار: Finnhub Company News
    - الترجمة: deep-translator
    - لا يستخدم OpenRouter
    """
    ticker = normalize_ticker(ticker)

    if not ticker:
        return "رمز السهم غير صحيح."

    return format_company_news(ticker, days=7, limit=limit, translate=True)
