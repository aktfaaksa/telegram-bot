import requests
import time
import json
import hashlib
import os
import google.generativeai as genai

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from deep_translator import GoogleTranslator

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 👇 الشخصين هنا
CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# ====== منع التكرار ======
def news_id(title):
    return hashlib.md5(title.lower()[:60].encode()).hexdigest()

def load_news():
    try:
        with open("sent.json", "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_news():
    with open("sent.json", "w") as f:
        json.dump(list(sent_news), f)

sent_news = load_news()

# ====== ترجمة ======
def smart_translate(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# ====== السعر ======
def get_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        d = requests.get(url).json()
        c = d.get("c")
        pc = d.get("pc")

        if c and pc:
            change = ((c - pc) / pc) * 100
            return c, round(change, 2)
    except:
        pass
    return None, None

# ====== السوق ======
def get_market_status():
    try:
        indices = {"S&P 500": "SPY", "Nasdaq": "QQQ", "Dow": "DIA"}
        results = {}

        for name, symbol in indices.items():
            _, change = get_price(symbol)
            results[name] = change if change else 0

        spy = results["S&P 500"]
        nasdaq = results["Nasdaq"]
        dow = results["Dow"]

        if spy > 0 and nasdaq > 0:
            sentiment = "🔥 السوق صاعد"
        elif spy < 0 and dow < 0:
            sentiment = "📉 السوق هابط"
        else:
            sentiment = "⚠️ السوق متذبذب"

        return f"""
📊 حالة السوق:

S&P 500: {spy}%
Nasdaq: {nasdaq}%
Dow: {dow}%

{sentiment}
"""
    except:
        return "❌ خطأ في جلب السوق"

# ====== AI ======
def analyze_stock(symbol):
    try:
        prompt = f"حلل سهم {symbol} بشكل مختصر واذكر هل هو مناسب للشراء أو البيع"
        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ فشل التحليل"

# ====== أوامر ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك في بوت الأسهم\n\nالأوامر:\n/تحليل TSLA\n/سعر TSLA\n/السوق")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ اكتب: /تحليل TSLA")
        return

    symbol = context.args[0].upper()
    result = analyze_stock(symbol)

    await update.message.reply_text(f"""
📊 سهم: {symbol}

🤖 التحليل:
{result}
""")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ اكتب: /سعر TSLA")
        return

    symbol = context.args[0].upper()
    p, c = get_price(symbol)

    if p:
        arrow = "📈" if c > 0 else "📉"
        await update.message.reply_text(f"{symbol}: {p}$ {arrow} {c}%")
    else:
        await update.message.reply_text("❌ خطأ في جلب السعر")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_market_status())

# ====== الأخبار ======
def send_news(app):
    global sent_news

    while True:
        try:
            url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
            news = requests.get(url).json()

            for n in news[:5]:
                title = n.get("headline")
                link = n.get("url")

                if not title or not link:
                    continue

                nid = news_id(title)
                if nid in sent_news:
                    continue

                msg = f"""
🚨 خبر جديد

📰 {title}
🇸🇦 {smart_translate(title)}

🔗 {link}
"""

                # إرسال للجميع
                for chat_id in CHAT_IDS:
                    app.bot.send_message(chat_id=chat_id, text=msg)

                sent_news.add(nid)
                save_news()

                time.sleep(2)

            time.sleep(60)

        except Exception as e:
            print(e)
            time.sleep(10)

# ====== تشغيل ======
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("تحليل", analyze))
    app.add_handler(CommandHandler("سعر", price))
    app.add_handler(CommandHandler("السوق", market))

    print("Bot started...")

    # تشغيل الأخبار بالخلفية
    import threading
    threading.Thread(target=send_news, args=(app,), daemon=True).start()

    app.run_polling()

if __name__ == "__main__":
    main()