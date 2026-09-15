import os
import asyncio
import aiohttp
import threading
from flask import Flask
import telebot

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN) if TOKEN else None

app = Flask(__name__)

@app.route('/')
def home():
    return "Async Ultra-Fast Firebase Checker is Online!"

async def check_url(session, url):
    """Fast Async URL check with strict 2s timeout"""
    if "firebaseio.com" not in url and "firebasedatabase.app" not in url:
        return None
    
    if not url.startswith("http"):
        url = "https://" + url

    clean_url = url.rstrip('/') + '/.json'
    
    try:
        async with session.get(clean_url, timeout=2) as response:
            text = await response.text()
            if response.status == 404 or "disabled" in text.lower() or "does not exist" in text.lower():
                return f"🔴 `{url}`"
            else:
                return f"🟢 `{url}`"
    except Exception:
        return f"⚠️ `{url}`"

async def process_bulk_urls(urls):
    """Parallel execution using asyncio"""
    async with aiohttp.ClientSession() as session:
        tasks = [check_url(session, url) for url in urls]
        return await asyncio.gather(*tasks)

def send_in_chunks(chat_id, text):
    """Telegram 4000 char limit handler"""
    max_len = 3500
    for i in range(0, len(text), max_len):
        bot.send_message(chat_id, text[i:i+max_len], parse_mode="Markdown")

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "⚡ **Super Fast Async Firebase Checker Ready!**\n\nKitne bhi links bhej do, 3 second me result milega.")

    @bot.message_handler(func=lambda message: True)
    def check_firebase(message):
        urls = [line.strip() for line in message.text.split('\n') if line.strip()]
        
        if not urls:
            return

        msg = bot.reply_to(message, f"🚀 Checking {len(urls)} Firebase URLs... Please wait.")

        # Run Async loop for fast processing
        try:
            results = asyncio.run(process_bulk_urls(urls))
        except Exception:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(process_bulk_urls(urls))

        valid_results = [res for res in results if res is not None]

        if not valid_results:
            bot.edit_message_text("❌ No valid Firebase URLs found.", message.chat.id, msg.message_id)
            return

        active_count = sum(1 for r in valid_results if "🟢" in r)
        dead_count = sum(1 for r in valid_results if "🔴" in r)
        error_count = sum(1 for r in valid_results if "⚠️" in r)

        header = (
            f"📊 **Check Complete! (Total: {len(valid_results)})**\n\n"
            f"🟢 Active: {active_count} | 🔴 Dead: {dead_count} | ⚠️ Error: {error_count}\n"
            + "─"*30 + "\n\n"
        )
        full_response = header + "\n".join(valid_results)

        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception:
            pass

        send_in_chunks(message.chat.id, full_response)

def run_bot():
    if bot:
        bot.remove_webhook()
        print("Bot started with Async engine...")
        bot.infinity_polling(skip_pending=True)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
