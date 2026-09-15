import os
import threading
import requests
import telebot
from flask import Flask

# Flask Server (Render Port Binding ke liye)
app = Flask(__name__)

# Telegram Bot Token
BOT_TOKEN = "8876082662:AAG5mw5h8Pim7V236Xnk0MJt-lEv_RWOuAU"
bot = telebot.TeleBot(BOT_TOKEN)

def check_firebase_status(url):
    url = url.strip()
    if not url:
        return None

    clean_url = url.split("?")[0].rstrip("/")
    target_url = f"{clean_url}/.json"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(target_url, headers=headers, timeout=5)
        body = response.text.lower()
        status = response.status_code

        # Deactivated / Disabled Check
        if "database disabled" in body or "project disabled" in body:
            return {"url": clean_url, "status": "DEAD", "reason": "Database Disabled"}
        # Locked Rules Check
        elif "permission denied" in body:
            return {"url": clean_url, "status": "ACTIVE_LOCKED", "reason": "Permission Denied"}
        # Open DB
        elif status == 200:
            return {"url": clean_url, "status": "ACTIVE_OPEN", "reason": "Open Read Access"}
        else:
            return {"url": clean_url, "status": "DEAD", "reason": f"HTTP {status}"}
    except Exception:
        return {"url": clean_url, "status": "ERROR", "reason": "Timeout/Network Error"}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "👋 **Firebase Database Checker Bot**\n\n1. Mujhe Firebase URLs ka message bhejo.\n2. Ya fir `.txt` file upload karo.")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ Kripya sirf `.txt` file bhejein.")
        return

    msg = bot.reply_to(message, "⏳ File process ho rahi hai, kripya intezar karein...")
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    urls = downloaded_file.decode('utf-8', errors='ignore').splitlines()
    process_and_respond(message, urls, msg)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    urls = message.text.splitlines()
    if not any("firebaseio.com" in u or "firebasedatabase.app" in u for u in urls):
        bot.reply_to(message, "❌ Text me koi valid Firebase URL nahi mila.")
        return

    msg = bot.reply_to(message, "⏳ Checking started...")
    process_and_respond(message, urls, msg)

def process_and_respond(message, urls, status_msg):
    active_urls = []
    dead_count = 0

    for url in urls:
        if not url.strip():
            continue
        res = check_firebase_status(url)
        if res:
            if "ACTIVE" in res["status"]:
                active_urls.append(res["url"])
            else:
                dead_count += 1

    result_filename = f"active_{message.chat.id}.txt"
    with open(result_filename, "w") as f:
        f.write("\n".join(active_urls))

    response_text = (
        f"✅ **Checking Complete!**\n\n"
        f"🟢 Active URLs: `{len(active_urls)}`\n"
        f"🔴 Dead / Disabled URLs: `{dead_count}`\n"
        f"📊 Total Checked: `{len(active_urls) + dead_count}`"
    )

    bot.edit_message_text(response_text, message.chat.id, status_msg.message_id, parse_mode="Markdown")

    if active_urls:
        with open(result_filename, "rb") as f:
            bot.send_document(message.chat.id, f, caption="📁 Active Firebase URLs file.")

    if os.path.exists(result_filename):
        os.remove(result_filename)

def run_bot():
    print("Telegram Bot Polling Started...", flush=True)
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

@app.route('/')
def health_check():
    return "Telegram Bot Web Service is Running!"

if __name__ == "__main__":
    # Telegram Bot ko separate thread me start karo
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Flask App for Render Port Binding
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

