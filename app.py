import os
import re
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Flask Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Ultra-Fast Firebase Monitor Bot Active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Fast Async Firebase Check
async def check_single_firebase_async(session, firebase_url: str) -> dict:
    clean_url = firebase_url.strip()
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url
    if not clean_url.endswith(".json"):
        clean_url = clean_url.rstrip("/") + "/.json"

    # Fast Timeout (4 seconds maximum per link)
    timeout = aiohttp.ClientTimeout(total=4)

    try:
        async with session.get(clean_url, timeout=timeout) as response:
            if response.status in [401, 403]:
                return {"status": "error", "msg": "🔒 Locked (Permission Denied)"}
            elif response.status != 200:
                return {"status": "error", "msg": f"❌ Failed (HTTP {response.status})"}
            
            data = await response.json(content_type=None)
            if data is None:
                return {"status": "error", "msg": "⚠️ Database Empty (null)"}

            online_count = 0
            offline_count = 0
            total_devices = 0

            # Scan data
            def scan_data(obj):
                nonlocal online_count, offline_count, total_devices
                if isinstance(obj, dict):
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
                    
                    for v in obj.values():
                        scan_data(v)
                elif isinstance(obj, list):
                    for item in obj:
                        scan_data(item)

            scan_data(data)

            if total_devices == 0:
                return {"status": "error", "msg": "⚠️ Status keys not found"}

            return {
                "status": "ok",
                "online": online_count,
                "offline": offline_count,
                "total": total_devices
            }

    except asyncio.TimeoutError:
        return {"status": "error", "msg": "⏱️ Request Timeout (Slow Database)"}
    except Exception:
        return {"status": "error", "msg": "❌ Connection Error"}

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ **Super Fast Multi-Firebase Monitor**\n\n"
        "Direct Firebase links bhejien, sabhi ka parallel fast result milega."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    firebase_pattern = r'https://[a-zA-Z0-9\.-]+?\.(?:firebaseio\.com|firebasedatabase\.app)'
    found_urls = re.findall(firebase_pattern, text)
    unique_urls = list(dict.fromkeys(found_urls))

    if not unique_urls:
        await update.message.reply_text("❌ Koi valid Firebase URL nahi mila.")
        return

    status_msg = await update.message.reply_text(f"⚡ **{len(unique_urls)} Firebase links PARALLEL check ho rahe hain...**")

    # Fast Parallel Execution using asyncio.gather
    async with aiohttp.ClientSession() as session:
        tasks = [check_single_firebase_async(session, url) for url in unique_urls]
        results = await asyncio.gather(*tasks)

    report_lines = []
    total_all_online = 0
    total_all_offline = 0
    total_all_devices = 0

    for idx, (url, res) in enumerate(zip(unique_urls, results), 1):
        domain_name = url.split("//")[1].split(".")[0]
        
        if res["status"] == "ok":
            online = res["online"]
            offline = res["offline"]
            total = res["total"]
            
            total_all_online += online
            total_all_offline += offline
            total_all_devices += total
            
            report_lines.append(f"**{idx}. {domain_name}**\n🟢 Online: {online} | 🔴 Offline: {offline} | 📱 Total: {total}")
        else:
            report_lines.append(f"**{idx}. {domain_name}**\n{res['msg']}")

    # Final Combined Report
    final_report = f"📊 **Firebase Fast Summary Report**\n\n"
    final_report += "\n\n".join(report_lines)
    final_report += (
        f"\n\n-------------------------\n"
        f"🌐 **Overall Totals ({len(unique_urls)} Databases):**\n"
        f"🟢 Total Online: **{total_all_online}**\n"
        f"🔴 Total Offline: **{total_all_offline}**\n"
        f"📱 Total Devices: **{total_all_devices}**"
    )

    await status_msg.edit_text(final_report, parse_mode="Markdown")

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Error: BOT_TOKEN Environment Variable nahi mila!")
        return

    Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running fast...")
    application.run_polling()

if __name__ == '__main__':
    main()

