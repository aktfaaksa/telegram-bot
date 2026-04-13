import aiohttp
import os
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from openai import OpenAI

# ===== ENV =====
TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_KEY = os.getenv("OPENROUTER_API_KEY")

CHAT_IDS = [
    int(os.getenv("CHAT_ID")),
    6315087880
]

# ===== AI =====
client = OpenAI(
    api_key=OPENAI_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://example.com",
        "X-Title": "telegram-bot"
    }
)

async def ai_analyze(text):
    try:
        response = client.chat.completions.create(
            model="qwen/qwen3-next-80b-a3b-instruct:free",
            messages=[
                {"role": "system", "content": "You are a stock trading assistant."},
                {"role": "user", "content": f"""
Decision: BUY or SELL or HOLD
Confidence: %

Stock: {text}
"""}
            ]
        )
        return response.choices[0].message.content

    except Exception as e:
        print("QWEN ERROR:", e)

        # 🔥 fallback
        try:
            response = client.chat.completions.create(
                model="meta-llama/llama-3-8b-instruct:free",
                messages=[{"role": "user", "content": text}]
            )
            return response.choices[0].message.content
        except Exception as e2:
            print("LLAMA ERROR:", e2)
            return "❌ AI غير متوفر حالياً"

# ===== COMPANY MAP =====
COMPANY_MAP = {
    "TESLA":"TSLA","APPLE":"AAPL","NVIDIA":"NVDA",
    "AMD":"AMD","META":"META","MICROSOFT":"MSFT",
    "AMAZON":"AMZN","GOOGLE":"GOOGL"
}

def get_symbol(text):
    t = text.upper()
    if t in COMPANY_MAP.values():
        return t
    for name, s in COMPANY_MAP.items():
        if name in t:
            return s
    return t

# ===== STOCK =====
async def get_stock(symbol):
    print("Fetching:", symbol)

    async with aiohttp.ClientSession() as session:
        q = await (await session.get(
            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        )).json()

        print("DATA:", q)

        if not q or q.get("c") is None:
            return "❌ السهم غير موجود أو API فيه مشكلة"

        price = q.get("c")
        change = round(q.get("dp", 0), 2)
        arrow = "📈" if change >= 0 else "📉"

        ai_text = await ai_analyze(symbol)

        return f"""
📊 {symbol}

💰 {price}$ {arrow} {change}%

🤖 {ai_text}
"""

# ===== COMMAND =====
async def stock_cmd(update, context):
    if not context.args:
        msg = "اكتب:\n/stock TSLA"
    else:
        symbol = get_symbol(context.args[0])
        msg = await get_stock(symbol)

    for c in CHAT_IDS:
        await context.bot.send_message(chat_id=c, text=msg)

# ===== TEXT (عربي) =====
async def handle_text(update, context):
    text = update.message.text.lower()

    if text.startswith("سهم"):
        try:
            symbol = get_symbol(text.split(" ")[1])
            msg = await get_stock(symbol)
        except:
            msg = "اكتب: سهم TSLA"

    elif text.startswith("تحليل"):
        try:
            symbol = get_symbol(text.split(" ")[1])
            msg = await ai_analyze(symbol)
        except:
            msg = "اكتب: تحليل TSLA"

    else:
        return

    for c in CHAT_IDS:
        await context.bot.send_message(chat_id=c, text=msg)

# ===== MAIN =====
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("stock", stock_cmd))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    print("Bot started...")

    app.run_polling()

# ===== RUN =====
if __name__ == "__main__":
    main()