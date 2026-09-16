import os
import re
import base64
import threading
import requests
import telebot
from urllib.parse import parse_qs, urlparse
from flask import Flask

app = Flask(__name__)

# Environment variable se Token lega ya fallback string se
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7123456789:AAFg...aapka_real_token_yahan")
bot = telebot.TeleBot(BOT_TOKEN)

def extract_and_decode_urls(text):
    """
    Multiple URLs aur raw text me se normal URLs aur Base64 encoded 
    panel links (?s=...) dono ko decode karke extract karta hai.
    """
    urls_found = set()
    # General URL pattern matching
    raw_urls = re.findall(r'https?://[^\s"\']+', text)
    
    for url in raw_urls:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Check agar URL me Base64 encoded parameter (?s=...) hai
        if 's' in params:
            encoded_str = params['s'][0]
            try:
                # Fix missing Base64 padding (=)
                missing_padding = len(encoded_str) % 4
                if missing_padding:
                    encoded_str += '=' * (4 - missing_padding)
                
                decoded_bytes = base64.b64decode(encoded_str)
                decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
                
                # Decoded content se inner Firebase URLs extract karein
                inner_urls = re.findall(r'https?://[^\s"\'|]+', decoded_text)
                for u in inner_urls:
                    urls_found.add(u)
            except Exception:
                urls_found.add(url)
        else:
            urls_found.add(url)
            
    return list(urls_found)

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
        # Open DB Access Check
        elif status == 200:
            return {"url": clean_url, "status": "ACTIVE_OPEN", "reason": "Open Read Access"}
        else:
            return {"url": clean_url, "status": "DEAD", "reason": f"HTTP {status}"}
    except Exception:
        return {"url": clean_url, "status": "ERROR", "reason": "Timeout/Network Error"}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "👋 **Firebase Database & Panel Decoder Bot**\n\n"
        "1. Single/Multiple direct URLs ya Base64 Panel links ka message bhejo.\n"
        "2. Ya fir `.txt` file upload karo.\n\n"
        "Bot auto-decode karke sabhi Firebase status check kar dega."
    )

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ Kripya sirf `.txt` file bhejein.")
        return

    msg = bot.reply_to(message, "⏳ File process aur decode ho rahi hai...")
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_content = downloaded_file.decode('utf-8', errors='ignore')

    urls = extract_and_decode_urls(file_content)
    process_and_respond(message, urls, msg)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    urls = extract_and_decode_urls(message.text)
    if not urls:
        bot.reply_to(message, "❌ Input me koi valid URL ya decode hone wala link nahi mila.")
        return

    msg = bot.reply_to(message, "⏳ Links extract aur decode ho rahe hain...")
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
        f"✅ **Processing Complete!**\n\n"
        f"🟢 Active URLs: `{len(active_urls)}`\n"
        f"🔴 Dead / Disabled URLs: `{dead_count}`\n"
        f"📊 Total Extracted & Checked: `{len(active_urls) + dead_count}`"
    )

    bot.edit_message_text(response_text, message.chat.id, status_msg.message_id, parse_mode="Markdown")

    if active_urls:
        with open(result_filename, "rb") as f:
            bot.send_document(message.chat.id, f, caption="📁 Ye rahe aapke Active URLs.")

    if os.path.exists(result_filename):
        os.remove(result_filename)

def start_polling():
    print(">>> Telegram Bot Polling Thread Started <<<", flush=True)
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"Polling error: {e}", flush=True)

# Gunicorn start hone par background thread launch karein
t = threading.Thread(target=start_polling, daemon=True)
t.start()

@app.route('/')
def health_check():
    return "Firebase Decoder & Checker Bot is Alive & Running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

