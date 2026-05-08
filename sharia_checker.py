# AlphaBot Pro v5.9
# sharia_checker.py
# فحص شرعية مبسط وقابل للتوسعة
#
# مهم:
# هذا الملف لا يدعي أنه مصدر شرعي نهائي.
# الهدف الحالي: منع الإضافة التلقائية قبل وجود نتيجة.
# لاحقًا يمكن ربطه بقاعدة بيانات أو API أو ملف CSV خاص بالشرعية.

from watchlist_storage import normalize_ticker

SHARIA_DB = {
    "RKLB": {
        "status": "compliant",
        "label": "متوافق",
        "source": "فلتر بنك البلاد وبنك الراجحي حسب بيانات المستخدم",
        "purification": "2.54%",
        "note": "معتمد مؤقتًا في قائمة المستخدم حتى إعادة التقييم.",
    },
    "SOUN": {
        "status": "compliant",
        "label": "متوافق",
        "source": "فلتر بنك البلاد وبنك الراجحي حسب بيانات المستخدم",
        "purification": "4.34%",
        "note": "متابعة حذرة بسبب التذبذب.",
    },
}


def check_sharia(ticker):
    ticker = normalize_ticker(ticker)

    if not ticker:
        return {
            "ticker": "",
            "status": "invalid",
            "label": "رمز غير صحيح",
            "can_add": False,
            "needs_user_approval": False,
            "message": "رمز السهم غير صحيح.",
        }

    item = SHARIA_DB.get(ticker)

    if item:
        status = item.get("status")

        if status == "compliant":
            return {
                "ticker": ticker,
                "status": "compliant",
                "label": "متوافق",
                "can_add": True,
                "needs_user_approval": False,
                "source": item.get("source", ""),
                "purification": item.get("purification", ""),
                "note": item.get("note", ""),
                "message": format_sharia_message(ticker, item),
            }

        if status == "non_compliant":
            return {
                "ticker": ticker,
                "status": "non_compliant",
                "label": "غير متوافق",
                "can_add": False,
                "needs_user_approval": False,
                "source": item.get("source", ""),
                "purification": item.get("purification", ""),
                "note": item.get("note", ""),
                "message": format_sharia_message(ticker, item),
            }

    # أي سهم جديد غير محفوظ نعتبره غير محسوم، ولا نضيفه إلا مؤقتًا بموافقة صريحة
    return {
        "ticker": ticker,
        "status": "unknown",
        "label": "غير محسوم",
        "can_add": False,
        "needs_user_approval": True,
        "source": "لا توجد نتيجة محفوظة في قاعدة الشرعية الحالية",
        "purification": "غير متوفر",
        "note": "لا تتم الإضافة الدائمة إلا بعد فحص الشرعية. يمكن إضافته مؤقتًا فقط بموافقتك.",
        "message": f"""📈 شرعية سهم {ticker}:

⚠️ الحالة: غير محسومة
المصدر: لا توجد نتيجة محفوظة في قاعدة الشرعية الحالية
نسبة التطهير: غير متوفرة

القرار:
لا يتم إضافة السهم إضافة دائمة الآن.
يمكن إضافته مؤقتًا فقط إذا وافقت من الزر.

⚠️ تنويه:
هذا فحص آلي مساعد وليس فتوى أو توصية. القرار النهائي عليك.""",
    }


def format_sharia_message(ticker, item):
    label = item.get("label", "غير معروف")
    source = item.get("source", "غير محدد")
    purification = item.get("purification", "غير متوفر")
    note = item.get("note", "")

    icon = "✅" if item.get("status") == "compliant" else "❌"

    return f"""📈 شرعية سهم {ticker}:

{icon} الحالة: {label}
المصدر: {source}
نسبة التطهير: {purification}

ملاحظة:
{note or "لا توجد ملاحظات إضافية."}

⚠️ تنويه:
هذا فحص آلي مساعد وليس فتوى أو توصية. القرار النهائي عليك."""
