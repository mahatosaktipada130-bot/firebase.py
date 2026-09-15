import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
import telebot

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN) if TOKEN else None

app = Flask(__name__)

@app.route('/')
def home():
    return "Ultra-Fast 100 Bulk Firebase Checker is Running!"

def single_check(url):
    """Fast URL checking with strict 3s timeout"""
    if "firebaseio.com" not in url and "firebasedatabase.app" not in url:
        return None
    
    if not url.startswith("http"):
        url = "https://" + url

    clean_url = url.rstrip('/') + '/.json'
    try:
        r = requests.get(clean_url, timeout=3)
        if r.status_code == 404 or "disabled" in r.text.lower() or "does not exist" in r.text.lower():
            return f"🔴 `{url}`"
        else:
            return f"🟢 `{url}`"
    except Exception:
        return f"⚠️ `{url}`"

def send_long_message(chat_id, text):
    """100 Links ke bade results ko safely split karke bhejne ke liye"""
    max_length = 3500
    if len(text) <= max_length:
        bot.send_message(chat_id, text, parse_mode="Markdown")
    else:
        lines = text.split("\n")
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > max_length:
                bot.send_message(chat_id, current_chunk, parse_mode="Markdown")
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk:
            bot.send_message(chat_id, current_chunk, parse_mode="Markdown")

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "⚡ **100 Bulk Firebase Checker Ready!**\n\nEk saath 100 links tak paste karke bhej do, super-fast check ho jayega.")

    @bot.message_handler(func=lambda message: True)
    def check_firebase(message):
        text = message.text.strip()
        urls = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not urls:
            return

        msg = bot.reply_to(message, f"🚀 Checking {len(urls)} Firebase URLs in parallel... Please wait.")

        # Ek saath 50 threads parallel chalenge (Ultra Speed)
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(single_check, urls))

        valid_results = [res for res in results if res is not None]

        if not valid_results:
            bot.edit_message_text("❌ Koi valid Firebase URL nahi mila.", message.chat.id, msg.message_id)
            return

        # Counts
        active_count = sum(1 for r in valid_results if "🟢" in r)
        dead_count = sum(1 for r in valid_results if "🔴" in r)
        error_count = sum(1 for r in valid_results if "⚠️" in r)

        summary_header = (
            f"📊 **Check Complete! (Total: {len(valid_results)})**\n\n"
            f"🟢 Active: {active_count} | 🔴 Dead: {dead_count} | ⚠️ Error: {error_count}\n"
            + "─"*32 + "\n\n"
        )
        full_response = summary_header + "\n".join(valid_results)

        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception:
            pass

        send_long_message(message.chat.id, full_response)

def start_bot():
    if bot:
        print("Bot is polling...")
        bot.infinity_polling()

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
