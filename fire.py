# ====================================================
#          👑  Rᴜsʜᴇʀ Kɪɴɢ  👑  •  ᴜʟᴛʀᴀ ꜰʀᴇᴇ ʜᴏsᴛɪɴɢ v5.3
# ====================================================

import os
import sys
import sqlite3
import subprocess
import time
import random
import string
import threading
import re
import signal
import html as html_mod
from datetime import datetime, timedelta
from telebot import TeleBot, types
from flask import Flask

# ==================== FLASK SERVER (24/7 UPTIME) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "👑 Rusher King Hosting Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# Start Flask in background thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# ==================== CONFIGURATIONS ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8959750104:AAHw7JF8ZoaCiU3NCGvtoWyDCY9K18YRveI")
OWNER_NAME = "👑  Rᴜsʜᴇʀ Kɪɴɢ  👑"
HOST_DIR = "hosted_files"
MAX_LOG_SIZE_MB = 5

config = {
    "brand_name": "PRIME HOSTING SERVER",
    "max_limit": 50, # Totally free & high limit for everyone
}

os.makedirs(HOST_DIR, exist_ok=True)
bot = TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

# ==================== DATABASE ====================
def get_db():
    conn = sqlite3.connect("hosting_data.db", check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosted_bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            filepath TEXT,
            logpath TEXT,
            pid INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'stopped',
            auto_guard INTEGER DEFAULT 1,
            created_at TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==================== HELPERS ====================
def register_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def send_typing(chat_id):
    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

def is_process_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def safe_popen(filepath, logpath):
    log_file = open(logpath, 'a', encoding='utf-8')
    log_file.write(f"\n--- [STARTED {datetime.now()}] ---\n")
    log_file.flush()
    cmd = [sys.executable, "-u", filepath]
    cwd = os.path.dirname(filepath) or "."
    try:
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, cwd=cwd, start_new_session=True)
    except Exception:
        try: log_file.close()
        except Exception: pass
        log_file = open(logpath, 'a', encoding='utf-8')
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, cwd=cwd)
    return proc

def safe_kill(pid):
    if not pid or not is_process_alive(pid):
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        time.sleep(0.3)
        if is_process_alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try: os.kill(pid, 9)
        except Exception: pass

# ==================== AUTO PIP INSTALLER ====================
def extract_imports(filepath):
    packages = set()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        for match in re.finditer(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE):
            pkg = match.group(1).split('.')[0]
            stdlib = {'os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random', 'string', 'threading', 'subprocess', 'sqlite3', 'logging', 'collections', 'functools', 'itertools', 'pathlib', 'shutil', 'urllib', 'http', 'socket', 'ssl', 'hashlib', 'base64', 'typing', 'asyncio', 'queue', 'signal', 'flask'}
            if pkg and pkg not in stdlib and not pkg.startswith('_'):
                packages.add(pkg)
    except Exception:
        pass
    return packages

def auto_install_packages(filepath, logpath):
    packages = extract_imports(filepath)
    if not packages:
        return []
    installed = []
    name_map = {'telebot': 'pyTelegramBotAPI', 'telegram': 'python-telegram-bot', 'PIL': 'Pillow', 'cv2': 'opencv-python', 'bs4': 'beautifulsoup4', 'yaml': 'PyYAML', 'dotenv': 'python-dotenv', 'requests': 'requests', 'aiohttp': 'aiohttp', 'flask': 'flask', 'fastapi': 'fastapi', 'uvicorn': 'uvicorn', 'numpy': 'numpy', 'pandas': 'pandas'}
    with open(logpath, 'a', encoding='utf-8') as log:
        log.write(f"\n--- [AUTO-PIP START {datetime.now()}] ---\n")
        for pkg in packages:
            pip_name = name_map.get(pkg, pkg)
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir", pip_name], capture_output=True, text=True, timeout=60)
                installed.append(pip_name)
            except Exception:
                pass
    return installed

# ==================== CRASH GUARD ====================
def crash_guard_worker():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hosted_bots WHERE status = 'running'")
            running_bots = cursor.fetchall()
            for b in running_bots:
                if not is_process_alive(b['pid']):
                    try:
                        proc = safe_popen(b['filepath'], b['logpath'])
                        cursor.execute("UPDATE hosted_bots SET pid = ? WHERE id = ?", (proc.pid, b['id']))
                        conn.commit()
                    except Exception:
                        cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (b['id'],))
                        conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(10)

threading.Thread(target=crash_guard_worker, daemon=True).start()

# ==================== KEYBOARDS ====================
def main_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, row_width=2)
    markup.row(types.KeyboardButton("🚀 Upload Bot"), types.KeyboardButton("📦 My Bots"))
    markup.row(types.KeyboardButton("🖥️ Server Status"), types.KeyboardButton("❓ Help"))
    return markup

def bot_control_keyboard(bot_id, running):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if running:
        markup.add(types.InlineKeyboardButton("🔴 Stop", callback_data=f"stopbot_{bot_id}"),
                   types.InlineKeyboardButton("📜 Logs", callback_data=f"logbot_{bot_id}"))
    else:
        markup.add(types.InlineKeyboardButton("🟢 Start", callback_data=f"startbot_{bot_id}"),
                   types.InlineKeyboardButton("📜 Logs", callback_data=f"logbot_{bot_id}"))
    markup.add(types.InlineKeyboardButton("🧹 Clear Logs", callback_data=f"clearlog_{bot_id}"),
               types.InlineKeyboardButton("🗑️ Delete", callback_data=f"delbot_{bot_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Back to My Bots", callback_data="my_bots"))
    return markup

# ==================== HANDLERS ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    register_user(user_id)
    send_typing(message.chat.id)
    
    welcome_text = (
        f"✨ **{config['brand_name']}** ✨\n"
        f"👑 **{OWNER_NAME}** • Ultra Fast Hosting\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Welcome, **{message.from_user.first_name}**!\n"
        f"🚀 Bot hosting is now **100% FREE** with unlimited fast execution and Flask Web Server support.\n\n"
        f"👇 Use the buttons below to manage your bots:"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=main_reply_keyboard())

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    register_user(user_id)
    send_typing(message.chat.id)

    if not message.document.file_name or not message.document.file_name.lower().endswith('.py'):
        bot.reply_to(message, "❌ Only `.py` Python files are allowed.")
        return

    filename = message.document.file_name
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    user_dir = os.path.join(os.getcwd(), HOST_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    filepath = os.path.join(user_dir, filename)
    logpath = filepath + ".log"

    with open(filepath, 'wb') as f:
        f.write(downloaded)

    with open(logpath, 'w', encoding='utf-8') as f:
        f.write(f"--- [UPLOADED {datetime.now()}] Ready ---\n")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO hosted_bots (user_id, filename, filepath, logpath, status, created_at) VALUES (?, ?, ?, ?, 'stopped', ?)",
        (user_id, filename, filepath, logpath, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    # Instant auto-install requirements
    auto_install_packages(filepath, logpath)

    bot.reply_to(
        message,
        f"✅ **File Uploaded Successfully!**\n\n"
        f"📄 File: `{filename}`\n"
        f"🚀 No approval required. Go to **My Bots** to start your bot instantly!",
        parse_mode="Markdown",
        reply_markup=main_reply_keyboard()
    )

@bot.message_handler(func=lambda m: m.text in {"🚀 Upload Bot", "📦 My Bots", "🖥️ Server Status", "❓ Help"})
def menu_handler(message):
    user_id = message.from_user.id
    text = message.text
    send_typing(message.chat.id)

    if text == "🚀 Upload Bot":
        bot.send_message(message.chat.id, "📥 Send your `.py` script file directly in this chat to host it instantly.", parse_mode="Markdown")
    elif text == "📦 My Bots":
        show_my_bots(message.chat.id, user_id)
    elif text == "🖥️ Server Status":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM hosted_bots")
        total = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as running FROM hosted_bots WHERE status='running'")
        running = cursor.fetchone()['running']
        conn.close()
        bot.send_message(message.chat.id, f"🖥️ **Server Status**\n━━━━━━━━━━━━━━━━━━━━\n🤖 Total Bots: `{total}`\n🟢 Running: `{running}`", parse_mode="Markdown")
    elif text == "❓ Help":
        bot.send_message(message.chat.id, "❓ **Help Guide**\n1. Upload any Python `.py` script.\n2. Go to **My Bots**.\n3. Click **Start** to run your bot 24/7 with Flask web backing.", parse_mode="Markdown")

def show_my_bots(chat_id, user_id, message_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE user_id = ? ORDER BY id DESC", (user_id,))
    bots = cursor.fetchall()
    conn.close()

    if not bots:
        bot.send_message(chat_id, "❌ You haven't uploaded any bots yet.", reply_markup=main_reply_keyboard())
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for b in bots:
        running = b['status'] == 'running' and b['pid'] and is_process_alive(b['pid'])
        icon = "🟢" if running else "🔴"
        markup.add(types.InlineKeyboardButton(f"{icon} {b['filename']}", callback_data=f"manage_{b['id']}"))

    if message_id:
        try:
            bot.edit_message_text("📦 **Your Hosted Bots:**", chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, "📦 **Your Hosted Bots:**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data

    if data == "my_bots":
        show_my_bots(chat_id, user_id, msg_id)
        return

    if data.startswith("manage_"):
        bot_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
        b = cursor.fetchone()
        conn.close()
        if not b:
            return
        running = b['status'] == 'running' and b['pid'] and is_process_alive(b['pid'])
        status_text = "🟢 Running" if running else "🔴 Stopped"
        text = f"🤖 **Bot Control Panel**\n━━━━━━━━━━━━━━━━━━━━\n📄 File: `{b['filename']}`\n📊 Status: {status_text}"
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown", reply_markup=bot_control_keyboard(bot_id, running))

    elif data.startswith("startbot_"):
        bot_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
        b = cursor.fetchone()
        if b:
            proc = safe_popen(b['filepath'], b['logpath'])
            cursor.execute("UPDATE hosted_bots SET status = 'running', pid = ? WHERE id = ?", (proc.pid, bot_id))
            conn.commit()
        conn.close()
        call.data = f"manage_{bot_id}"
        callbacks(call)

    elif data.startswith("stopbot_"):
        bot_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
        b = cursor.fetchone()
        if b and b['pid']:
            safe_kill(b['pid'])
            cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
            conn.commit()
        conn.close()
        call.data = f"manage_{bot_id}"
        callbacks(call)

    elif data.startswith("logbot_"):
        bot_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
        b = cursor.fetchone()
        conn.close()
        if not b or not os.path.exists(b['logpath']):
            bot.answer_callback_query(call.id, "Logs not found.")
            return
        with open(b['logpath'], 'r', encoding='utf-8', errors='ignore') as f:
            logs = "".join(f.readlines()[-30:]).strip() or "No logs available."
        if len(logs) > 3500: logs = logs[-3500:]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"logbot_{bot_id}"),
                   types.InlineKeyboardButton("🔙 Back", callback_data=f"manage_{bot_id}"))
        bot.edit_message_text(f"📜 **Live Logs:**\n```\n{logs}\n```", chat_id, msg_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("clearlog_"):
        bot_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT logpath FROM hosted_bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
        b = cursor.fetchone()
        conn.close()
        if b and os.path.exists(b['logpath']):
            with open(b['logpath'], 'w', encoding='utf-8') as f:
                f.write(f"--- [LOG CLEARED {datetime.now()}] ---\n")
        call.data = f"logbot_{bot_id}"
        callbacks(call)

    elif data.startswith("delbot_"):
        bot_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND user_id = ?", (bot_id, user_id))
        b = cursor.fetchone()
        if b:
            if b['pid']: safe_kill(b['pid'])
            for p in [b['filepath'], b['logpath']]:
                if p and os.path.exists(p): os.remove(p)
            cursor.execute("DELETE FROM hosted_bots WHERE id = ?", (bot_id,))
            conn.commit()
        conn.close()
        show_my_bots(chat_id, user_id, msg_id)

# ==================== RUN BOT ====================
if __name__ == '__main__':
    print(f"👑 {OWNER_NAME} - Ultra Free Hosting v5.3 Started Successfully!")
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=10)
