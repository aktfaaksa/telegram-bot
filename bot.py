import requests
import asyncio
import json
import hashlib
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from deep_translator import GoogleTranslator
from openai import OpenAI

# ====== إعدادات ======
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880
]

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

# ====== Ticker ======
KNOWN_TICKERS = ["TSLA","AAPL","NVDA","MSFT","AMZN","GOOGL","META"]

NAME_TO_TICKER = {
    "tesla": "TSLA",
    "apple": "AAPL",
    "nvidia": "NVDA",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "google": "GOOGL",
    "meta": "META"
}

def extract_ticker(title):
    t = title.lower()

    for name, symbol in NAME_TO_TICKER.items():
        if name in t:
            return symbol

    for w in title.upper().split():
        if w in KNOWN_TICKERS:
            return w

    return None

# ====== ترجمة ======
def smart_translate(title):
    t = title.lower()

    if "earnings" in t and "beat" in t:
        return "أرباح أعلى من التوقعات (إيجابي 📈)"
    if "miss" in t:
        return "أرباح أقل من المتوقع (سلبي 📉)"

    try:
        return GoogleTranslator(source='auto', target='ar').translate(title)
    except:
        return title

# ====== تقييم ======
def news_impact(title):
    t = title.lower()
    score = 0

    if "earnings" in t:
        score += 4
    if "fed" in t:
        score += 3
    if "surge" in t or "crash" in t:
        score += 2

    return score

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
        indices = {
            "S&P 500": "SPY",
            "Nasdaq": "QQQ",
            "Dow": "DIA"
        }

        results = {}

        for name, symbol in indices.items():
            _, change = get_price(symbol)
            results[name] = change if change else 0

        spy = results["S&P 500"]
        nasdaq = results["Nasdaq"]
        dow = results["Dow"]

        if spy > 0 and nasdaq > 0 and dow > 0:
            sentiment = "🔥 السوق قوي"
        elif spy < 0 and dow < 0:
            sentiment = "📉 السوق ضعيف"
        else:
            sentiment = "⚠️ حذر"

        return (
            f"📊 حالة السوق:\n"
            f"S&P 500: {spy}%\n"
            f"Nasdaq: {nasdaq}%\n"
            f"Dow: {dow}%\n\n"
            f"{sentiment}"
        )
    except:
        return "❌ خطأ في السوق"

# ====== AI ======
def generate_ai_analysis(symbol, title):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": f"حلل الخبر {title} للسهم {symbol} بشكل مختصر"}]
        )
        return response.choices[0].message.content
    except:
        return "تعذر التحليل"

# ====== الأخبار ======
def get_news():
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={API_KEY}"
        return requests.get(url).json()
    except:
        return []

# ====== الأوامر ======
async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in CHAT_IDS:
        return
    await update.message.reply_text(get_market_status())

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in CHAT_IDS:
        return
    try:
        symbol = context.args[0].upper()
    except:
        await update.message.reply_text("❌ اكتب: /سعر TSLA")
        return

    price, change = get_price(symbol)
    arrow = "📈" if change and change > 0 else "📉"
    await update.message.reply_text(f"{symbol}\n{price}$ {arrow} {change}%")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in CHAT_IDS:
        return
    try:
        symbol = context.args[0].upper()
    except:
        await update.message.reply_text("❌ اكتب: /تحليل TSLA")
        return

    analysis = generate_ai_analysis(symbol, "تحليل عام")
    await update.message.reply_text(f"🤖 تحليل {symbol}\n\n{analysis}")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in CHAT_IDS:
        return
    try:
        symbol = context.args[0].upper()
    except:
        await update.message.reply_text("❌ اكتب: /اخبار TSLA")
        return

    url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from=2024-01-01&to=2025-12-31&token={API_KEY}"
    data = requests.get(url).json()

    msgs = []
    for n in data[:3]:
        msgs.append(f"📰 {n['headline']}\n🔗 {n['url']}")

    await update.message.reply_text("\n\n".join(msgs))

# ====== الأخبار التلقائية ======
async def news_loop(app):
    while True:
        try:
            news_list = get_news()

            for n in news_list:
                title = n.get("headline")
                url = n.get("url")

                if not title or not url:
                    continue

                nid = news_id(title)
                if nid in sent_news:
                    continue

                impact = news_impact(title)
                if impact < 3:
                    continue

                ticker = extract_ticker(title)
                price, change = get_price(ticker) if ticker else (None, None)
                ar = smart_translate(title)
                market = get_market_status()

                msg = f"""
🚨 تنبيه

{market}

🏢 {ticker if ticker else 'عام'}
📊 {price}$ ({change}%)

📰 {title}
🇸🇦 {ar}

🔗 {url}
"""

                for chat_id in CHAT_IDS:
                    await app.bot.send_message(chat_id=chat_id, text=msg)

                sent_news.add(nid)
                save_news()

                await asyncio.sleep(2)

            await asyncio.sleep(15)

        except Exception as e:
            print(e)
            await asyncio.sleep(10)

# ====== التشغيل ======
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("السوق", market_command))
    app.add_handler(CommandHandler("تحليل", analyze_command))
    app.add_handler(CommandHandler("سعر", price_command))
    app.add_handler(CommandHandler("اخبار", news_command))

    await app.initialize()
    await app.start()

    asyncio.create_task(news_loop(app))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())