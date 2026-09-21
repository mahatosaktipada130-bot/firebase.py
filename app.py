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
    Sirf 1+ active devices/data wale link ko return karega.
    0 device / dead links ko None karke HATA DEGA.
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
                
                # Agar data active/present hai (devices > 0)
                if data is not None:
                    if isinstance(data, (dict, list)) and len(data) > 0:
                        return clean_url
                    elif not isinstance(data, (dict, list)): # Single value/primitive data
                        return clean_url
    except Exception:
        # Request error / timeout / unreachable ko 0 device maan kar ignore karenge
        pass
    
    # 0 device ya invalid link ko None return karke hata do
    return None

async def check_all_firebases(urls: list) -> list:
    """
    300+ URLs ko ek sath parallelly execute karta hai
    """
    connector = aiohttp.TCPConnector(limit=100) # Concurrent connections limit
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_single_firebase(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        # None (0 devices) wale items ko filter karke hata do
        return [res for res in results if res is not None]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ Active Firebase Checker Ready!\n\n"
        "Bhai Firebase links bhej do. Main 0 device wale saare links hata dunga "
        "aur sirf active (1+ device) wale links bhejunga."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # RegEx for all Firebase URLs
    urls = re.findall(r'(https?://[^\s]+|[\w-]+\.firebaseio\.com[^\s]*)', text)
    
    if not urls:
        await update.message.reply_text("Koyi valid Firebase link nahi mila.")
        return

    msg = await update.message.reply_text(f"🚀 {len(urls)} links check ho rahe hain (0 device wale filter ho rahe hain)...")

    # Parallel async execution
    active_device_links = await check_all_firebases(urls)

    if active_device_links:
        # 4096 character length limits handle karne ke liye chunks me bhejega
        if len("\n".join(active_device_links)) > 4000:
            for i in range(0, len(active_device_links), 80):
                chunk = "\n".join(active_device_links[i:i+80])
                await update.message.reply_text(chunk)
        else:
            response_text = "\n".join(active_device_links)
            await update.message.reply_text(response_text)
    else:
        await update.message.reply_text("Ek bhi active device wala Firebase link nahi mila (Sabhi 0 device/dead the).")

def main():
    # Flask ko alag thread me run karein Render port binding ke liye
    Thread(target=run_flask, daemon=True).start()

    # Telegram Bot App
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Server and Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()

