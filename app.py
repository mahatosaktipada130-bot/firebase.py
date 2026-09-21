import os
import re
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Render Web Server to keep port alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# Telegram Bot Token Yahan Dalein ya Render Environment Variables me set karein
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

async def check_single_firebase(session: aiohttp.ClientSession, url: str) -> str | None:
    """
    Async request se fast check karta hai.
    0 device/connections wale link ko return karega, baki ko None.
    """
    clean_url = url.split("?")[0].rstrip("/")
    request_url = clean_url if clean_url.endswith(".json") else clean_url + ".json"
    
    if not request_url.startswith("http://") and not request_url.startswith("https://"):
        request_url = "https://" + request_url

    try:
        # Timeout 3 seconds rakha hai fast processing ke liye
        async with session.get(request_url, timeout=aiohttp.ClientTimeout(total=3)) as response:
            if response.status == 200:
                data = await response.json()
                # Data empty ho ya 0 length ho tabhi valid 0-device manega
                if data is None or len(data) == 0:
                    return clean_url
            else:
                # Agar endpoint response nahi de raha ya dead hai to use 0 device manke include karna hai
                return clean_url
    except Exception:
        # Request failed or timeout means no active devices reachable
        return clean_url
    
    return None

async def check_all_firebases(urls: list) -> list:
    """
    300+ URLs ko ek sath parallelly execute karta hai
    """
    connector = aiohttp.TCPConnector(limit=100) # Concurrent connections limit
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_single_firebase(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        # None values ko filter karke hata do
        return [res for res in results if res is not None]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ Fast Firebase Checker active!\n\n"
        "Bhai 300-500 kitne bhi Firebase links ek sath bhej do, "
        "kuch hi seconds me filter ho jayenge."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Expressive RegEx for all URLs containing firebaseio.com or custom endpoints
    urls = re.findall(r'(https?://[^\s]+|[\w-]+\.firebaseio\.com[^\s]*)', text)
    
    if not urls:
        await update.message.reply_text("Koyi valid Firebase link nahi mila.")
        return

    msg = await update.message.reply_text(f"🚀 {len(urls)} links fast check ho rahe hain...")

    # Parallel async execution
    zero_device_links = await check_all_firebases(urls)

    if zero_device_links:
        # 4096 character length limits handle karne ke liye chunks me bhejega
        response_text = "\n".join(zero_device_links)
        
        if len(response_text) > 4000:
            for i in range(0, len(zero_device_links), 80):
                chunk = "\n".join(zero_device_links[i:i+80])
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response_text)
    else:
        await update.message.reply_text("Koyi bhi 0-device wala Firebase link nahi mila.")

def main():
    # Flask ko alag thread me run karein taaki Render ka Web Service port bind ho jaye
    Thread(target=run_flask, daemon=True).start()

    # Telegram Bot App
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Server and Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()
