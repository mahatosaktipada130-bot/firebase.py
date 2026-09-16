import base64
from datetime import datetime
import os
import re
import threading
from urllib.parse import parse_qs, urlparse
from flask import Flask
import requests
import telebot
from telebot.types import KeyboardButton, ReplyKeyboardMarkup

app = Flask(__name__)

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "7123456789:AAFg...aapka_real_token_yahan"
)
bot = telebot.TeleBot(BOT_TOKEN)

TXT_FILE = "saved_firebase_vault.txt"


# --- TXT FILE MANAGEMENT FUNCTIONS ---
def save_active_url(user_id, url, status):
  user_id = str(user_id)
  existing_urls = [u for u, _ in get_user_urls(user_id)]

  if url in existing_urls:
    return

  now = datetime.now().strftime("%d %b %Y, %I:%M %p")
  # Format: user_id|status|added_time|url
  line = f"{user_id}|{status}|{now}|{url}\n"

  try:
    with open(TXT_FILE, "a", encoding="utf-8") as f:
      f.write(line)
  except Exception as e:
    print(f"TXT Save Error: {e}", flush=True)


def get_user_urls(user_id):
  user_id = str(user_id)
  if not os.path.exists(TXT_FILE):
    return []

  user_data = []
  try:
    with open(TXT_FILE, "r", encoding="utf-8") as f:
      for line in f:
        parts = line.strip().split("|")
        if len(parts) >= 4 and parts[0] == user_id:
          # returns (url, status)
          user_data.append((parts[3], parts[1]))
  except Exception as e:
    print(f"TXT Read Error: {e}", flush=True)

  return user_data


def clear_user_history(chat_id, message_obj):
  user_id = str(chat_id)
  if not os.path.exists(TXT_FILE):
    return

  try:
    with open(TXT_FILE, "r", encoding="utf-8") as f:
      lines = f.readlines()

    with open(TXT_FILE, "w", encoding="utf-8") as f:
      for line in lines:
        parts = line.strip().split("|")
        if len(parts) >= 1 and parts[0] != user_id:
          f.write(line)

    bot.send_message(
        chat_id,
        "🗑️ **VAULT CLEARED**\n`All stored URLs removed successfully.`",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
  except Exception as e:
    print(f"TXT Clear Error: {e}", flush=True)


# --- CORE LOGIC & TELEGRAM HANDLERS ---
def extract_and_decode_urls(text):
  urls_found = set()
  raw_urls = re.findall(r'https?://[^\s"\']+', text)

  for url in raw_urls:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if "s" in params:
      encoded_str = params["s"][0]
      try:
        missing_padding = len(encoded_str) % 4
        if missing_padding:
          encoded_str += "=" * (4 - missing_padding)

        decoded_bytes = base64.b64decode(encoded_str)
        decoded_text = decoded_bytes.decode("utf-8", errors="ignore")

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
      return {
          "url": clean_url,
          "status": "ACTIVE_LOCKED",
          "reason": "Permission Denied",
      }
    elif status == 200:
      return {
          "url": clean_url,
          "status": "ACTIVE_OPEN",
          "reason": "Open Read Access",
      }
    else:
      return {"url": clean_url, "status": "DEAD", "reason": f"HTTP {status}"}
  except Exception:
    return {
        "url": clean_url,
        "status": "ERROR",
        "reason": "Timeout/Network Error",
    }


def main_menu_keyboard():
  markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn_vault = KeyboardButton("📜 View Saved Vault")
  btn_analytics = KeyboardButton("📊 Analytics")
  btn_clear = KeyboardButton("🗑️ Clear Vault")
  btn_system = KeyboardButton("⚡ System Info")

  markup.add(btn_vault, btn_analytics)
  markup.add(btn_clear, btn_system)
  return markup


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  welcome_card = (
      "👑 **FIREBASE ENGINE V3.0 (PRO SUITE)** 👑\n"
      "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
      "Welcome to the high-performance Firebase URL decoder & security"
      " inspector.\n\n"
      "💎 **VIP Engine Capabilities:**\n"
      " ├ ⚡ `Auto Base64 URL Extraction`\n"
      " ├ 🔒 `Real-time Security Rule Inspector`\n"
      " ├ 🛡️ `Anti-Duplicate Vault Engine`\n"
      " └ 📊 `Live Database Status Analytics`\n\n"
      "👇 *Use bottom keyboard buttons or paste links below:*"
  )
  bot.reply_to(
      message,
      welcome_card,
      parse_mode="Markdown",
      reply_markup=main_menu_keyboard(),
  )


@bot.message_handler(
    func=lambda message: message.text
    in [
        "📜 View Saved Vault",
        "📊 Analytics",
        "🗑️ Clear Vault",
        "⚡ System Info",
    ]
)
def handle_keyboard_buttons(message):
  chat_id = message.chat.id
  text = message.text

  if text == "📜 View Saved Vault":
    render_all_urls(chat_id, message)
  elif text == "🗑️ Clear Vault":
    clear_user_history(chat_id, message)
  elif text == "📊 Analytics":
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
    bot.send_message(
        chat_id,
        stats_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
  elif text == "⚡ System Info":
    sys_text = (
        "⚙️ **SYSTEM INFRASTRUCTURE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 **Server Status:** `ONLINE (TXT Database Active)`\n"
        "⚡ **Worker Daemon:** `Active Polling`\n"
        "🗄️ **Storage Engine:** `Plain-Text (TXT) Vault`\n"
        "🔒 **Encryption:** `Base64 Auto-Stream Decoder`"
    )
    bot.send_message(
        chat_id,
        sys_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


@bot.message_handler(commands=["all"])
def command_all(message):
  render_all_urls(message.chat.id, message)


@bot.message_handler(commands=["clear"])
def command_clear(message):
  clear_user_history(message.chat.id, message)


def render_all_urls(chat_id, message_obj):
  urls = get_user_urls(chat_id)
  if not urls:
    bot.send_message(
        chat_id,
        (
            "📭 **VAULT IS EMPTY**\n`No active Firebase endpoints stored"
            " yet.`"
        ),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return

  text = (
      f"💎 **SAVED UNIQUE VAULT LIST ({len(urls)})**\n"
      "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
  )
  for idx, (u, status) in enumerate(urls, 1):
    badge = "🟢 `[OPEN]`" if status == "ACTIVE_OPEN" else "🟡 `[LOCKED]`"
    text += f"**{idx:02d}.** {badge}\n`{u}`\n\n"

  if len(text) > 4000:
    for chunk in [text[i : i + 4000] for i in range(0, len(text), 4000)]:
      bot.send_message(
          chat_id,
          chunk,
          parse_mode="Markdown",
          reply_markup=main_menu_keyboard(),
      )
  else:
    bot.send_message(
        chat_id, text, parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )


@bot.message_handler(content_types=["document"])
def handle_docs(message):
  if not message.document.file_name.endswith(".txt"):
    bot.reply_to(
        message,
        "⚠️ **INVALID FILE**\n`Please provide a valid .txt document.`",
        parse_mode="Markdown",
    )
    return

  msg = bot.reply_to(
      message,
      "⚡ **PRO PROCESSING INITIATED**\n`[■■■□□□□□□□] 30% Decoding Payload...`",
      parse_mode="Markdown",
  )

  file_info = bot.get_file(message.document.file_id)
  downloaded_file = bot.download_file(file_info.file_path)
  file_content = downloaded_file.decode("utf-8", errors="ignore")

  urls = extract_and_decode_urls(file_content)
  process_and_respond(message, urls, msg)


@bot.message_handler(func=lambda message: True)
def handle_text(message):
  urls = extract_and_decode_urls(message.text)
  if not urls:
    bot.reply_to(
        message,
        (
            "❌ **NO TARGET ENDPOINTS DETECTED**\n`Paste valid links or Base64"
            " parameters.`"
        ),
        parse_mode="Markdown",
    )
    return

  msg = bot.reply_to(
      message,
      "⚡ **PRO ENGINE RUNNING**\n`[■■■■■■□□□□] 60% Verifying Firebase"
      " Endpoints...`",
      parse_mode="Markdown",
  )
  process_and_respond(message, urls, msg)


def process_and_respond(message, urls, status_msg):
  active_open = 0
  active_locked = 0
  dead_count = 0
  new_added = 0

  existing_urls = set(u for u, _ in get_user_urls(message.chat.id))

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
      "💎 *Use keyboard panel below to access Vault.*"
  )

  bot.edit_message_text(
      response_card,
      message.chat.id,
      status_msg.message_id,
      parse_mode="Markdown",
  )
  bot.send_message(
      message.chat.id,
      "👇 **Control Panel Ready:**",
      reply_markup=main_menu_keyboard(),
  )


def start_polling():
  print(">>> Pro VIP Engine Polling Started <<<", flush=True)
  try:
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
  except Exception as e:
    print(f"Polling error: {e}", flush=True)


t = threading.Thread(target=start_polling, daemon=True)
t.start()


@app.route("/")
def health_check():
  return "VIP Firebase Engine Online!"


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)

