import os
import requests
import threading
from flask import Flask
import telebot

# Telegram Bot Token (Environment Variable se lega)
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN) if TOKEN else None

app = Flask(__name__)

# Web server route taaki Render app ko active/alive rakhe
@app.route('/')
def home():
    return "Firebase Checker Telegram Bot is running successfully!"

# Telegram Bot Logic
if bot:
    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        bot.reply_to(message, "🤖 **Firebase Checker Bot Ready!**\n\nKoi bhi Firebase URL bhejein, main check karke bataunga ki Active hai ya Deactivated.", parse_mode="Markdown")

    @bot.message_handler(func=lambda message: True)
    def check_firebase(message):
        text = message.text.strip()
        
        # Multiple URLs support (line-by-line check)
        urls = [line.strip() for line in text.split('\n') if line.strip()]
        
        if len(urls) == 1:
            url = urls[0]
            if "firebaseio.com" not in url and "firebasedatabase.app" not in url:
                bot.reply_to(message, "❌ Yeh valid Firebase URL nahi lag raha hai.")
                return
            
            if not url.startswith("http"):
                url = "https://" + url

            msg = bot.reply_to(message, "⏳ Checking status...")

            try:
                clean_url = url.rstrip('/') + '/.json'
                r = requests.get(clean_url, timeout=5)
                
                if r.status_code == 404 or "disabled" in r.text.lower() or "does not exist" in r.text.lower():
                    bot.edit_message_text(f"🔴 *DEACTIVATED / DEAD*\n\n`{url}`", message.chat.id, msg.message_id, parse_mode="Markdown")
                else:
                    bot.edit_message_text(f"🟢 *ACTIVE / WORKING*\n\n`{url}`", message.chat.id, msg.message_id, parse_mode="Markdown")
            except Exception:
                bot.edit_message_text(f"⚠️ *ERROR / OFFLINE*\n\n`{url}`", message.chat.id, msg.message_id, parse_mode="Markdown")

        else:
            # Agar user ne ek sath multiple URLs bheje ho
            msg = bot.reply_to(message, f"⏳ Checking {len(urls)} Firebase URLs...")
            results = []
            
            for url in urls:
                if "firebaseio.com" not in url and "firebasedatabase.app" not in url:
                    continue
                if not url.startswith("http"):
                    url = "https://" + url
                
                try:
                    clean_url = url.rstrip('/') + '/.json'
                    r = requests.get(clean_url, timeout=4)
                    if r.status_code == 404 or "disabled" in r.text.lower() or "does not exist" in r.text.lower():
                        results.append(f"🔴 `{url}`")
                    else:
                        results.append(f"🟢 `{url}`")
                except Exception:
                    results.append(f"⚠️ `{url}`")
            
            response_text = "\n".join(results) if results else "❌ Koi valid Firebase URL nahi mila."
            if len(response_text) > 4000:
                response_text = response_text[:4000] + "\n...list too long"
            bot.edit_message_text(response_text, message.chat.id, msg.message_id, parse_mode="Markdown")

def start_bot():
    if bot:
        print("Bot is polling...")
        bot.infinity_polling()

# Bot ko background thread me chalana taaki Flask app freeze na ho
threading.Thread(target=start_bot, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

