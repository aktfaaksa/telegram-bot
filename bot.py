# ===== Alpha Market Intelligence (Events Only) =====

import asyncio
import aiohttp
import feedparser
import hashlib
import os
from telegram import Bot

# ===== ENV VARIABLES =====
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_MAIN = int(os.getenv("CHAT_ID"))

# المستلم الثاني (اللي حطيته أنت)
CHAT_IDS = [
    CHAT_ID_MAIN,
    6315087880,
]

bot = Bot(token=TOKEN)

# ===== RSS SOURCES =====
RSS_FEEDS = [
    "https://finance.yahoo.com/rss/",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# ===== KEYWORDS (الأحداث المهمة) =====
KEYWORDS = [
    "earnings", "revenue", "eps", "guidance",
    "acquisition", "merger", "buyout",
    "upgrade", "downgrade", "rating",
    "fda", "sec", "approval", "regulation",
]

# ===== STORAGE لمنع التكرار =====
sent_hashes = set()

def is_new(text):
    h = hashlib.md5(text.encode()).hexdigest()
    if h in sent_hashes:
        return False
    sent_hashes.add(h)
    return True

# ===== جلب الأخبار =====
async def get_market_news():
    important_news = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            title = entry.title.lower()

            if any(word in title for word in KEYWORDS):
                important_news.append({
                    "title": entry.title,
                    "link": entry.link
                })

    return important_news

# ===== إرسال الرسالة =====
async def send_news_alert(news):
    message = f"""
📰 *Market Event*

{news['title']}

🔗 {news['link']}
"""

    for chat_id in CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
        except Exception as e:
            print(f"Error sending to {chat_id}: {e}")

# ===== اللوب الرئيسي =====
async def main():
    print("🚀 Bot Started...")

    while True:
        try:
            news_list = await get_market_news()

            for news in news_list:
                if is_new(news["title"]):
                    await send_news_alert(news)

            await asyncio.sleep(300)  # كل 5 دقائق

        except Exception as e:
            print("Error:", e)
            await asyncio.sleep(60)

# ===== تشغيل =====
if __name__ == "__main__":
    asyncio.run(main())