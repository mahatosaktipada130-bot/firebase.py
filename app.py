import os
import requests
import json
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Render Port Binding ke liye Flask Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Firebase Monitor Bot is Active 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Firebase Data Check karne wala function
def check_firebase_status(firebase_url: str):
    # Ensure correct URL format
    clean_url = firebase_url.strip()
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url
    if not clean_url.endswith(".json"):
        clean_url = clean_url.rstrip("/") + "/.json"

    try:
        response = requests.get(clean_url, timeout=10)
        
        if response.status_code == 401 or response.status_code == 403:
            return "🔒 **Error:** Firebase Database Locked hai (Permission Denied)."
        elif response.status_code != 200:
            return f"❌ **Error:** Firebase request failed (Status: {response.status_code})."
            
        data = response.json()
        
        if data is None:
            return "⚠️ Database bilkul khali (null) hai."

        # Search for online/offline keys in JSON recursively
        online_count = 0
        offline_count = 0
        total_devices = 0

        # Helper function to scan through all keys/nested objects
        def scan_data(obj):
            nonlocal online_count, offline_count, total_devices
            if isinstance(obj, dict):
                # Check for common presence/status keys
                has_status = False
                for k, v in obj.items():
                    if k.lower() in ["status", "state", "presence", "isonline", "online"]:
                        has_status = True
                        val_str = str(v).lower()
                        if val_str in ["online", "true", "1", "active"]:
                            online_count += 1
                        else:
                            offline_count += 1
                        break
                
                if has_status:
                    total_devices += 1
                
                # Continue searching inside child nodes
                for v in obj.values():
                    scan_data(v)
                    
            elif isinstance(obj, list):
                for item in obj:
                    scan_data(item)

        scan_data(data)

        if total_devices == 0:
            return "⚠️ Firebase me koi `status` ya `isOnline` jaisa key nahi mila."

        result_msg = (
            f"📊 **Firebase Device Status Report**\n\n"
            f"🟢 **Online Devices:** {online_count}\n"
            f"🔴 **Offline Devices:** {offline_count}\n"
            f"📱 **Total Devices Found:** {total_devices}"
        )
        return result_msg

    except Exception as e:
        return f"❌ Error: Invalid Firebase URL ya Connection problem."

# Telegram Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hii! Bas mujhe koi bhi Firebase Realtime Database link bhejo, "
        "main count karke bata doonga kitne device Online aur Offline hain."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if "firebaseio.com" in text or "firebasedatabase.app" in text:
        await update.message.reply_text("🔎 Firebase checking in progress...")
        report = check_firebase_status(text)
        await update.message.reply_text(report, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Kripya valid Firebase Realtime Database link bhejein.")

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Error: BOT_TOKEN Environment Variable nahi mila!")
        return

    # Background me Flask start karo
    Thread(target=run_flask, daemon=True).start()

    # Telegram Application
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
