import os
import re
import sqlite3
import base64
import threading
import requests
import telebot
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

app = Flask(__name__)

# Environment variable se Token lega ya fallback string se
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7123456789:AAFg...aapka_real_token_yahan")
bot = telebot.TeleBot(BOT_TOKEN)

DB_NAME = "firebase_links.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT UNIQUE,
            status TEXT,
            added_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_active_url(user_id, url, status):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now = datetime.now().strftime("%d %b %Y, %I:%M %p")
        cursor.execute('''
            INSERT OR IGNORE INTO active_urls (user_id, url, status, added_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, url, status, now))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}", flush=True)

def get_user_urls(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT url, status FROM active_urls WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def extract_and_decode_urls(text):
    urls_found = set()
    raw_urls = re.findall(r'https?://[^\s"\']+', text)
    
    for url in raw_urls:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if 's' in params:
            encoded_str = params['s'][0]
            try:
                missing_padding = len(encoded_str) % 4
                if missing_padding:
                    encoded_str += '=' * (4 - missing_padding)
                
                decoded_bytes = base64.b64decode(encoded_str)
                decoded_text = decoded_bytes.decode('utf-8', errors='ignore')
                
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

        if "database disabled" in body or "project disabled" in body:
            return {"url": clean_url, "status": "DEAD", "reason": "Database Disabled"}
        elif "permission denied" in body:
            return {"url": clean_url, "status": "ACTIVE_LOCKED", "reason": "Permission Denied"}
        elif status == 200:
            return {"url": clean_url, "status": "ACTIVE_OPEN", "reason": "Open Read Access"}
        else:
            return {"url": clean_url, "status": "DEAD", "reason": f"HTTP {status}"}
    except Exception:
        return {"url": clean_url, "status": "ERROR", "reason": "Timeout/Network Error"}

# Main Menu UI Keyboard
def main_menu_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📜 View Saved Vault", callback_data="cmd_all"),
        InlineKeyboardButton("📊 Analytics", callback_data="cmd_stats")
    )
    markup.row(
        InlineKeyboardButton("🗑️ Clear Vault", callback_data="cmd_clear"),
        InlineKeyboardButton("⚡ System Info", callback_data="cmd_system")
    )
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_card = (
        "👑 **FIREBASE ENGINE V3.0 (PRO SUITE)** 👑\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Welcome to the high-performance Firebase URL decoder & security inspector.\n\n"
        "💎 **VIP Engine Capabilities:**\n"
        " ├ ⚡ `Auto Base64 URL Extraction`\n"
        " ├ 🔒 `Real-time Security Rule Inspector`\n"
        " ├ 🛡️ `Anti-Duplicate Vault Engine`\n"
        " └ 📊 `Live Database Status Analytics`\n\n"
        "👇 *Use quick action buttons or paste links below:*"
    )
    bot.reply_to(message, welcome_card, parse_mode="Markdown", reply_markup=main_menu_keyboard())

@bot.message_handler(commands=['all'])
def command_all(message):
    render_all_urls(message.chat.id, message)

@bot.message_handler(commands=['clear'])
def command_clear(message):
    clear_user_history(message.chat.id, message)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    if call.data == "cmd_all":
        render_all_urls(chat_id, call.message)
    elif call.data == "cmd_clear":
        clear_user_history(chat_id, call.message)
    elif call.data == "cmd_stats":
        urls = get_user_urls(chat_id)
        open_cnt = sum(1 for _, s in urls if s == "ACTIVE_OPEN")
        locked_cnt = sum(1 for _, s in urls if s == "ACTIVE_LOCKED")
        stats_text = (
            "📊 **VAULT ANALYTICS SUMMARY**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 **Total Stored Databases:** `{len(urls)}`\n"
            f"🟢 **Publicly Open:** `{open_cnt}`\n"
            f"🟡 **Permission Locked:** `{locked_cnt}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ *All entries are de-duplicated & active.*"
        )
        bot.answer_callback_query(call.id, "Analytics Loaded!")
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")
    elif call.data == "cmd_system":
        sys_text = (
            "⚙️ **SYSTEM INFRASTRUCTURE**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🟢 **Server Status:** `ONLINE (Render Web Engine)`\n"
            "⚡ **Worker Daemon:** `Active Polling`\n"
            "🗄️ **Storage Engine:** `SQLite3 Persistent Data`\n"
            "🔒 **Encryption:** `Base64 Auto-Stream Decoder`"
        )
        bot.answer_callback_query(call.id, "System Health OK")
        bot.send_message(chat_id, sys_text, parse_mode="Markdown")

def render_all_urls(chat_id, message_obj):
    urls = get_user_urls(chat_id)
    if not urls:
        bot.send_message(chat_id, "📭 **VAULT IS EMPTY**\n`No active Firebase endpoints stored yet.`", parse_mode="Markdown")
        return

    text = f"💎 **SAVED UNIQUE VAULT LIST ({len(urls)})**\n━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, (u, status) in enumerate(urls, 1):
        badge = "🟢 `[OPEN]`" if status == "ACTIVE_OPEN" else "🟡 `[LOCKED]`"
        text += f"**{idx:02d}.** {badge}\n`{u}`\n\n"

    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            bot.send_message(chat_id, chunk, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, parse_mode="Markdown")

def clear_user_history(chat_id, message_obj):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM active_urls WHERE user_id = ?', (chat_id,))
    conn.commit()
    conn.close()
    bot.send_message(chat_id, "🗑️ **VAULT CLEARED**\n`All stored URLs removed successfully.`", parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "⚠️ **INVALID FILE**\n`Please provide a valid .txt document.`", parse_mode="Markdown")
        return

    msg = bot.reply_to(message, "⚡ **PRO PROCESSING INITIATED**\n`[■■■□□□□□□□] 30% Decoding Payload...`", parse_mode="Markdown")
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_content = downloaded_file.decode('utf-8', errors='ignore')

    urls = extract_and_decode_urls(file_content)
    process_and_respond(message, urls, msg)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    urls = extract_and_decode_urls(message.text)
    if not urls:
        bot.reply_to(message, "❌ **NO TARGET ENDPOINTS DETECTED**\n`Paste valid links or Base64 parameters.`", parse_mode="Markdown")
        return

    msg = bot.reply_to(message, "⚡ **PRO ENGINE RUNNING**\n`[■■■■■■□□□□] 60% Verifying Firebase Endpoints...`", parse_mode="Markdown")
    process_and_respond(message, urls, msg)

def process_and_respond(message, urls, status_msg):
    active_open = 0
    active_locked = 0
    dead_count = 0
    new_added = 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM active_urls WHERE user_id = ?', (message.chat.id,))
    existing_urls = set(row[0] for row in cursor.fetchall())
    conn.close()

    for url in urls:
        if not url.strip():
            continue
        res = check_firebase_status(url)
        if res:
            if "ACTIVE" in res["status"]:
                if res["status"] == "ACTIVE_OPEN":
                    active_open += 1
                else:
                    active_locked += 1

                if res["url"] not in existing_urls:
                    save_active_url(message.chat.id, res["url"], res["status"])
                    existing_urls.add(res["url"])
                    new_added += 1
            else:
                dead_count += 1

    total_checked = active_open + active_locked + dead_count
    timestamp = datetime.now().strftime("%d %b %Y | %I:%M %p")

    response_card = (
        "👑 **EXECUTION EXECUTIVE SUMMARY**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 **Active Open DBs:** `{active_open}`\n"
        f"🟡 **Active Locked DBs:** `{active_locked}`\n"
        f"🔴 **Dead / Offline:** `{dead_count}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ **New Unique Vault Additions:** `{new_added}`\n"
        f"📊 **Total Stream Processed:** `{total_checked}`\n"
        f"⏱️ **Timestamp:** `{timestamp}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 *Use inline control panel below to access Vault.*"
    )

    bot.edit_message_text(response_card, message.chat.id, status_msg.message_id, parse_mode="Markdown", reply_markup=main_menu_keyboard())

def start_polling():
    print(">>> Pro VIP Engine Polling Started <<<", flush=True)
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"Polling error: {e}", flush=True)

t = threading.Thread(target=start_polling, daemon=True)
t.start()

@app.route('/')
def health_check():
    return "VIP Firebase Engine Online!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
