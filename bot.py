import requests
import asyncio
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

# 👇 تم التعديل هنا (إضافة شخص ثاني)
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
def smart_translate(title):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(title)
    except:
        return title

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
            sentiment = "⚠️ حذر"

        return f"""
📊 حالة السوق:

S&P 500: {spy}%
Nasdaq: {nasdaq}%
Dow: {dow}%

{sentiment}
"""
    except:
        return "❌ خطأ في السوق"

# ====== AI ======
def analyze_stock(symbol):
    try:
        prompt = f"حلل سهم {symbol} بشكل مختصر واذكر التوصية (شراء أو بيع أو حياد)"
        response = model.generate_content(prompt)
        return response.text
    except:
        return "⚠️ فشل التحليل"

# ====== أوامر ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً بك\nاستخدم /تحليل TSLA")

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
        await update.message.reply_text("❌ خطأ")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_market_status())

# ====== أخبار تلقائية ======
async def news_loop(app):
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
🚨 خبر

📰 {title}
🇸🇦 {smart_translate(title)}

🔗 {link}
"""

                # 👇 تم التعديل هنا (إرسال للجميع)
                for chat_id in CHAT_IDS:
                    await app.bot.send_message(chat_id=chat_id, text=msg)

                sent_news.add(nid)
                save_news()

                await asyncio.sleep(2)

            await asyncio.sleep(60)

        except Exception as e:
            print(e)
            await asyncio.sleep(10)

# ====== تشغيل ======
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("تحليل", analyze))
    app.add_handler(CommandHandler("سعر", price))
    app.add_handler(CommandHandler("السوق", market))

    await app.initialize()
    await app.start()

    asyncio.create_task(news_loop(app))

    await app.run_polling()

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("تحليل", analyze))
    app.add_handler(CommandHandler("سعر", price))
    app.add_handler(CommandHandler("السوق", market))

    print("Bot started...")

    app.run_polling()

if __name__ == "__main__":
    main()