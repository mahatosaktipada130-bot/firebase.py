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
    return "Optimized Low-RAM Firebase Checker is Active!"

def check_single(url):
    """Memory-efficient checking logic"""
    if "firebaseio.com" not in url and "firebasedatabase.app" not in url:
        return None
    
    if not url.startswith("http"):
        url = "https://" + url

    clean_url = url.rstrip('/') + '/.json'
    
    # Session ka use karke connections reusable aur memory safe banaye hain
    session = requests.Session()
    try:
        r = session.get(clean_url, timeout=3)
        if r.status_code == 404 or "disabled" in r.text.lower() or "does not exist" in r.text.lower():
            res = f"🔴 `{url}`"
        else:
            res = f"🟢 `{url}`"
    except Exception:
        res = f"⚠️ `{url}`"
    finally:
        session.close()
        
    return res

def send_in_chunks(chat_id, text):
    """Telegram message length limit handle karne ke liye"""
    max_len = 3500
    for i in range(0, len(text), max_len):
        bot.send_message(chat_id, text[i:i+max_len], parse_mode="Markdown")

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "⚡ **Stable Bulk Firebase Checker Ready!**\n\nAap 100 links tak paste karke bhej sakte hain.")

    @bot.message_handler(func=lambda message: True)
    def check_firebase(message):
        urls = [line.strip() for line in message.text.split('\n') if line.strip()]
        
        if not urls:
            return

        msg = bot.reply_to(message, f"🚀 Checking {len(urls)} Firebase URLs... Please wait.")

        # Max 10 threads taaki Render 512MB RAM crash na ho
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(check_single, urls))

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

def start_bot():
    if bot:
        print("Bot is polling...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
