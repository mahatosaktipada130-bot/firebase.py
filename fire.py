import os
import re
import base64
import json
import time
import threading
from urllib.parse import unquote

import requests
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

# ===== BOT TOKEN =====
BOT_TOKEN = "8430586261:AAFSWAl_Z6knmPrdsQ8n1wf3783C-mC0WT4"

# ===== PARTY POPPER EFFECT =====
FIRE_EFFECT_ID = "5046509860389126442"

# ===== FLASK KEEPALIVE =====
PORT = int(os.environ.get("PORT", 8080))
flask_app = Flask(__name__)

BOT_STARTED_AT = time.time()

# Firebase URLs (legacy + regional + default)
FIREBASE_PATTERN = (
    r"https?://"
    r"(?:"
    r"[a-zA-Z0-9_-]+\.firebaseio\.com"
    r"|"
    r"[a-zA-Z0-9_-]+(?:\.[a-z0-9-]+)?\.firebasedatabase\.app"
    r")"
)

PARAM_PATTERN = re.compile(r"[?&]([a-zA-Z0-9_]+)=([^&#\s]+)")
STD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

FIREBASE_PATHS = [
    "clients.json",
    "users.json",
    "Users.json",
    "devices.json",
    "Devices.json",
    "online.json",
    "data.json",
    ".json",
]

COMMON_KEYS = [
    b"key", b"firebase", b"panel", b"admin", b"secret", b"password",
    b"123456", b"abc", b"xyz", b"test", b"app", b"web", b"fire", b"db",
    b"nex", b"cod", b"game", b"apex", b"free", b"live", b"share",
    b"link", b"url", b"data", b"info", b"qwerty", b"hello", b"world",
    b"bot", b"tg", b"telegram", b"user", b"pass", b"auth", b"login",
    b"root", b"toor", b"default", b"guest", b"null", b"none",
    b"zxkaiz", b"vercel", b"annebella", b"dakku", b"abhixalfinzo", b"firexpanel",
]

SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ',
    'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
    'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
    's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
}

URL_REGEX = re.compile(r'https?://\S+')


# ================= Flask routes =================
@flask_app.route("/")
def index():
    return {
        "status": "ok",
        "bot": "firebase-checker",
        "uptime_seconds": int(time.time() - BOT_STARTED_AT),
    }


@flask_app.route("/health")
@flask_app.route("/healthz")
def health():
    return {"status": "healthy", "uptime": int(time.time() - BOT_STARTED_AT)}, 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ================= Styling =================
def small_caps(text: str) -> str:
    urls = []

    def _hold(m):
        urls.append(m.group())
        return f"\uE000{len(urls) - 1}\uE001"

    temp = URL_REGEX.sub(_hold, text)
    converted = "".join(SMALL_CAPS_MAP.get(c, c) for c in temp)
    for i, u in enumerate(urls):
        converted = converted.replace(f"\uE000{i}\uE001", u)
    return converted


async def send_styled(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    styled = small_caps(text)
    chat_id = update.effective_chat.id
    try:
        return await context.bot.send_message(
            chat_id=chat_id, text=styled, message_effect_id=FIRE_EFFECT_ID,
        )
    except TypeError:
        pass
    except Exception:
        pass
    try:
        return await context.bot.send_message(chat_id=chat_id, text=styled)
    except Exception:
        return None


# ================= Device parsing =================
def is_online_value(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        if val in (0, 1):
            return bool(val)
        return None
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ("online", "active", "true", "1", "yes", "on"):
            return True
        if s in ("offline", "inactive", "false", "0", "no", "off"):
            return False
        return None
    if isinstance(val, dict):
        for field in ("status", "online", "isOnline", "is_online", "state", "presence", "active"):
            if field in val:
                r = is_online_value(val[field])
                if r is not None:
                    return r
        for field in ("lastSeen", "last_seen", "timestamp", "ts", "lastActive", "last_active"):
            if field in val:
                try:
                    ts = float(val[field])
                    if ts > 1e12:
                        ts /= 1000
                    if 0 < time.time() - ts < 120:
                        return True
                except (ValueError, TypeError):
                    pass
        return None
    return None


def parse_devices(data):
    if data is None:
        return 0, 0, 0
    if isinstance(data, dict):
        items = list(data.values())
    elif isinstance(data, list):
        items = data
    else:
        return 0, 0, 0

    total = 0
    online = 0
    for val in items:
        if val is None:
            continue
        total += 1
        if is_online_value(val) is True:
            online += 1
    return online, total - online, total


# ================= Decoders =================
def _xor(data: bytes, key: bytes) -> bytes:
    if not key:
        return data
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _try_b64_decode(s: str):
    s_clean = re.sub(r"\s+", "", s).replace("-", "+").replace("_", "/")
    stripped = s_clean.rstrip("=")
    padded = stripped + "=" * ((-len(stripped)) % 4)
    try:
        return base64.b64decode(padded, validate=True)
    except Exception:
        try:
            return base64.b64decode(padded)
        except Exception:
            return None


def walk_extract(obj, found: list):
    if isinstance(obj, dict):
        for v in obj.values():
            walk_extract(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk_extract(v, found)
    elif isinstance(obj, str):
        found.extend(re.findall(FIREBASE_PATTERN, obj))


def _process(data: bytes, found: list) -> bool:
    if not data:
        return False
    try:
        text = data.decode("utf-8", errors="strict")
    except Exception:
        return False
    if "firebaseio.com" in text or "firebasedatabase.app" in text:
        found.extend(re.findall(FIREBASE_PATTERN, text))
        return True
    unq = unquote(text)
    if "firebaseio.com" in unq or "firebasedatabase.app" in unq:
        found.extend(re.findall(FIREBASE_PATTERN, unq))
        return True
    stripped = text.strip()
    if stripped and stripped[0] in "{[":
        try:
            walk_extract(json.loads(stripped), found)
            return len(found) > 0
        except Exception:
            pass
    return False


def _rc4(data: bytes, key: bytes) -> bytes:
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(byte ^ S[(S[i] + S[j]) % 256])
    return bytes(out)


def decode_param_value(value: str, hint: str = "") -> list:
    found = []
    if not value or len(value) < 8:
        return found
    s = re.sub(r"\s+", "", unquote(value))
    if not s:
        return found

    raw = _try_b64_decode(s)
    if raw and _process(raw, found):
        return found

    if raw:
        for k in range(256):
            if _process(bytes(b ^ k for b in raw), found):
                return found

    if raw:
        for key in COMMON_KEYS:
            if _process(_xor(raw, key), found):
                return found

    if raw and hint:
        hb = hint.encode("utf-8", errors="ignore")
        if hb and _process(_xor(raw, hb), found):
            return found
        for n in (3, 4, 5, 6, 7, 8, 10, 12, 16):
            if len(hb) >= n and _process(_xor(raw, hb[:n]), found):
                return found

    if raw:
        for key in COMMON_KEYS:
            if _process(_rc4(raw, key), found):
                return found

    s_strip = s.replace("-", "+").replace("_", "/").rstrip("=")
    for shift in range(64):
        rotated = STD_ALPHABET[shift:] + STD_ALPHABET[:shift]
        mp = {rotated[i]: STD_ALPHABET[i] for i in range(64)}
        mapped = "".join(mp.get(c, c) for c in s_strip)
        dec = _try_b64_decode(mapped)
        if dec and _process(dec, found):
            return found

    rb = s.encode("utf-8", errors="ignore")
    for key in COMMON_KEYS:
        try:
            dec = _try_b64_decode(_xor(rb, key).decode("latin-1"))
        except Exception:
            continue
        if dec and _process(dec, found):
            return found

    if raw:
        try:
            inner = _try_b64_decode(raw.decode("ascii", errors="ignore").strip())
            if inner and _process(inner, found):
                return found
        except Exception:
            pass

    raw_rev = _try_b64_decode(s[::-1])
    if raw_rev and _process(raw_rev, found):
        return found
    if raw_rev:
        for k in range(256):
            if _process(bytes(b ^ k for b in raw_rev), found):
                return found

    return found


def extract_firebase_urls(text: str) -> list:
    found = list(re.findall(FIREBASE_PATTERN, text))
    hint = ""
    m = re.search(r"([a-zA-Z0-9-]+)\.vercel\.app", text)
    if m:
        hint = m.group(1)
    for match in PARAM_PATTERN.finditer(text):
        found.extend(decode_param_value(match.group(2), hint))
    return list(dict.fromkeys(u.rstrip("/") for u in found))


# ================= Handlers =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_styled(
        update, context,
        "👋 Firebase Checker Bot Ready!\n\n"
        "Mujhe koi bhi text bhejo jisme Firebase URL ho (direct ya encoded wrapper link "
        "jaise ?m=, ?share=, ?s=). Main decode karke check kar lunga!\n\n"
        "ℹ️ Multiple DB paths try hote hain — clients, users, devices, root, etc."
    )


async def check_firebase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    unique_urls = extract_firebase_urls(text)

    if not unique_urls:
        await send_styled(
            update, context,
            "❌ Koi Firebase URL extract nahi ho saka.\n\n"
            "Agar custom-cipher panel link hai (jaise zxkaiz.vercel.app/?s=...), "
            "to panel ka main.js / bundle.js bhejo — exact decoder add kar dunga."
        )
        return

    scan_msg = await send_styled(
        update, context,
        f"⏳ Scanning {len(unique_urls)} Firebase URL(s)..."
    )

    sent = skipped = errors = 0

    try:
        for url in unique_urls:
            online = offline = total = 0
            last_status = None
            err_msg = None
            paths_tried = []

            for path in FIREBASE_PATHS:
                paths_tried.append(path)
                try:
                    r = requests.get(f"{url}/{path}", timeout=10)
                    last_status = r.status_code
                    if r.status_code == 200:
                        try:
                            data = r.json()
                        except Exception:
                            continue
                        o, off, t = parse_devices(data)
                        if t > 0:
                            online, offline, total = o, off, t
                            break
                except Exception as e:
                    err_msg = str(e)
                    continue

            if online > 0:
                sent += 1
                await send_styled(
                    update, context,
                    f"🟢 Online devices     : {online}\n"
                    f"🔴 Offline devices    : {offline}\n\n"
                    f"✅ {url}"
                )

            elif total > 0:
                skipped += 1
                if len(unique_urls) == 1:
                    await send_styled(
                        update, context,
                        f"🟢 Online devices     : 0\n"
                        f"🔴 Offline devices    : {offline}\n\n"
                        f"✅ {url}"
                    )

            elif last_status == 200:
                skipped += 1
                if len(unique_urls) == 1:
                    await send_styled(
                        update, context,
                        f"ℹ️ Database accessible hai lekin koi recognized device data nahi mila.\n"
                        f"Paths tried: {', '.join(FIREBASE_PATHS)}\n\n"
                        f"🔗 {url}"
                    )

            elif last_status in (401, 403):
                errors += 1
                await send_styled(
                    update, context,
                    f"🔒 Database permission denied (HTTP {last_status}).\n"
                    f"Firebase rules public read block kar rahe hain.\n\n"
                    f"🔗 {url}"
                )

            elif err_msg:
                errors += 1
                await send_styled(
                    update, context,
                    f"❌ Scan Failed!\nError: {err_msg}\n\n🔗 {url}"
                )

            else:
                errors += 1
                await send_styled(
                    update, context,
                    f"❌ Could not access DB (HTTP {last_status})\n\n🔗 {url}"
                )

        if len(unique_urls) > 1 and (skipped or errors):
            lines = ["📊 Summary:", f"✅ Reported: {sent}"]
            if skipped:
                lines.append(f"⏭️ Skipped (0 online / no data): {skipped}")
            if errors:
                lines.append(f"❌ Errors: {errors}")
            await send_styled(update, context, "\n".join(lines))

    finally:
        if scan_msg is not None:
            try:
                await scan_msg.delete()
            except Exception:
                pass


def main():
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN missing hai!")
        return

    threading.Thread(target=run_flask, daemon=True).start()
    print(f"🌐 Flask keepalive running on port {PORT}")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_firebase))
    print("🤖 Bot is running on Railway...")
    app.run_polling()


if __name__ == "__main__":
    main()
