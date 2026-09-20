import os
import re
import json
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Flask Server for Render/Keep-Alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Ultra High-Speed Multi-Firebase Monitor Active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Concurrency Semaphore: Up to 30 requests concurrently
SEMAPHORE = asyncio.Semaphore(30)

async def check_single_firebase_fast(session, firebase_url: str) -> dict:
    clean_url = firebase_url.strip()
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url
    if not clean_url.endswith(".json"):
        clean_url = clean_url.rstrip("/") + "/.json"

    # Strict 3 seconds timeout per link
    timeout = aiohttp.ClientTimeout(total=3.0, connect=1.5)

    async with SEMAPHORE:
        try:
            async with session.get(clean_url, timeout=timeout) as response:
                if response.status in [401, 403]:
                    return {"status": "error", "msg": "🔒 Locked"}
                elif response.status != 200:
                    return {"status": "error", "msg": f"❌ HTTP {response.status}"}
                
                text_data = await response.text()
                if not text_data or text_data == "null":
                    return {"status": "error", "msg": "⚠️ Empty"}

                try:
                    data = json.loads(text_data)
                except Exception:
                    return {"status": "error", "msg": "❌ Invalid Data"}

                online_count = 0
                offline_count = 0
                total_devices = 0

                # Non-recursive fast iterative scanner
                nodes = [data]
                while nodes:
                    curr = nodes.pop()
                    if isinstance(curr, dict):
                        has_status = False
                        for k, v in curr.items():
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
                        nodes.extend(curr.values())
                    elif isinstance(curr, list):
                        nodes.extend(curr)

                if total_devices == 0:
                    return {"status": "error", "msg": "⚠️ No Status Key"}

                return {
                    "status": "ok",
                    "online": online_count,
                    "offline": offline_count,
                    "total": total_devices,
                    "original_url": firebase_url
                }

        except asyncio.TimeoutError:
            return {"status": "error", "msg": "⏱️ Timeout"}
        except Exception:
            return {"status": "error", "msg": "❌ Conn Error"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ **Ultra-Fast Online Firebase Scanner**\n\n"
        "Direct multiple Firebase links bhejien. Check karke bot aapko sirf wahi Firebase links dega jinme devices ONLINE hain!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Extract unique Firebase URLs
    firebase_pattern = r'https://[a-zA-Z0-9\.-]+?\.(?:firebaseio\.com|firebasedatabase\.app)'
    found_urls = re.findall(firebase_pattern, text)
    unique_urls = list(dict.fromkeys(found_urls))

    if not unique_urls:
        await update.message.reply_text("❌ Koi valid Firebase URL nahi mila.")
        return

    status_msg = await update.message.reply_text(f"⚡ **{len(unique_urls)} Firebase links check ho rahe hain...**")

    # High-Performance Async Connection Pool
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_single_firebase_fast(session, url) for url in unique_urls]
        results = await asyncio.gather(*tasks)

    report_lines = []
    online_firebase_links = []
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
            
            report_lines.append(f"**{idx}. {domain_name}** ➔ 🟢 {online} | 🔴 {offline} | 📱 {total}")
            
            # Agar online devices > 0 hain, toh is link ko save kar lo
            if online > 0:
                online_firebase_links.append(url)
        else:
            report_lines.append(f"**{idx}. {domain_name}** ➔ {res['msg']}")

    # Final Combined Output
    final_report = f"📊 **Multi-Firebase Speed Scan Report**\n\n"
    
    formatted_body = "\n".join(report_lines)
    if len(formatted_body) > 2000:
        formatted_body = formatted_body[:2000] + "\n\n...[Truncated due to size limit]"

    final_report += formatted_body
    final_report += (
        f"\n\n-------------------------\n"
        f"🌐 **Overall Totals ({len(unique_urls)} Databases):**\n"
        f"🟢 Total Online: **{total_all_online}**\n"
        f"🔴 Total Offline: **{total_all_offline}**\n"
        f"📱 Total Devices: **{total_all_devices}**"
    )

    # Adding Active/Online Firebase Links Section
    if online_firebase_links:
        final_report += f"\n\n✅ **ACTIVE ONLINE FIREBASE LINKS ({len(online_firebase_links)}):**\n"
        final_report += "\n".join([f"`{link}`" for link in online_firebase_links])
    else:
        final_report += "\n\n⚠️ **Kisi bhi Firebase me Online Device nahi mila.**"

    await status_msg.edit_text(final_report, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Error: BOT_TOKEN Environment Variable nahi mila!")
        return

    Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Ultra-Fast Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
