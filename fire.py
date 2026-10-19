import os
import re
import asyncio
import httpx
import urllib.parse
import time
import base64
import json
import tempfile
import zipfile
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = "8430586261:AAEFV7l7yBWPVRLxRZa64VQVWzzCUT1GrK4"
TG_GATEWAY = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

ADMIN_IDS = []

ADMIN_LOGS = []
LOG_LOCK = asyncio.Lock()
USERS_FILE = "bot_users.json"

# Font conversion helper for Rusher style (Small Caps)
def to_rusher_font(text):
    normal = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    small_caps = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡ🇽🇾ᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡ🇽🇾ᴢ"
    # Mapping table for lowercase & uppercase small caps
    trans_table = str.maketrans(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    )
    return text.translate(trans_table)

# Smart formatting function to apply Rusher font ONLY to normal text, leaving HTML tags and code blocks untouched
def format_reply(text):
    # Split text by HTML tags to avoid modifying tags or code contents
    parts = re.split(r'(</?[^>]+>)', text)
    formatted_parts = []
    in_code = False
    
    for part in parts:
        if part.startswith('<code') or part.startswith('<pre'):
            in_code = True
            formatted_parts.append(part)
        elif part.startswith('</code>') or part.startswith('</pre>'):
            in_code = False
            formatted_parts.append(part)
        elif in_code or part.startswith('<'):
            formatted_parts.append(part)
        else:
            formatted_parts.append(to_rusher_font(part))
            
    return "".join(formatted_parts)

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        try:
            with open(USERS_FILE, "w") as f:
                json.dump(list(users), f)
        except:
            pass

async def send_message_raw(chat_id, text, reply_markup=None):
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "text": format_reply(text),
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            await client.post(f"{TG_GATEWAY}/sendMessage", json=payload, timeout=8)
    except Exception:
        pass

async def parse_panel_data(client_session, firebase_url):
    try:
        base_clean = firebase_url.strip().rstrip('/')
        target_endpoint = f"{base_clean}/.json" if not base_clean.endswith(".json") else base_clean
            
        response = await client_session.get(target_endpoint, timeout=2.5)
        if response.status_code == 200:
            data = response.json()
            if not isinstance(data, dict):
                return 0, 0

            clients_node = data.get("clients", data)
            total_devices = 0
            online_devices = 0

            if isinstance(clients_node, dict):
                for client_id, client_info in clients_node.items():
                    if isinstance(client_info, dict):
                        total_devices += 1
                        status = client_info.get("status")
                        if status is True or status == "Online" or status == "online":
                            online_devices += 1

            return total_devices, online_devices
        return 0, 0
    except Exception:
        return 0, 0

async def parse_batch_panels(database_urls):
    semaphore = asyncio.Semaphore(40)
    limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
    
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        async def bounded_fetch(db_url):
            async with semaphore:
                total, online = await parse_panel_data(client, db_url)
                return db_url, total, online
        
        tasks = [bounded_fetch(url) for url in database_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        parsed_results = []
        for res in results:
            if isinstance(res, tuple):
                parsed_results.append(res)
        return parsed_results

def extract_firebase_from_vercel_link(link_str):
    extracted_dbs = set()
    try:
        link_str = link_str.strip()
        
        if "?" in link_str:
            parsed = urllib.parse.urlparse(link_str)
            qs = urllib.parse.parse_qs(parsed.query)
            for param_key in ['s', 'm', 'data', 'q']:
                if param_key in qs:
                    for val in qs[param_key]:
                        extracted_dbs.update(extract_firebase_from_vercel_link(val))
                        
        candidate = link_str
        for modifier in [lambda x: x, lambda x: x + '==', lambda x: x.replace('-', '+').replace('_', '/')]:
            try:
                mod_str = modifier(candidate)
                padding_needed = len(mod_str) % 4
                if padding_needed:
                    mod_str += "=" * (4 - padding_needed)
                decoded_bytes = base64.b64decode(mod_str)
                decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
                
                if decoded_str.startswith("MERGED:::") or decoded_str.startswith("[") or "{" in decoded_str:
                    clean_json_str = decoded_str.replace("MERGED:::", "")
                    try:
                        data_json = json.loads(clean_json_str)
                        if isinstance(data_json, list):
                            for item in data_json:
                                if isinstance(item, dict):
                                    for sub_val in item.values():
                                        if isinstance(sub_val, str) and ("firebaseio.com" in sub_val or "firebasedatabase.app" in sub_val or "-default-rtdb" in sub_val):
                                            extracted_dbs.add(sub_val.strip())
                        elif isinstance(data_json, dict):
                            for sub_val in data_json.values():
                                if isinstance(sub_val, str) and ("firebaseio.com" in sub_val or "firebasedatabase.app" in sub_val or "-default-rtdb" in sub_val):
                                    extracted_dbs.add(sub_val.strip())
                    except:
                        pass
                
                parts = decoded_str.split('|||')
                for p in parts:
                    sub_p = p.split('|')
                    for sp in sub_p:
                        sp_clean = sp.strip()
                        if "firebaseio.com" in sp_clean or "firebasedatabase.app" in sp_clean or "-default-rtdb" in sp_clean:
                            extracted_dbs.add(sp_clean)
                        elif sp_clean.startswith("http"):
                            extracted_dbs.add(sp_clean)
                            
                if "firebaseio.com" in decoded_str or "firebasedatabase.app" in decoded_str:
                    matches = re.findall(r'https?://[a-zA-Z0-9_.-]+(?:firebaseio\.com|firebasedatabase\.app)', decoded_str)
                    for m in matches:
                        extracted_dbs.add(m)
            except:
                pass

        if "firebaseio.com" in link_str or "firebasedatabase.app" in link_str or "-default-rtdb" in link_str:
            matches = re.findall(r'https?://[a-zA-Z0-9_.-]+(?:firebaseio\.com|firebasedatabase\.app)', link_str)
            if matches:
                for m in matches:
                    extracted_dbs.add(m)
            else:
                extracted_dbs.add(link_str)

    except:
        pass
        
    return list(extracted_dbs) if extracted_dbs else [link_str]

def generate_vercel_link(db_url):
    clean_db = db_url.strip().strip('/')
    if not clean_db.startswith("http"):
        clean_db = "https://" + clean_db
        
    future_timestamp = str(int(time.time() * 1000) + 31536000000)
    raw_payload = f"{clean_db}|||yadavji|||{future_timestamp}"
    encoded_payload = base64.b64encode(raw_payload.encode('utf-8')).decode('utf-8')
    return f"https://cyber-core-seven.vercel.app/?s={encoded_payload}"

def extract_urls_from_binary(data_bytes: bytes) -> set:
    found = set()
    try:
        text = data_bytes.decode('utf-8', errors='ignore') if isinstance(data_bytes, bytes) else str(data_bytes)
    except:
        text = str(data_bytes)

    matches = re.findall(r'https?://[a-zA-Z0-9_.-]+(?:firebaseio\.com|firebasedatabase\.app)', text)
    for m in matches:
        if "your-project" not in m:
            found.add(m)

    domains = re.findall(r'[a-zA-Z0-9_-]+-default-rtdb\.[a-z0-9.-]+', text)
    for d in domains:
        if not d.startswith("http"):
            d = "https://" + d
        if "your-project" not in d:
            found.add(d)
            
    return found

def extract_firebase_from_apk(file_path: str) -> tuple:
    found_databases = set()
    try:
        with zipfile.ZipFile(file_path, 'r') as apk_zip:
            for filename in apk_zip.namelist():
                try:
                    file_data = apk_zip.read(filename)
                    found_databases.update(extract_urls_from_binary(file_data))
                except:
                    pass
        
        resolved_list = []
        for db in found_databases:
            unpacked = extract_firebase_from_vercel_link(db)
            resolved_list.extend(unpacked)
        resolved_set = list(set(resolved_list))[:2000]
        
        if resolved_set:
            result_text = f"📦 <b>Lightning APK Scan Successful!</b>\n\n<b>Found Databases ({len(resolved_set)}):</b>\n"
            for idx, db_url in enumerate(resolved_set, 1):
                vercel_url = generate_vercel_link(db_url)
                result_text += f"\n{idx}. <code>{db_url}</code>\n\n🔗 <b>Cyber Core Panel Link:</b>\n{vercel_url}\n\n"
            result_text += "🛡️ <b>Developed by Cyber Core System</b>"
            return format_reply(result_text), resolved_set
        else:
            return format_reply("⚠️ No Firebase database URL resolved.\n\n🛡️ <b>Developed by Cyber Core System</b>"), []
    except Exception as e:
        return format_reply(f"❌ Error: <code>{str(e)}</code>\n\n🛡️ <b>Developed by Cyber Core System</b>"), []

async def extract_firebase_from_url(target_url: str) -> tuple:
    headers = {"User-Agent": "Mozilla/5.0"}
    found_databases = set()

    unpacked_urls = extract_firebase_from_vercel_link(target_url)
    for u in unpacked_urls:
        if "firebaseio.com" in u or "firebasedatabase.app" in u or "-default-rtdb" in u:
            found_databases.add(u)
        
    try:
        if not target_url.startswith("http"):
            target_url = "https://" + target_url
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(target_url, headers=headers, timeout=4)
            found_databases.update(extract_urls_from_binary(response.content))
            extra_unpacked = extract_firebase_from_vercel_link(response.text)
            for eu in extra_unpacked:
                if "firebaseio.com" in eu or "firebasedatabase.app" in eu or "-default-rtdb" in eu:
                    found_databases.add(eu)
                
        final_dbs = list(found_databases)[:2000]
        if final_dbs:
            batch_results = await parse_batch_panels(final_dbs)
            result_text = f"⚡ <b>Lightning Scanned Successfully!</b>\n🌐 Target: <code>{target_url}</code>\n\n<b>Found Databases ({len(final_dbs)}):</b>\n"
            for idx, (db_url, total, online) in enumerate(batch_results, 1):
                vercel_url = generate_vercel_link(db_url)
                result_text += f"\n{idx}. <code>{db_url}</code>\n📦 <b>Total:</b> <code>{total}</code> | 🟢 <b>Online:</b> <code>{online}</code>\n\n🔗 <b>Cyber Core Panel Link:</b>\n{vercel_url}\n\n"
            result_text += "🛡️ <b>Developed by Cyber Core System</b>"
            return format_reply(result_text), final_dbs
        else:
            return format_reply("⚠️ No Firebase URL found.\n\n🛡️ <b>Developed by Cyber Core System</b>"), []
    except Exception as err:
        if found_databases:
            final_dbs = list(found_databases)[:2000]
            batch_results = await parse_batch_panels(final_dbs)
            result_text = f"⚡ <b>Parsed from Link Payload!</b>\n\n<b>Found Databases ({len(final_dbs)}):</b>\n"
            for idx, (db_url, total, online) in enumerate(batch_results, 1):
                vercel_url = generate_vercel_link(db_url)
                result_text += f"\n{idx}. <code>{db_url}</code>\n📦 <b>Total:</b> <code>{total}</code> | 🟢 <b>Online:</b> <code>{online}</code>\n\n🔗 <b>Cyber Core Panel Link:</b>\n{vercel_url}\n\n"
            result_text += "🛡️ <b>Developed by Cyber Core System</b>"
            return format_reply(result_text), final_dbs
        return format_reply(f"❌ Error: <code>{str(err)}</code>\n\n🛡️ <b>Developed by Cyber Core System</b>"), []

async def download_telegram_file(file_id: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{TG_GATEWAY}/getFile", params={"file_id": file_id}, timeout=10)
            file_path_info = res.json().get("result", {}).get("file_path")
            if not file_path_info:
                return None
            download_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path_info}"
            file_resp = await client.get(download_url, timeout=30)
            temp_file = os.path.join(tempfile.gettempdir(), f"target_cyber_{time.time()}.tmp")
            with open(temp_file, "wb") as f:
                f.write(file_resp.content)
            return temp_file
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚡ *Cyber Core High-Speed Bot* 🚀\n"
        "👋 Welcome! Send panel link, raw Firebase URL, bulk list, or `.txt` file..\n\n"
        "_🛡️ Developed by Cyber Core System_"
    )
    await update.message.reply_text(format_reply(text), parse_mode="Markdown")

async def handle_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    chat_id = msg.chat_id
    await send_message_raw(chat_id, "📊 <b>Export Feature:</b> Sabhi ke liye free aur open hai!\n\n🛡️ <b>Developed by Cyber Core System</b>")

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
        
    chat_id = msg.chat_id
    user = msg.from_user
    user_id = user.id if user else 0
    
    save_user(user_id)

    if msg.text:
        txt = msg.text.strip()
        if txt.startswith("/export"):
            await handle_export_command(update, context)
            return
            
        raw_items = []
        if "," in txt:
            raw_items = [item.strip() for item in txt.split(",") if item.strip()]
        else:
            raw_items = txt.splitlines()
            
        all_target_dbs = []
        for line in raw_items:
            line = line.strip()
            if not line:
                continue
            match = re.search(r'https?://[^\s]+', line)
            target_url = match.group(0) if match else line
            
            unpacked_dbs = extract_firebase_from_vercel_link(target_url)
            valid_dbs = [db for db in unpacked_dbs if "firebaseio.com" in db or "firebasedatabase.app" in db or "-default-rtdb" in db]
            all_target_dbs.extend(valid_dbs)

        seen = set()
        unique_target_dbs = [x for x in all_target_dbs if not (x in seen or seen.add(x))][:2000]

        if len(unique_target_dbs) > 1:
            status_msg = await msg.reply_text(format_reply(f"⚡ High-Speed Bulk Processing ({len(unique_target_dbs)} Firebase URLs)..."), parse_mode="HTML")
            
            batch_outputs = await parse_batch_panels(unique_target_dbs)

            report = f"⚡ <b>High-Speed Bulk Scan Report (Total: {len(unique_target_dbs)})</b>\n\n"
            for idx, (db_url, total, online) in enumerate(batch_outputs, 1):
                vercel_url = generate_vercel_link(db_url)
                report += f"<b>{idx}.</b> <code>{db_url}</code>\n📦 Total: <code>{total}</code> | 🟢 Online: <code>{online}</code>\n🔗 Panel: {vercel_url}\n\n"

            report += "🛡️ <b>Developed by Cyber Core System</b>"

            if len(report) > 4000:
                file_path = os.path.join(tempfile.gettempdir(), f"Bulk_Scan_Report_{time.time()}.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    clean_export = report.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
                    f.write(clean_export)
                await status_msg.edit_text(format_reply(f"⚡ <b>Bulk Scan Complete!</b>\n🔥 Processed Databases: <code>{len(unique_target_dbs)}</code>\n\n📄 Detailed results attached below.\n\n🛡️ <b>Developed by Cyber Core System</b>"), parse_mode="HTML")
                await context.bot.send_document(chat_id=chat_id, document=open(file_path, "rb"), caption=format_reply("📁 <b>Full Bulk Scan Report</b>"), parse_mode="HTML")
                try: os.remove(file_path)
                except: pass
            else:
                await status_msg.edit_text(format_reply(report), parse_mode="HTML", disable_web_page_preview=True)
            
        elif len(unique_target_dbs) == 1:
            clean_target = unique_target_dbs[0]
            status_msg = await msg.reply_text(format_reply(f"⚡ Fast Checking: `{clean_target}`..."), parse_mode="HTML")
            async with httpx.AsyncClient() as client:
                total, online = await parse_panel_data(client, clean_target)
            node_name = clean_target.split('//')[-1].split('-')[0]
            vercel_url = generate_vercel_link(clean_target)

            report = (
                f"⚡ <b>Lightning Status & Extractor Report</b>\n"
                f"🌐 <b>Node:</b> <code>{node_name}</code>\n\n"
                f"🔥 <b>Firebase URL:</b>\n<code>{clean_target}</code>\n\n"
                f"📦 <b>Total Devices:</b> <code>{total}</code>\n"
                f"🟢 <b>Online Devices:</b> <code>{online}</code>\n\n"
                f"🔗 <b>Cyber Core Panel Link:</b>\n{vercel_url}\n\n"
                f"🛡️ <b>Developed by Cyber Core System</b>"
            )
            await status_msg.edit_text(format_reply(report), parse_mode="HTML", disable_web_page_preview=True)
        else:
            for line in raw_items:
                line = line.strip()
                if not line:
                    continue
                match = re.search(r'https?://[^\s]+', line)
                target_url = match.group(0) if match else line
                status_msg = await msg.reply_text(format_reply("⚡ Unpacking & Scanning Mixed Panel Payload..."), parse_mode="HTML")
                scan_res, found_dbs = await extract_firebase_from_url(target_url)
                await status_msg.edit_text(scan_res, parse_mode="HTML", disable_web_page_preview=True)

    elif msg.document:
        doc = msg.document
        file_name = doc.file_name or "unknown"
        status_msg = await msg.reply_text(format_reply("⚡ <b>Processing Uploaded File...</b>"), parse_mode="HTML")
        file_path = await download_telegram_file(doc.file_id)
        
        if file_path:
            try:
                is_text_file = False
                file_content = ""
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                    if "firebaseio.com" in file_content or "firebasedatabase.app" in file_content or "-default-rtdb" in file_content or "\n" in file_content:
                        is_text_file = True
                except:
                    pass

                if is_text_file and len(file_content.strip()) > 0:
                    raw_items = file_content.splitlines()
                    all_target_dbs = []
                    for line in raw_items:
                        line = line.strip()
                        if not line:
                            continue
                        match = re.search(r'https?://[^\s]+', line)
                        target_url = match.group(0) if match else line
                        unpacked_dbs = extract_firebase_from_vercel_link(target_url)
                        valid_dbs = [db for db in unpacked_dbs if "firebaseio.com" in db or "firebasedatabase.app" in db or "-default-rtdb" in db]
                        all_target_dbs.extend(valid_dbs)

                    seen = set()
                    unique_target_dbs = [x for x in all_target_dbs if not (x in seen or seen.add(x))][:2000]

                    if unique_target_dbs:
                        batch_outputs = await parse_batch_panels(unique_target_dbs)
                        report = f"⚡ <b>File Bulk Scan Report (Total: {len(unique_target_dbs)})</b>\n\n"
                        for idx, (db_url, total, online) in enumerate(batch_outputs, 1):
                            vercel_url = generate_vercel_link(db_url)
                            report += f"<b>{idx}.</b> <code>{db_url}</code>\n📦 Total: <code>{total}</code> | 🟢 Online: <code>{online}</code>\n🔗 Panel: {vercel_url}\n\n"
                        report += "🛡️ <b>Developed by Cyber Core System</b>"

                        if len(report) > 4000:
                            out_path = os.path.join(tempfile.gettempdir(), f"File_Bulk_Report_{time.time()}.txt")
                            with open(out_path, "w", encoding="utf-8") as out_f:
                                clean_export = report.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
                                out_f.write(clean_export)
                            await status_msg.edit_text(format_reply(f"⚡ <b>Bulk Scan Complete!</b>\n🔥 Processed Databases: <code>{len(unique_target_dbs)}</code>\n\n📄 Detailed results attached below.\n\n🛡️ <b>Developed by Cyber Core System</b>"), parse_mode="HTML")
                            await context.bot.send_document(chat_id=chat_id, document=open(out_path, "rb"), caption=format_reply("📁 <b>Full File Bulk Scan Report</b>"), parse_mode="HTML")
                            try: os.remove(out_path)
                            except: pass
                        else:
                            await status_msg.edit_text(format_reply(report), parse_mode="HTML", disable_web_page_preview=True)
                    else:
                        await status_msg.edit_text(format_reply("⚠️ No valid Firebase URLs found inside the uploaded file."), parse_mode="HTML")
                else:
                    scan_res, found_dbs = extract_firebase_from_apk(file_path)
                    await status_msg.edit_text(scan_res, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                await status_msg.edit_text(format_reply(f"❌ Error processing file: <code>{str(e)}</code>"), parse_mode="HTML")
            finally:
                try: os.remove(file_path)
                except: pass
        else:
            await status_msg.edit_text(format_reply("❌ Failed to download file."), parse_mode="HTML")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("export", handle_messages))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_messages))
    app.run_polling()

if __name__ == "__main__":
    main()
