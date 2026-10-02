from flask import Flask
# ====================================================
#          ƬʜᴇΉΛᑕKΣЯ♛  •  PRIME HOSTING v5.2
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

# ==================== RAILWAY / ENV CONFIG ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", 5427735251))
OWNER_NAME = "👑  Rᴜsʜᴇʀ Kɪɴɢ  👑"

HOST_DIR = "hosted_files"
MAX_LOG_SIZE_MB = 5

# Default live custom-emoji IDs (Premium animated)
DEFAULT_EMOJI = {
    "fire": "5424972470023104089",
    "star": "5438496463044752972",
    "check": "5206607081334906820",
    "cross": "5210952531676504517",
    "bell": "5458603043203327669",
    "money": "5409048419211682843",
    "lock": "5296369303661067030",
    "warning": "5447644880824181073",
    "settings": "5341715473882955310",
    "gift": "5309849913218071967",
    "rocket": "5188481279963715781",
    "diamond": "5199448307155350272",
    "wave": "5870734657384877785",
    "user": "5879770735999717115",
    "people": "5942877472163892475",
    "bot": "5931415565955503486",
    "link": "5271604874419647061",
    "refresh": "5375338737028841420",
    "top": "5415655814079723871",
    "card": "5927169041595634481",
    "support": "5884510167986343350",
    "urgent": "5224607267797606837",
    "crown": "5438496463044752972",
    "spark": "5424972470023104089",
}

config = {
    "bot_username": "",
    "admin_username": "",
    "channel_username": "",
    "force_channel": "",
    "brand_name": "👑  Rᴜsʜᴇʀ Kɪɴɢ  👑",
    "free_limit": 5,
    "prime_limit": 5,
}
EMOJI_IDS = dict(DEFAULT_EMOJI)

os.makedirs(HOST_DIR, exist_ok=True)

bot = TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

# Admin / user waiting states  e.g. {"123": {"action": "set_emoji", "key": "rocket"}}
waiting_states = {}

# ==================== DATABASE ====================
def get_db():
    conn = sqlite3.connect("hosting_data.db", check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_prime INTEGER DEFAULT 0,
            prime_expire TEXT DEFAULT NULL,
            referred_by INTEGER DEFAULT NULL,
            referral_count INTEGER DEFAULT 0,
            ref_pending INTEGER DEFAULT NULL,
            joined_ok INTEGER DEFAULT 0
        )
    """)
    # migrate columns if old DB
    for col, typ in (("ref_pending", "INTEGER DEFAULT NULL"), ("joined_ok", "INTEGER DEFAULT 0")):
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        except Exception:
            pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosted_bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            filepath TEXT,
            logpath TEXT,
            pid INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'pending',
            auto_guard INTEGER DEFAULT 1,
            speed_boost INTEGER DEFAULT 0,
            created_at TEXT DEFAULT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prime_codes (
            code TEXT PRIMARY KEY,
            days INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    default_config = {
        "bot_username": "",
        "admin_username": "",
        "channel_username": "",
        "force_channel": "",
        "brand_name": "👑  Rᴜsʜᴇʀ Kɪɴɢ  👑",
        "free_limit": "5",
        "prime_limit": "5",
    }
    for k, v in default_config.items():
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))
    # Seed default emoji ids
    for ek, ev in DEFAULT_EMOJI.items():
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (f"emoji_{ek}", ev))

    conn.commit()
    conn.close()

init_db()

def load_config():
    global config, EMOJI_IDS
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM config")
    rows = cursor.fetchall()
    conn.close()
    emoji_map = dict(DEFAULT_EMOJI)
    for row in rows:
        key = row['key']
        val = row['value']
        if key in config:
            if key in ["free_limit", "prime_limit"]:
                try:
                    config[key] = int(val)
                except Exception:
                    pass
            else:
                config[key] = val
        elif key.startswith("emoji_"):
            ek = key[6:]
            if val and str(val).isdigit():
                emoji_map[ek] = str(val)
    EMOJI_IDS = emoji_map

load_config()


def ce(emoji_id: str, fallback: str) -> str:
    """HTML live custom emoji tag."""
    if emoji_id and str(emoji_id).isdigit():
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback


def pe(key: str, fallback: str) -> str:
    """Resolve live emoji by key (admin override aware)."""
    eid = EMOJI_IDS.get(key) or DEFAULT_EMOJI.get(key)
    return ce(str(eid), fallback) if eid else fallback


def brand() -> str:
    return config.get("brand_name") or "👑  Rᴜsʜᴇʀ Kɪɴɢ  👑"


def set_config_value(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
    load_config()

# ==================== HELPERS ====================
def register_user(user_id, ref_by=None):
    """Register user. Referral is NOT counted until force-channel verify."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, joined_ok, ref_pending, referred_by FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        if ref_by and ref_by != user_id:
            # Store pending referrer — count only after channel verify
            cursor.execute(
                "INSERT INTO users (user_id, ref_pending, joined_ok) VALUES (?, ?, 0)",
                (user_id, ref_by),
            )
        else:
            cursor.execute("INSERT INTO users (user_id, joined_ok) VALUES (?, 0)", (user_id,))
        conn.commit()
    elif ref_by and ref_by != user_id and not row["referred_by"] and not row["ref_pending"]:
        cursor.execute("UPDATE users SET ref_pending = ? WHERE user_id = ?", (ref_by, user_id))
        conn.commit()
    conn.close()


def get_bot_username():
    """Working bot username for referral links."""
    u = (config.get("bot_username") or "").strip().lstrip("@")
    if u:
        return u
    try:
        me = bot.get_me()
        if me and me.username:
            set_config_value("bot_username", me.username)
            return me.username
    except Exception:
        pass
    return "bot"


def check_user_in_force_channel(user_id):
    """Return True if no force channel set, or user is member."""
    ch = (config.get("force_channel") or "").strip().lstrip("@")
    if not ch:
        return True
    try:
        member = bot.get_chat_member(f"@{ch}", user_id)
        status = getattr(member, "status", "") or ""
        return status in ("member", "administrator", "creator", "owner", "restricted")
    except Exception:
        return False


def credit_referral(user_id):
    """After force-join verify — move ref_pending → referred_by and bump count."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ref_pending, referred_by, joined_ok FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    ref_by = row["ref_pending"]
    if row["referred_by"] or not ref_by:
        cursor.execute("UPDATE users SET joined_ok = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return
    cursor.execute(
        "UPDATE users SET referred_by = ?, ref_pending = NULL, joined_ok = 1 WHERE user_id = ?",
        (ref_by, user_id),
    )
    cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (ref_by,))
    cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (ref_by,))
    ref_row = cursor.fetchone()
    conn.commit()
    conn.close()
    if ref_row and ref_row["referral_count"] % 3 == 0:
        add_prime_days(ref_by, 1)
        try:
            bot.send_message(
                ref_by,
                f'{pe("gift", "🎉")} <b>Referral Bonus!</b> +1 day FREE Prime VIP.',
                parse_mode="HTML",
            )
        except Exception:
            pass
    try:
        bot.send_message(
            ref_by,
            f'{pe("people", "👥")} New referral verified! Total may have increased.',
            parse_mode="HTML",
        )
    except Exception:
        pass


def force_join_keyboard():
    ch = (config.get("force_channel") or "").strip().lstrip("@")
    markup = types.InlineKeyboardMarkup()
    if ch:
        markup.add(ibtn(f"Join @{ch}", url=f"https://t.me/{ch}", style="primary", icon="link"))
    markup.add(ibtn("I Joined — Verify", callback_data="force_verify", style="danger", icon="check"))
    return markup

def is_prime_user(user_id):
    # All users get the full feature set for free. Kept as a compatibility
    # helper because older handlers still call this function.
    return True

def add_prime_days(user_id, days):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT prime_expire FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    now = datetime.now()
    if row and row['prime_expire']:
        try:
            current_expire = datetime.strptime(row['prime_expire'], "%Y-%m-%d %H:%M:%S")
            new_expire = (current_expire if current_expire > now else now) + timedelta(days=days)
        except Exception:
            new_expire = now + timedelta(days=days)
    else:
        new_expire = now + timedelta(days=days)
    expire_str = new_expire.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE users SET is_prime = 1, prime_expire = ? WHERE user_id = ?", (expire_str, user_id))
    conn.commit()
    conn.close()

def send_typing(chat_id):
    """Show typing indicator so user knows bot is working."""
    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

def send_or_edit(chat_id, text, reply_markup=None, message_id=None, parse_mode="HTML"):
    send_typing(chat_id)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode, reply_markup=reply_markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)

def is_process_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def safe_popen(filepath, logpath):
    """Start script safely — no preexec_fn crash on restricted hosts."""
    log_file = open(logpath, 'a', encoding='utf-8')
    log_file.write(f"\n--- [STARTED {datetime.now()}] ---\n")
    log_file.flush()
    cmd = [sys.executable, "-u", filepath]
    cwd = os.path.dirname(filepath) or "."
    # Prefer start_new_session (no preexec_fn — avoids platform crash)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            start_new_session=True,
        )
    except Exception:
        try:
            log_file.close()
        except Exception:
            pass
        log_file = open(logpath, 'a', encoding='utf-8')
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=cwd,
        )
    return proc


def safe_kill(pid):
    """Kill process safely across platforms."""
    if not pid or not is_process_alive(pid):
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        time.sleep(0.3)
        if is_process_alive(pid):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            if is_process_alive(pid):
                os.kill(pid, 9)
        except Exception:
            try:
                os.kill(pid, 9)
            except Exception:
                pass

# ==================== AUTO LIBRARY INSTALLER ====================
def extract_imports(filepath):
    packages = set()
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        for match in re.finditer(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE):
            pkg = match.group(1).split('.')[0]
            stdlib = {
                'os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random',
                'string', 'threading', 'subprocess', 'sqlite3', 'logging',
                'collections', 'functools', 'itertools', 'pathlib', 'shutil',
                'tempfile', 'urllib', 'http', 'socket', 'ssl', 'hashlib',
                'base64', 'pickle', 'copy', 'traceback', 'typing', 'dataclasses',
                'enum', 'abc', 'io', 'csv', 'xml', 'html', 'email',
                'multiprocessing', 'concurrent', 'asyncio', 'queue', 'signal',
                'platform', 'getpass', 'glob', 'fnmatch', 'struct', 'array',
                'bisect', 'heapq', 'weakref', 'types', 'pprint', 'reprlib',
                'numbers', 'decimal', 'fractions', 'statistics', 'cmath',
                'secrets', 'uuid', 'hmac', 'secrets', 'argparse', 'configparser',
                'contextlib', 'warnings', 'gc', 'inspect', 'ast', 'dis',
                'importlib', 'pkgutil', 'modulefinder', 'runpy', 'site',
                'builtins', 'operator', 'keyword', 'token', 'tokenize', 'code',
                'codeop', 'py_compile', 'compileall', 'zipimport', 'zlib',
                'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile', 'csv', 'netrc',
                'calendar', 'sched', 'select', 'selectors', 'mmap', 'ctypes',
                'errno', 'fcntl', 'pipes', 'resource', 'syslog', 'termios',
                'tty', 'pty', 'pwd', 'grp', 'spwd', 'crypt', 'nis', 'stat',
                'fileinput', 'linecache', 'textwrap', 'unicodedata', 'stringprep',
                'codecs', 'locale', 'gettext', 'cmd', 'shlex', 'tkinter',
                'turtle', 'pdb', 'profile', 'pstats', 'timeit', 'trace',
                'tracemalloc', 'gc', 'sysconfig', 'venv', 'ensurepip',
                'wsgiref', 'http', 'ftplib', 'poplib', 'imaplib', 'nntplib',
                'smtplib', 'telnetlib', 'xmlrpc', 'ipaddress', 'socketserver',
                'webbrowser', 'cgi', 'cgitb', 'wsgiref', 'secrets',
            }
            if pkg and pkg not in stdlib and not pkg.startswith('_'):
                packages.add(pkg)
    except Exception:
        pass
    return packages

def auto_install_packages(filepath, logpath):
    packages = extract_imports(filepath)
    if not packages:
        return [], []

    installed = []
    failed = []
    name_map = {
        'telebot': 'pyTelegramBotAPI',
        'telegram': 'python-telegram-bot',
        'PIL': 'Pillow',
        'cv2': 'opencv-python',
        'sklearn': 'scikit-learn',
        'bs4': 'beautifulsoup4',
        'yaml': 'PyYAML',
        'dotenv': 'python-dotenv',
        'dateutil': 'python-dateutil',
        'jwt': 'PyJWT',
        'Crypto': 'pycryptodome',
        'requests': 'requests',
        'aiohttp': 'aiohttp',
        'flask': 'flask',
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'qrcode': 'qrcode',
        'pymongo': 'pymongo',
        'discord': 'discord.py',
        'yt_dlp': 'yt-dlp',
    }

    with open(logpath, 'a', encoding='utf-8') as log:
        log.write(f"\n--- [AUTO-PIP START {datetime.now()}] ---\n")
        for pkg in packages:
            pip_name = name_map.get(pkg, pkg)
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", pip_name],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    log.write(f"[OK] Already installed: {pip_name}\n")
                    continue
                log.write(f"[INSTALLING] {pip_name} ...\n")
                log.flush()
                install = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir", pip_name],
                    capture_output=True, text=True, timeout=120
                )
                if install.returncode == 0:
                    installed.append(pip_name)
                    log.write(f"[SUCCESS] {pip_name} installed\n")
                else:
                    failed.append(pip_name)
                    log.write(f"[FAILED] {pip_name}: {install.stderr[:200]}\n")
            except Exception as e:
                failed.append(pip_name)
                log.write(f"[ERROR] {pip_name}: {str(e)}\n")
        log.write(f"--- [AUTO-PIP END] Installed: {len(installed)} | Failed: {len(failed)} ---\n")
        log.flush()
    return installed, failed

# ==================== CRASH GUARD ====================
def crash_guard_worker():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hosted_bots WHERE status = 'running'")
            running_bots = cursor.fetchall()

            for b in running_bots:
                pid = b['pid']
                bot_id = b['id']
                user_id = b['user_id']
                filepath = b['filepath']
                logpath = b['logpath']

                if os.path.exists(logpath) and os.path.getsize(logpath) > MAX_LOG_SIZE_MB * 1024 * 1024:
                    try:
                        with open(logpath, 'w', encoding='utf-8') as f:
                            f.write(f"--- [LOG RESET {datetime.now()}] ---\n")
                    except Exception:
                        pass

                alive = is_process_alive(pid) if pid else False

                if not alive:
                    if is_prime_user(user_id) and b['auto_guard'] == 1:
                        try:
                            with open(logpath, 'a', encoding='utf-8') as lf:
                                lf.write(f"\n--- [AUTO-RESTART {datetime.now()}] ---\n")
                            proc = safe_popen(filepath, logpath)
                            cursor.execute("UPDATE hosted_bots SET pid = ? WHERE id = ?", (proc.pid, bot_id))
                            conn.commit()
                        except Exception:
                            cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
                            conn.commit()
                    else:
                        cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
                        conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(8)

guard_thread = threading.Thread(target=crash_guard_worker, daemon=True)
guard_thread.start()

# ==================== STYLED BUTTONS ====================
def _btn_to_dict_patch(original_to_dict):
    """Inject style + icon_custom_emoji_id into button JSON for Telegram API."""
    def patched(self):
        d = original_to_dict(self)
        style = getattr(self, "_style", None)
        icon = getattr(self, "_icon_custom_emoji_id", None)
        if style:
            d["style"] = style
        if icon:
            d["icon_custom_emoji_id"] = str(icon)
        return d
    return patched

if not getattr(types.InlineKeyboardButton, "_style_patched", False):
    types.InlineKeyboardButton.to_dict = _btn_to_dict_patch(types.InlineKeyboardButton.to_dict)
    types.InlineKeyboardButton._style_patched = True
if not getattr(types.KeyboardButton, "_style_patched", False):
    types.KeyboardButton.to_dict = _btn_to_dict_patch(types.KeyboardButton.to_dict)
    types.KeyboardButton._style_patched = True


def ibtn(text, callback_data=None, url=None, style=None, icon=None):
    """Inline button with blue/red style + live emoji icon."""
    kwargs = {}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    btn = types.InlineKeyboardButton(text, **kwargs)
    if style:
        btn._style = style
    eid = EMOJI_IDS.get(icon) if icon else None
    if eid:
        btn._icon_custom_emoji_id = str(eid)
    return btn


def kbtn(text, style=None, icon=None):
    """Bottom (reply) keyboard button with optional style + live icon."""
    btn = types.KeyboardButton(text)
    if style:
        btn._style = style
    eid = EMOJI_IDS.get(icon) if icon else None
    if eid:
        btn._icon_custom_emoji_id = str(eid)
    return btn


# ==================== KEYBOARDS ====================
def main_reply_keyboard(user_id):
    """Persistent Telegram reply keyboard. Colors alternate: blue/red/green.
    No two adjacent buttons use the same style.
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, row_width=2)
    markup.row(
        kbtn("Upload Bot", style="primary", icon="rocket"),
        kbtn("My Bots", style="danger", icon="bot"),
    )
    markup.row(
        kbtn("Status", style="success", icon="refresh"),
        kbtn("Help", style="primary", icon="bell"),
    )
    markup.row(
        kbtn("Referral", style="danger", icon="people"),
        kbtn("Free Features", style="success", icon="diamond"),
    )
    ch = config.get("channel_username", "").strip()
    ad = config.get("admin_username", "").strip()
    extra = []
    if ch:
        extra.append(kbtn("Channel", style="primary", icon="link"))
    if ad:
        extra.append(kbtn("Support", style="danger", icon="support"))
    if extra:
        markup.row(*extra)
    if user_id == ADMIN_ID:
        markup.row(kbtn("Admin Panel", style="success", icon="settings"))
    return markup


def fetch_bot_identity(token):
    """Call Telegram getMe with token → {username, first_name, id} or None."""
    if not token or ":" not in token:
        return None
    try:
        import urllib.request
        import json as _json
        url = f"https://api.telegram.org/bot{token}/getMe"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8", errors="ignore"))
        if data.get("ok") and isinstance(data.get("result"), dict):
            r = data["result"]
            return {
                "username": r.get("username") or "",
                "first_name": r.get("first_name") or "",
                "id": r.get("id"),
            }
    except Exception:
        return None
    return None


def analyze_uploaded_file(filepath):
    """Check token, bot @username (via getMe), syntax for admin report."""
    report = {
        "has_token": False,
        "token_preview": None,
        "bot_username": None,
        "bot_name": None,
        "bot_id": None,
        "same_as_host": False,
        "syntax_ok": True,
        "syntax_error": None,
        "imports": [],
        "lines": 0,
        "size_kb": 0,
    }
    try:
        report["size_kb"] = round(os.path.getsize(filepath) / 1024, 1)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        report["lines"] = content.count("\n") + 1

        token_re = re.compile(r'\b(\d{8,12}:[A-Za-z0-9_-]{30,})\b')
        tokens = token_re.findall(content)
        if tokens:
            report["has_token"] = True
            t = tokens[0]
            report["token_preview"] = t[:8] + "..." + t[-6:]
            if BOT_TOKEN and any(tok == BOT_TOKEN for tok in tokens):
                report["same_as_host"] = True
            # Resolve @username of the bot this token belongs to
            ident = fetch_bot_identity(t)
            if ident:
                report["bot_username"] = ident.get("username") or None
                report["bot_name"] = ident.get("first_name") or None
                report["bot_id"] = ident.get("id")
            else:
                # try other tokens in file
                for tok in tokens[1:4]:
                    ident = fetch_bot_identity(tok)
                    if ident and ident.get("username"):
                        report["bot_username"] = ident.get("username")
                        report["bot_name"] = ident.get("first_name")
                        report["bot_id"] = ident.get("id")
                        report["token_preview"] = tok[:8] + "..." + tok[-6:]
                        break

        if not report["has_token"]:
            if re.search(r'BOT_TOKEN\s*=|TOKEN\s*=|API_TOKEN\s*=', content):
                report["has_token"] = True
                report["token_preview"] = "variable (check file)"

        try:
            compile(content, filepath, "exec")
            report["syntax_ok"] = True
        except SyntaxError as e:
            report["syntax_ok"] = False
            report["syntax_error"] = f"Line {e.lineno}: {e.msg}"

        pkgs = extract_imports(filepath)
        report["imports"] = sorted(list(pkgs))[:12]
    except Exception as e:
        report["syntax_ok"] = False
        report["syntax_error"] = str(e)[:120]
    return report


def prime_zone_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("My Subscription", callback_data="prime_expire_check", style="primary", icon="star"),
        ibtn("Gift Prime", callback_data="gift_prime", style="danger", icon="gift"),
    )
    markup.add(ibtn("Redeem Code", callback_data="claim_code", style="primary", icon="card"))
    markup.add(ibtn("Main Menu", callback_data="main_menu", style="danger", icon="top"))
    return markup


def admin_panel_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        ibtn("Bot Limits", callback_data="admin_change_limits", style="primary", icon="settings"),
        ibtn("Brand Name", callback_data="admin_set_brand", style="primary", icon="star"),
    )
    markup.add(
        ibtn("Live Emojis", callback_data="admin_emojis", style="danger", icon="spark"),
        ibtn("Free Access", callback_data="free_access_info", style="success", icon="check"),
    )
    markup.add(
        ibtn("Channel Username", callback_data="admin_set_channel", style="primary", icon="link"),
    )
    markup.add(
        ibtn("Admin Username", callback_data="admin_set_admin_user", style="danger", icon="user"),
        ibtn("Bot Username", callback_data="admin_set_bot_user", style="danger", icon="bot"),
    )
    markup.add(
        ibtn("Pending Requests", callback_data="admin_pending", style="danger", icon="urgent"),
        ibtn("Reload Config", callback_data="admin_reload", style="primary", icon="refresh"),
    )
    markup.add(ibtn("Main Menu", callback_data="main_menu", style="primary", icon="top"))
    return markup


def emoji_panel_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    keys = sorted(DEFAULT_EMOJI.keys())
    for i in range(0, len(keys), 2):
        pair = keys[i:i+2]
        buttons = [ibtn(k, callback_data=f"setemoji_{k}", style="primary", icon=k) for k in pair]
        markup.add(*buttons)
    markup.add(ibtn("Admin Panel", callback_data="admin_panel", style="danger", icon="settings"))
    return markup


def now_ist_str():
    """Current time in IST."""
    try:
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(ist).strftime("%d-%m-%Y %I:%M:%S %p IST")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " IST"


def back_main_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(ibtn("Main Menu", callback_data="main_menu", style="danger", icon="top"))
    return markup

# ==================== COMMANDS ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    ref_by = None
    text_args = message.text.split()
    if len(text_args) > 1 and text_args[1].startswith("ref_"):
        try:
            ref_by = int(text_args[1].replace("ref_", ""))
        except ValueError:
            pass

    register_user(user_id, ref_by)
    is_prime = is_prime_user(user_id)
    user_name = message.from_user.first_name or "User"
    limit = config['prime_limit'] if is_prime else config['free_limit']

    send_typing(message.chat.id)

    # Free access: no mandatory channel join / verification.

    badge_html = f'{pe("check", "✅")} <b>FREE</b>'
    guard_html = f'{pe("check", "✅")} 24/7 Active'
    welcome = (
        f'{pe("spark", "✨")} <b>{brand()}</b> {pe("spark", "✨")}\n'
        f'{pe("crown", "👑")} <b>{OWNER_NAME}</b> • FREE v5.2\n'
        f'━━━━━━━━━━━━━━━━━━━━\n\n'
        f'{pe("wave", "👋")} Welcome, <b>{user_name}</b>!\n\n'
        f'{pe("card", "🪪")} <b>Profile</b>\n'
        f'├ {pe("user", "🏷")} Name: <code>{user_name}</code>\n'
        f'├ {pe("card", "🆔")} ID: <code>{user_id}</code>\n'
        f'└ {pe("diamond", "💎")} Status: {badge_html}\n\n'
        f'{pe("rocket", "⚡")} <b>Hosting</b>\n'
        f'├ {pe("bot", "📦")} Limit: <code>{limit}</code> bots\n'
        f'└ {pe("lock", "🛡")} Crash Guard: {guard_html}\n\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'{pe("top", "👇")} Use buttons below:'
    )
    bot.send_message(
        message.chat.id,
        welcome,
        parse_mode="HTML",
        reply_markup=main_reply_keyboard(user_id),
    )

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    send_typing(message.chat.id)
    register_user(user_id)

    if not message.document.file_name or not message.document.file_name.lower().endswith('.py'):
        bot.reply_to(message, "❌ Only `.py` Python files are allowed.")
        return

    is_prime = is_prime_user(user_id)
    max_allowed = config['prime_limit'] if is_prime else config['free_limit']
    filename = message.document.file_name

    conn = get_db()
    cursor = conn.cursor()

    # Count only approved bots for limit
    cursor.execute("SELECT COUNT(*) as count FROM hosted_bots WHERE user_id = ? AND status != 'pending'", (user_id,))
    current_count = cursor.fetchone()['count']

    cursor.execute("SELECT id FROM hosted_bots WHERE user_id = ? AND filename = ? AND status != 'pending'", (user_id, filename))
    existing_approved = cursor.fetchone()

    if not existing_approved and current_count >= max_allowed:
        conn.close()
        bot.reply_to(message, f"⚠️ Limit reached! Max `{max_allowed}` hosted bots.", parse_mode="Markdown")
        return

    # Also check pending for same filename
    cursor.execute("SELECT id FROM hosted_bots WHERE user_id = ? AND filename = ? AND status = 'pending'", (user_id, filename))
    existing_pending = cursor.fetchone()
    if existing_pending:
        conn.close()
        bot.reply_to(message, "⏳ This file is already pending approval. Please wait.")
        return

    # Download & save
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)

    user_dir = os.path.join(os.getcwd(), HOST_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    filepath = os.path.join(user_dir, filename)
    logpath = filepath + ".log"

    with open(filepath, 'wb') as f:
        f.write(downloaded)

    with open(logpath, 'w', encoding='utf-8') as f:
        f.write(f"--- [UPLOADED {datetime.now()}] Pending approval ---\n")

    now_str = now_ist_str()
    cursor.execute(
        "INSERT INTO hosted_bots (user_id, filename, filepath, logpath, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (user_id, filename, filepath, logpath, now_str)
    )
    bot_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Notify user
    send_typing(message.chat.id)
    bot.reply_to(
        message,
        f'{pe("check", "✅")} <code>{html_mod.escape(filename)}</code> received!\n\n'
        f'{pe("bell", "⏳")} <b>Waiting for Admin Approval</b>\n'
        f'{pe("crown", "👑")} Owner: <b>{html_mod.escape(OWNER_NAME)}</b>\n'
        f'You will be notified once approved or rejected.',
        parse_mode="HTML",
    )

    # Notify Admin: full .py file + safe HTML details (no parse errors)
    try:
        user_name = message.from_user.first_name or "User"
        username = f"@{message.from_user.username}" if message.from_user.username else "No username"
        analysis = analyze_uploaded_file(filepath)

        esc = html_mod.escape
        token_line = "Token found" if analysis["has_token"] else "No bot token detected"
        if analysis.get("token_preview"):
            token_line += f" ({esc(str(analysis['token_preview']))})"
        danger = ""
        if analysis.get("same_as_host"):
            danger = "\n⚠️ <b>DANGER: Same token as HOSTING bot — do NOT approve.</b>"

        if analysis["syntax_ok"]:
            syntax_line = "Syntax OK"
        else:
            syntax_line = f"Syntax Error: {esc(str(analysis.get('syntax_error') or 'unknown'))}"

        imports = analysis.get("imports") or []
        imp_line = ", ".join(esc(str(p)) for p in imports) if imports else "none"

        # Bot @username from token (getMe)
        tg_user = analysis.get("bot_username")
        tg_name = analysis.get("bot_name")
        if tg_user:
            bot_identity = f"@{esc(tg_user)}"
            if tg_name:
                bot_identity = f"{esc(tg_name)} ({bot_identity})"
        else:
            bot_identity = "Unknown (token invalid / not found)"

        caption = (
            f"📥 New Hosting Request\n"
            f"🔢 File ID: {bot_id}\n"
            f"🤖 TG Bot: {bot_identity}\n"
            f"📄 File: {esc(filename)}\n"
            f"👤 {esc(user_name)} ({esc(username)})\n"
            f"🆔 User: {user_id}\n"
            f"📦 {analysis.get('size_kb', '?')} KB | {analysis.get('lines', '?')} lines\n"
            f"🔑 {token_line}{danger}\n"
            f"🧪 {syntax_line}"
        )
        if len(caption) > 1000:
            caption = caption[:990] + "..."

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            ibtn("Approve", callback_data=f"approve_{bot_id}", style="primary", icon="check"),
            ibtn("Reject", callback_data=f"reject_{bot_id}", style="danger", icon="cross"),
        )
        markup.add(ibtn("View Logs", callback_data=f"adminlog_{bot_id}", style="primary", icon="bell"))

        with open(filepath, 'rb') as doc:
            bot.send_document(
                ADMIN_ID,
                doc,
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )

        detail = (
            f'{pe("card", "📋")} <b>Request details</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("star", "🔢")} <b>File ID:</b> <code>{bot_id}</code>\n'
            f'{pe("bot", "🤖")} <b>TG Bot:</b> {bot_identity}\n'
            f'{pe("bot", "📄")} <b>File:</b> <code>{esc(filename)}</code>\n'
            f'{pe("user", "👤")} User: <b>{esc(user_name)}</b> ({esc(username)})\n'
            f'{pe("card", "🆔")} User ID: <code>{user_id}</code>\n'
            f'{pe("bell", "📅")} Time: <code>{esc(now_str)}</code>\n'
            f'{pe("lock", "🔑")} Token: {esc(token_line)}{danger}\n'
            f'{pe("check", "🧪")} Syntax: {syntax_line}\n'
            f'{pe("rocket", "📚")} Imports: <code>{imp_line}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("gift", "📎")} Full <code>.py</code> above.\n'
            f'{pe("bell", "📜")} Logs: <code>/logs {bot_id}</code> ya <code>/logs {user_id}</code>'
        )
        bot.send_message(ADMIN_ID, detail, parse_mode="HTML")
    except Exception as e:
        # Last resort: still try to send raw file without parse_mode
        try:
            with open(filepath, 'rb') as doc:
                bot.send_document(ADMIN_ID, doc, caption=f"New upload from {user_id} | {filename}")
            bot.send_message(ADMIN_ID, f"⚠️ Details failed: {str(e)[:200]}")
        except Exception as e2:
            try:
                bot.send_message(ADMIN_ID, f"⚠️ Upload notify failed from {user_id}: {str(e2)[:150]}")
            except Exception:
                pass


# ==================== WAITING STATE HANDLER (emoji / admin steps) ====================
@bot.message_handler(func=lambda m: m.from_user and m.from_user.id in waiting_states,
                     content_types=['text', 'sticker', 'animation', 'photo', 'document'])
def waiting_state_handler(message):
    uid = message.from_user.id
    state = waiting_states.get(uid)
    if not state:
        return
    action = state.get("action")
    text = (message.text or message.caption or "").strip()

    if text.lower() in ("cancel", "/cancel", "exit", "back"):
        waiting_states.pop(uid, None)
        bot.reply_to(message, f'{pe("check", "✅")} Cancelled.', parse_mode="HTML")
        return

    if action == "set_emoji":
        key = state.get("key")
        eid = _extract_custom_emoji_id(message)
        if not eid and text.isdigit() and len(text) >= 10:
            eid = text
        if not eid:
            bot.reply_to(
                message,
                f'{pe("cross", "❌")} Custom emoji nahi mila.\n'
                f'Sirf <b>live emoji</b> bhejo (extra text mat likho).\n'
                f'Cancel: <code>cancel</code>',
                parse_mode="HTML",
            )
            return
        set_config_value(f"emoji_{key}", eid)
        waiting_states.pop(uid, None)
        bot.reply_to(
            message,
            f'{pe("check", "✅")} <b>{key}</b> set!\n'
            f'Preview: {pe(key, "✨")}\n'
            f'<code>{eid}</code>',
            parse_mode="HTML",
        )
        return

    if action == "set_brand":
        val = text
        if not val or len(val) > 64:
            bot.reply_to(message, "❌ Brand name 1-64 chars. Cancel: cancel")
            return
        set_config_value("brand_name", val)
        waiting_states.pop(uid, None)
        bot.reply_to(message, f'{pe("check", "✅")} Brand: <b>{val}</b>', parse_mode="HTML")
        return

    if action == "admin_logs_uid":
        if not text.isdigit():
            bot.reply_to(message, "❌ Numeric File ID ya User ID bhejo. Cancel: cancel")
            return
        waiting_states.pop(uid, None)
        tid = int(text)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM hosted_bots WHERE id = ?", (tid,))
        as_bot = cursor.fetchone()
        conn.close()
        if as_bot:
            _admin_send_bot_log(message.chat.id, tid)
        else:
            _admin_show_user_bots_logs(message.chat.id, tid)
        return


# ==================== BOTTOM MENU (TEXT) HANDLER ====================
@bot.message_handler(func=lambda m: m.text in {
    "Upload Bot", "My Bots", "PRIME ZONE", "Referral", "Redeem Code",
    "Status", "Help", "Channel", "Support", "Admin Panel"
})
def bottom_menu_handler(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    send_typing(chat_id)
    register_user(user_id)

    if text == "Upload Bot":
        bot.send_message(
            chat_id,
            f'{pe("rocket", "📥")} Send your <code>.py</code> file here.\n\n'
            f'{pe("bell", "⏳")} After upload, Admin will review & approve.\n'
            f'{pe("check", "✅")} You will be notified once done.',
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(user_id),
        )
    elif text == "My Bots":
        _show_my_bots(chat_id, user_id)
    elif text == "Free Features":
        msg = (
            f'{pe("diamond", "💎")} <b>FREE FEATURES</b>\n'
            f'{pe("crown", "👑")} <b>{OWNER_NAME}</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("check", "✅")} Full hosting access: <b>FREE</b>\n'
            f'{pe("bot", "📦")} Host up to <code>{config["free_limit"]}</code> bots\n'
            f'{pe("rocket", "⚡")} Auto Crash Guard: <b>ON</b>\n'
            f'{pe("check", "🟢")} No subscription required\n'
            f'{pe("check", "🟢")} No mandatory channel join'
        )
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=main_reply_keyboard(user_id))
    elif text == "Referral":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        ref_count = row['referral_count'] if row else 0
        conn.close()
        bot_user = get_bot_username()
        ref_link = f"https://t.me/{bot_user}?start=ref_{user_id}"
        msg = (
            f'{pe("people", "👥")} <b>Referral Program</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("gift", "🎁")} Invite friends and share the bot.\n\n'
            f'{pe("link", "🔗")} Your link:\n<code>{ref_link}</code>\n\n'
            f'{pe("star", "📊")} Referrals: <code>{ref_count}</code>\n'
            f'{pe("check", "✅")} Hosting access is already <b>FREE</b>.'
        )
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=main_reply_keyboard(user_id))
    elif text == "Redeem Code":
        m = bot.send_message(
            chat_id,
            f'{pe("gift", "🎟️")} Enter your <b>Prime Coupon Code</b>:',
            parse_mode="HTML",
        )
        bot.register_next_step_handler(m, process_claim_code)
    elif text == "Status":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM hosted_bots WHERE status != 'pending'")
        total = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as running FROM hosted_bots WHERE status='running'")
        running = cursor.fetchone()['running']
        cursor.execute("SELECT COUNT(*) as pending FROM hosted_bots WHERE status='pending'")
        pending = cursor.fetchone()['pending']
        conn.close()
        msg = (
            f'{pe("settings", "🖥️")} <b>Server Status</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("bot", "🤖")} Hosted Bots: <code>{total}</code>\n'
            f'{pe("check", "🟢")} Running: <code>{running}</code>\n'
            f'{pe("bell", "⏳")} Pending: <code>{pending}</code>'
        )
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=main_reply_keyboard(user_id))
    elif text == "Help":
        msg = (
            f'{pe("bell", "❓")} <b>Help Guide</b>\n'
            f'{pe("crown", "👑")} <b>{OWNER_NAME}</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("rocket", "1️⃣")} Upload a <code>.py</code> file\n'
            f'{pe("bell", "2️⃣")} Wait for Admin approval\n'
            f'{pe("check", "3️⃣")} Once approved → <b>My Bots</b> → Start\n'
            f'{pe("card", "4️⃣")} Check Live Logs if needed\n\n'
            f'{pe("spark", "💡")} Libraries auto-install after approval.'
        )
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=main_reply_keyboard(user_id))
    elif text == "Channel":
        ch = config.get("channel_username", "").strip()
        if ch:
            bot.send_message(chat_id, f"📢 Channel: https://t.me/{ch}", reply_markup=main_reply_keyboard(user_id))
        else:
            bot.send_message(chat_id, "📢 Channel not set yet.", reply_markup=main_reply_keyboard(user_id))
    elif text == "Support":
        ad = config.get("admin_username", "").strip()
        if ad:
            bot.send_message(chat_id, f"📞 Support: https://t.me/{ad}", reply_markup=main_reply_keyboard(user_id))
        else:
            bot.send_message(chat_id, "📞 Support not set yet.", reply_markup=main_reply_keyboard(user_id))
    elif text == "Admin Panel":
        if user_id != ADMIN_ID:
            return
        msg = (
            f'{pe("settings", "⚙️")} <b>ADMIN PANEL</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("star", "🏷")} Brand: <b>{brand()}</b>\n'
            f'{pe("bot", "📦")} Free Limit: <code>{config["free_limit"]}</code> bots\n'
            f'{pe("link", "📢")} Channel: @{config.get("channel_username") or "-"}\n'
            f'{pe("user", "📞")} Admin: @{config.get("admin_username") or "-"}\n'
            f'{pe("bot", "🤖")} Bot: @{config.get("bot_username") or "-"}\n\n'
            f'Select option:'
        )
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=admin_panel_keyboard())


def _show_my_bots(chat_id, user_id, msg_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE user_id = ? ORDER BY id DESC", (user_id,))
    bots = cursor.fetchall()
    conn.close()
    if not bots:
        bot.send_message(
            chat_id,
            f'{pe("cross", "❌")} No bots found.',
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(user_id),
        )
        return
    markup = types.InlineKeyboardMarkup()
    for b in bots:
        if b['status'] == 'pending':
            label = f"⏳ {b['filename']} (Pending)"
        else:
            alive = b['status'] == 'running' and b['pid'] and is_process_alive(b['pid'])
            icon = "🟢" if alive else "🔴"
            label = f"{icon} {b['filename']}"
        markup.add(ibtn(label[:40], callback_data=f"manage_{b['id']}", style="primary" if b['status'] != 'pending' else "danger", icon="bot"))
    markup.add(ibtn("Main Menu", callback_data="main_menu", style="danger", icon="top"))
    send_or_edit(chat_id, "⚙️ *Your Bots:*", markup, msg_id)


# ==================== CALLBACKS ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data
    send_typing(chat_id)

    # ---------- APPROVE / REJECT (Admin only) ----------
    if data.startswith("approve_"):
        if user_id != ADMIN_ID:
            return
        bot_id = int(data.split("_")[1])
        process_approve(chat_id, bot_id, msg_id)
        return

    if data.startswith("reject_"):
        if user_id != ADMIN_ID:
            return
        bot_id = int(data.split("_")[1])
        process_reject(chat_id, bot_id, msg_id)
        return

    if data == "force_verify":
        if check_user_in_force_channel(user_id):
            credit_referral(user_id)
            try:
                bot.edit_message_text(
                    f'{pe("check", "✅")} <b>Verified!</b>\nAb /start dabao.',
                    chat_id, msg_id, parse_mode="HTML",
                )
            except Exception:
                bot.send_message(chat_id, f'{pe("check", "✅")} Verified! Ab /start dabao.', parse_mode="HTML")
            bot.send_message(
                chat_id,
                f'{pe("wave", "👋")} Welcome back — use menu below.',
                parse_mode="HTML",
                reply_markup=main_reply_keyboard(user_id),
            )
        else:
            bot.answer_callback_query(call.id, "Pehle channel join karo!", show_alert=True)
        return

    # Admin view any user's bot logs
    if data.startswith("adminlog_"):
        if user_id != ADMIN_ID:
            return
        try:
            bid = int(data.replace("adminlog_", "", 1))
        except ValueError:
            return
        _admin_send_bot_log(chat_id, bid, msg_id)
        return

    if data.startswith("adminlogs_user_"):
        if user_id != ADMIN_ID:
            return
        try:
            tuid = int(data.replace("adminlogs_user_", "", 1))
        except ValueError:
            return
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
        _admin_show_user_bots_logs(chat_id, tuid)
        return

    if data == "main_menu":
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            f'{pe("top", "🏠")} <b>Main Menu</b>\n{pe("top", "👇")} Use buttons below:',
            parse_mode="HTML",
            reply_markup=main_reply_keyboard(user_id),
        )

    elif data == "free_access_info":
        msg = (
            f'{pe("check", "🟢")} <b>FREE ACCESS</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'All users get the full hosting feature set.\n'
            f'No subscription and no mandatory channel join.'
        )
        send_or_edit(chat_id, msg, main_reply_keyboard(user_id), msg_id)

    elif data == "prime_zone":
        status = "👑 PRIME VIP" if is_prime_user(user_id) else "🆓 FREE"
        msg = (
            f"💎 *PRIME ZONE*\n"
            f"👑 *{OWNER_NAME}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: *{status}*\n\n"
            f"🔥 *Prime Benefits*\n"
            f"├ 🚀 Host up to `{config['prime_limit']}` bots\n"
            f"├ ⚡ Priority execution\n"
            f"├ 🛡 Auto Crash Guard\n"
            f"└ 🎧 Priority support\n\n"
            f"🎟️ Redeem codes or gift Prime from here."
        )
        send_or_edit(chat_id, msg, prime_zone_keyboard(), msg_id)

    elif data == "prime_expire_check":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT prime_expire FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if is_prime_user(user_id):
            expire = row['prime_expire'] if row and row['prime_expire'] else "Unlimited (Admin)"
            msg = f"🌟 *Prime Active*\n⏳ Expires: `{expire}`"
        else:
            msg = "❌ No active Prime subscription."
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="prime_zone"))
        send_or_edit(chat_id, msg, markup, msg_id)

    elif data == "gift_prime":
        if not is_prime_user(user_id):
            bot.send_message(chat_id, "❌ Only Prime members can gift.")
            return
        m = bot.send_message(chat_id, "🎁 Enter target user's *numeric Telegram ID*:")
        bot.register_next_step_handler(m, process_gift_prime)

    elif data == "upload_info":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(
            chat_id,
            "📥 Send your `.py` file here.\n\n"
            "⏳ After upload, Admin will review & approve.\n"
            "You will be notified once done.",
            markup, msg_id
        )

    elif data == "referral_info":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        ref_count = row['referral_count'] if row else 0
        conn.close()
        bot_user = config.get("bot_username", "bot")
        ref_link = f"https://t.me/{bot_user}?start=ref_{user_id}"
        msg = (
            f"👥 *Referral Program*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Invite friends → Get FREE Prime!\n\n"
            f"🔗 Your link:\n`{ref_link}`\n\n"
            f"📊 Referrals: `{ref_count}`\n"
            f"🎁 Reward: *1 day Prime* every 3 invites"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, msg, markup, msg_id)

    elif data == "server_stats":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM hosted_bots WHERE status != 'pending'")
        total = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as running FROM hosted_bots WHERE status='running'")
        running = cursor.fetchone()['running']
        cursor.execute("SELECT COUNT(*) as pending FROM hosted_bots WHERE status='pending'")
        pending = cursor.fetchone()['pending']
        conn.close()
        msg = (
            f"🖥️ *Server Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Hosted Bots: `{total}`\n"
            f"🟢 Running: `{running}`\n"
            f"⏳ Pending: `{pending}`"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="server_stats"))
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, msg, markup, msg_id)

    elif data == "help_guide":
        msg = (
            f"❓ *Help Guide*\n"
            f"👑 *{OWNER_NAME}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ Upload a `.py` file\n"
            f"2️⃣ Wait for Admin approval\n"
            f"3️⃣ Once approved → *My Bots* → Start\n"
            f"4️⃣ Check *Live Logs* if needed\n\n"
            f"💡 Libraries auto-install after approval."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"))
        send_or_edit(chat_id, msg, markup, msg_id)

    elif data == "claim_code":
        m = bot.send_message(chat_id, "🎟️ Enter your *Prime Coupon Code*:")
        bot.register_next_step_handler(m, process_claim_code)

    # Admin Panel
    elif data == "admin_panel":
        if user_id != ADMIN_ID:
            return
        msg = (
            f'{pe("settings", "⚙️")} <b>ADMIN PANEL</b>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'{pe("star", "🏷")} Brand: <b>{brand()}</b>\n'
            f'{pe("bot", "📦")} Free Limit: <code>{config["free_limit"]}</code> bots\n'
            f'{pe("link", "📢")} Channel: @{config.get("channel_username") or "-"}\n'
            f'{pe("user", "📞")} Admin: @{config.get("admin_username") or "-"}\n'
            f'{pe("bot", "🤖")} Bot: @{config.get("bot_username") or "-"}\n\n'
            f'Select option:'
        )
        send_or_edit(chat_id, msg, admin_panel_keyboard(), msg_id)

    elif data == "admin_pending":
        if user_id != ADMIN_ID:
            return
        show_pending_requests(chat_id, msg_id)

    elif data == "admin_change_limits":
        if user_id != ADMIN_ID:
            return
        m = bot.send_message(chat_id, "✏️ Enter new limits:\n<code>Free, Prime</code>\nExample: <code>3, 10</code>", parse_mode="HTML")
        bot.register_next_step_handler(m, process_admin_set_limits)

    elif data == "admin_set_brand":
        if user_id != ADMIN_ID:
            return
        waiting_states[user_id] = {"action": "set_brand"}
        bot.send_message(
            chat_id,
            f'{pe("star", "🏷")} Current brand: <b>{brand()}</b>\n\n'
            f'Send new <b>Brand Name</b>\nCancel: <code>cancel</code>',
            parse_mode="HTML",
        )

    elif data == "admin_emojis":
        if user_id != ADMIN_ID:
            try:
                bot.answer_callback_query(call.id, "Admin only", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id, "Opening emoji manager...")
        except Exception:
            pass
        lines = [
            f'{pe("spark", "✨")} <b>Live Emoji Manager</b>',
            "━━━━━━━━━━━━━━━━━━━━",
            "Tap a key, then send the live emoji:",
            "",
        ]
        for k in sorted(DEFAULT_EMOJI.keys()):
            lines.append(f'• <code>{k}</code>')
        msg = "\n".join(lines)
        try:
            bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=emoji_panel_keyboard())
        except Exception as e:
            bot.send_message(chat_id, f"Emoji panel error: {str(e)[:100]}")

    elif data.startswith("setemoji_"):
        if user_id != ADMIN_ID:
            return
        key = data.replace("setemoji_", "", 1)
        if key not in DEFAULT_EMOJI:
            try:
                bot.answer_callback_query(call.id, "Unknown key", show_alert=True)
            except Exception:
                pass
            bot.send_message(chat_id, "❌ Unknown emoji key.")
            return
        waiting_states[user_id] = {"action": "set_emoji", "key": key}
        try:
            bot.answer_callback_query(call.id, f"Send emoji for {key}")
        except Exception:
            pass
        bot.send_message(
            chat_id,
            f'✨ Change <b>{html_mod.escape(key)}</b>\n'
            f'Current ID: <code>{html_mod.escape(str(EMOJI_IDS.get(key) or ""))}</code>\n\n'
            f'👉 Ab sirf <b>custom / live emoji</b> bhejo.\n'
            f'ID type ki zarurat nahi.\n'
            f'Cancel: <code>cancel</code>',
            parse_mode="HTML",
        )

    elif data == "admin_set_force":
        if user_id != ADMIN_ID:
            return
        cur = config.get("force_channel") or "none"
        m = bot.send_message(
            chat_id,
            f'{pe("lock", "🔒")} Force-join channel (referral verify)\n'
            f'Current: <code>{cur}</code>\n\n'
            f'Send channel username without @\n'
            f'Disable: <code>none</code>\n'
            f'<i>Bot must be admin in that channel.</i>',
            parse_mode="HTML",
        )
        bot.register_next_step_handler(m, process_admin_set_force)

    elif data == "admin_set_channel":
        if user_id != ADMIN_ID:
            return
        m = bot.send_message(chat_id, "✏️ Enter Channel username (without @):\nSend <code>none</code> to disable.", parse_mode="HTML")
        bot.register_next_step_handler(m, process_admin_set_channel)

    elif data == "admin_set_admin_user":
        if user_id != ADMIN_ID:
            return
        m = bot.send_message(chat_id, "✏️ Enter Admin username (without @):", parse_mode="HTML")
        bot.register_next_step_handler(m, process_admin_set_admin_user)

    elif data == "admin_set_bot_user":
        if user_id != ADMIN_ID:
            return
        m = bot.send_message(chat_id, "✏️ Enter Bot username (without @):", parse_mode="HTML")
        bot.register_next_step_handler(m, process_admin_set_bot_user)

    elif data == "admin_reload":
        if user_id != ADMIN_ID:
            return
        load_config()
        bot.send_message(chat_id, f'{pe("check", "✅")} Config reloaded.', parse_mode="HTML")

    elif data == "my_bots":
        _show_my_bots(chat_id, user_id, msg_id)

    elif data.startswith("manage_"):
        bot_id = int(data.split("_")[1])
        render_bot_control(chat_id, bot_id, msg_id, user_id)

    elif data.startswith("startbot_"):
        bot_id = int(data.split("_")[1])
        start_bot_action(chat_id, bot_id, msg_id, user_id)

    elif data.startswith("stopbot_"):
        bot_id = int(data.split("_")[1])
        stop_bot_action(chat_id, bot_id, msg_id, user_id)

    elif data.startswith("logbot_"):
        bot_id = int(data.split("_")[1])
        show_logs_action(chat_id, bot_id, msg_id)

    elif data.startswith("clearlog_"):
        bot_id = int(data.split("_")[1])
        clear_logs_action(chat_id, bot_id, msg_id)

    elif data.startswith("piplist_"):
        bot_id = int(data.split("_")[1])
        show_pip_action(chat_id, bot_id, msg_id)

    elif data.startswith("delbot_"):
        bot_id = int(data.split("_")[1])
        delete_bot_action(chat_id, bot_id, msg_id, user_id)

# ==================== APPROVE / REJECT ====================
def process_approve(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND status = 'pending'", (bot_id,))
    b = cursor.fetchone()

    if not b:
        bot.send_message(chat_id, "❌ Request not found or already processed.")
        conn.close()
        return

    # Safety: block if file uses same token as this hosting bot
    try:
        analysis = analyze_uploaded_file(b['filepath'])
        if analysis.get("same_as_host"):
            conn.close()
            bot.send_message(
                chat_id,
                "🚫 *BLOCKED*\nThis file uses the *same bot token* as the hosting bot.\n"
                "Approving would break the host. Change the token in the file first.",
                parse_mode="Markdown",
            )
            return
    except Exception:
        pass

    # Change status to stopped (approved & ready)
    cursor.execute("UPDATE hosted_bots SET status = 'stopped' WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()

    # Auto install packages
    installed, failed = auto_install_packages(b['filepath'], b['logpath'])

    # Notify Admin
    try:
        bot.edit_message_caption(
            caption=f"✅ *APPROVED*\n📄 `{b['filename']}`\n👤 User: `{b['user_id']}`",
            chat_id=chat_id,
            message_id=msg_id,
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(chat_id, f"✅ Approved `{b['filename']}` for user `{b['user_id']}`")

    # Notify User
    try:
        extra = ""
        if installed:
            extra += f"\n📦 Installed: `{', '.join(installed)}`"
        if failed:
            extra += f"\n⚠️ Failed: `{', '.join(failed)}`"
        bot.send_message(
            b['user_id'],
            f"🎉 *Your bot has been APPROVED!*\n\n"
            f"📄 File: `{b['filename']}`\n"
            f"{extra}\n\n"
            f"📱 Go to *My Bots* → Start",
            parse_mode="Markdown"
        )
    except Exception:
        pass

def process_reject(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ? AND status = 'pending'", (bot_id,))
    b = cursor.fetchone()

    if not b:
        bot.send_message(chat_id, "❌ Request not found or already processed.")
        conn.close()
        return

    # Delete files
    for path in [b['filepath'], b['logpath']]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    cursor.execute("DELETE FROM hosted_bots WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()

    try:
        bot.edit_message_caption(
            caption=f"❌ *REJECTED*\n📄 `{b['filename']}`\n👤 User: `{b['user_id']}`",
            chat_id=chat_id,
            message_id=msg_id,
            parse_mode="Markdown"
        )
    except Exception:
        bot.send_message(chat_id, f"❌ Rejected `{b['filename']}`")

    try:
        bot.send_message(
            b['user_id'],
            f"❌ *Your hosting request was REJECTED*\n\n"
            f"📄 File: `{b['filename']}`\n"
            f"Contact admin for more info.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

def show_pending_requests(chat_id, msg_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE status = 'pending' ORDER BY id ASC")
    pending = cursor.fetchall()
    conn.close()

    if not pending:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel"))
        send_or_edit(chat_id, "✅ No pending requests.", markup, msg_id)
        return

    msg = f"📋 *Pending Requests* ({len(pending)})\n━━━━━━━━━━━━━━━━━━━━\n"
    markup = types.InlineKeyboardMarkup()
    for b in pending:
        msg += f"• `{b['filename']}` — User `{b['user_id']}`\n"
        markup.add(
            ibtn(f"OK {b['filename'][:18]}", callback_data=f"approve_{b['id']}", style="primary", icon="check"),
            ibtn("No", callback_data=f"reject_{b['id']}", style="danger", icon="cross"),
        )
    markup.add(ibtn("Admin Panel", callback_data="admin_panel", style="danger", icon="settings"))
    send_or_edit(chat_id, msg, markup, msg_id)

# ==================== ADMIN PROCESSORS ====================
def process_admin_set_limits(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.strip().split(",")
        if len(parts) != 2:
            raise ValueError
        free = int(parts[0].strip())
        prime = int(parts[1].strip())
        # One free limit for everyone; ignore the old Prime tier value.
        set_config_value("free_limit", str(prime))
        set_config_value("prime_limit", str(prime))
        bot.reply_to(message, f'{pe("check", "✅")} Free limit updated: <code>{prime}</code> bots', parse_mode="HTML")
    except Exception:
        bot.reply_to(message, "❌ Invalid format. Use: <code>3, 10</code>", parse_mode="HTML")

def process_admin_set_brand(message):
    if message.from_user.id != ADMIN_ID:
        return
    val = (message.text or "").strip()
    if not val or len(val) > 64:
        bot.reply_to(message, "❌ Invalid brand name (1-64 chars).")
        return
    set_config_value("brand_name", val)
    bot.reply_to(message, f'{pe("check", "✅")} Brand updated to: <b>{val}</b>', parse_mode="HTML")


def _extract_custom_emoji_id(message):
    """Pull custom_emoji_id from a Telegram message (entities / caption)."""
    if not message:
        return None
    for attr in ("entities", "caption_entities"):
        ents = getattr(message, attr, None) or []
        for e in ents:
            # object style
            cid = getattr(e, "custom_emoji_id", None)
            if cid:
                return str(cid)
            # dict style (some telebot versions)
            if isinstance(e, dict):
                cid = e.get("custom_emoji_id")
                if cid:
                    return str(cid)
            # type check
            etype = str(getattr(e, "type", "") or (e.get("type") if isinstance(e, dict) else "")).lower()
            if etype in ("custom_emoji", "customemoji"):
                cid = getattr(e, "custom_emoji_id", None) or (e.get("custom_emoji_id") if isinstance(e, dict) else None)
                if cid:
                    return str(cid)
    return None


def process_admin_set_emoji(message, key):
    if message.from_user.id != ADMIN_ID:
        return
    eid = _extract_custom_emoji_id(message)
    text = (message.text or message.caption or "").strip()
    # Optional: still accept plain digits ID
    if not eid and text.isdigit() and len(text) >= 10:
        eid = text
    if not eid:
        bot.reply_to(
            message,
            f'{pe("cross", "❌")} Custom emoji nahi mila.\n'
            f'Sirf <b>live / custom emoji</b> wala message bhejo (text mat likho).',
            parse_mode="HTML",
        )
        return
    set_config_value(f"emoji_{key}", eid)
    bot.reply_to(
        message,
        f'{pe("check", "✅")} <b>{key}</b> set ho gaya!\n'
        f'Preview: {pe(key, "✨")}\n'
        f'<code>{eid}</code>',
        parse_mode="HTML",
    )


def process_admin_set_force(message):
    if message.from_user.id != ADMIN_ID:
        return
    set_config_value("force_channel", "")
    bot.reply_to(message, f'{pe("check", "✅")} Must-join channel is permanently disabled.', parse_mode="HTML")


def process_admin_set_channel(message):
    if message.from_user.id != ADMIN_ID:
        return
    val = message.text.strip().lstrip("@")
    if val.lower() == "none":
        val = ""
    set_config_value("channel_username", val)
    bot.reply_to(message, f'{pe("check", "✅")} Channel set to: <code>{val or "disabled"}</code>', parse_mode="HTML")

def process_admin_set_admin_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    val = message.text.strip().lstrip("@")
    set_config_value("admin_username", val)
    bot.reply_to(message, f'{pe("check", "✅")} Admin username: @{val}', parse_mode="HTML")

def process_admin_set_bot_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    val = message.text.strip().lstrip("@")
    set_config_value("bot_username", val)
    bot.reply_to(message, f'{pe("check", "✅")} Bot username: @{val}', parse_mode="HTML")

# ==================== BOT CONTROL ====================
def render_bot_control(chat_id, bot_id, msg_id=None, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()

    if not b:
        bot.send_message(chat_id, "❌ Bot not found.")
        return

    # Security: only owner or admin
    if user_id and user_id != ADMIN_ID and b['user_id'] != user_id:
        bot.send_message(chat_id, "❌ Access denied.")
        return

    if b['status'] == 'pending':
        msg = (
            f"⏳ *Pending Approval*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📄 File: `{b['filename']}`\n"
            f"📊 Status: Waiting for Admin\n"
            f"📅 Uploaded: `{b['created_at'] or 'N/A'}`\n\n"
            f"Please wait for admin to approve."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 My Bots", callback_data="my_bots"))
        send_or_edit(chat_id, msg, markup, msg_id)
        return

    alive = b['status'] == 'running' and b['pid'] and is_process_alive(b['pid'])
    status = "🟢 Running" if alive else "🔴 Stopped"

    msg = (
        f"🤖 *Bot Control*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 File: `{b['filename']}`\n"
        f"📊 Status: {status}\n"
        f"🆔 PID: `{b['pid'] if alive else 'N/A'}`"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    if alive:
        markup.add(ibtn("Stop", callback_data=f"stopbot_{b['id']}", style="danger", icon="cross"))
    else:
        markup.add(ibtn("Start", callback_data=f"startbot_{b['id']}", style="primary", icon="rocket"))
    markup.add(
        ibtn("Logs", callback_data=f"logbot_{b['id']}", style="primary", icon="bell"),
        ibtn("Clear Logs", callback_data=f"clearlog_{b['id']}", style="danger", icon="warning"),
    )
    markup.add(
        ibtn("Packages", callback_data=f"piplist_{b['id']}", style="primary", icon="card"),
        ibtn("Refresh", callback_data=f"manage_{b['id']}", style="primary", icon="refresh"),
    )
    markup.add(ibtn("Delete", callback_data=f"delbot_{b['id']}", style="danger", icon="cross"))
    markup.add(ibtn("My Bots", callback_data="my_bots", style="danger", icon="bot"))
    send_or_edit(chat_id, msg, markup, msg_id)

def start_bot_action(chat_id, bot_id, msg_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()

    if not b or b['status'] == 'pending':
        conn.close()
        bot.send_message(chat_id, "❌ Cannot start. Bot is pending approval.")
        return

    if user_id and user_id != ADMIN_ID and b['user_id'] != user_id:
        conn.close()
        return

    if not b['pid'] or not is_process_alive(b['pid']):
        try:
            process = safe_popen(b['filepath'], b['logpath'])
            cursor.execute("UPDATE hosted_bots SET status = 'running', pid = ? WHERE id = ?", (process.pid, bot_id))
            conn.commit()
        except Exception as e:
            try:
                with open(b['logpath'], 'a', encoding='utf-8') as f:
                    f.write(f"[START ERROR] {str(e)}\n")
            except Exception:
                pass
    conn.close()
    render_bot_control(chat_id, bot_id, msg_id, user_id)

def stop_bot_action(chat_id, bot_id, msg_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()

    if not b:
        conn.close()
        return

    if user_id and user_id != ADMIN_ID and b['user_id'] != user_id:
        conn.close()
        return

    if b['pid']:
        safe_kill(b['pid'])
        try:
            with open(b['logpath'], 'a', encoding='utf-8') as f:
                f.write(f"\n--- [STOPPED {datetime.now()}] ---\n")
        except Exception:
            pass

    cursor.execute("UPDATE hosted_bots SET status = 'stopped', pid = NULL WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()
    render_bot_control(chat_id, bot_id, msg_id, user_id)

def show_logs_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()

    if not b or not os.path.exists(b['logpath']):
        bot.send_message(chat_id, "❌ Log file not found.")
        return

    try:
        with open(b['logpath'], 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        last = "".join(lines[-40:]).strip()
        if not last:
            last = "No logs yet."
        if len(last) > 3500:
            last = last[-3500:]
        msg = f"📜 *Logs* — `{b['filename']}`\n```\n{last}\n```"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            ibtn("Refresh", callback_data=f"logbot_{bot_id}", style="primary", icon="refresh"),
            ibtn("Clear", callback_data=f"clearlog_{bot_id}", style="danger", icon="warning"),
        )
        markup.add(ibtn("Back", callback_data=f"manage_{bot_id}", style="danger", icon="top"))
        send_or_edit(chat_id, msg, markup, msg_id)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: `{str(e)}`")

def clear_logs_action(chat_id, bot_id, msg_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT logpath FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()
    if b and os.path.exists(b['logpath']):
        try:
            with open(b['logpath'], 'w', encoding='utf-8') as f:
                f.write(f"--- [LOGS CLEARED {datetime.now()}] ---\n")
        except Exception:
            pass
    show_logs_action(chat_id, bot_id, msg_id)

def show_pip_action(chat_id, bot_id, msg_id):
    try:
        res = subprocess.run([sys.executable, "-m", "pip", "list", "--format=columns"],
                             capture_output=True, text=True, timeout=20)
        packages = res.stdout[:2800] if res.stdout else "No packages."
        msg = f"📋 *Installed Packages*\n```\n{packages}\n```"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data=f"manage_{bot_id}"))
        send_or_edit(chat_id, msg, markup, msg_id)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: `{str(e)}`")

def delete_bot_action(chat_id, bot_id, msg_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()

    if not b:
        conn.close()
        return

    if user_id and user_id != ADMIN_ID and b['user_id'] != user_id:
        conn.close()
        return

    if b['pid']:
        safe_kill(b['pid'])

    for path in [b['filepath'], b['logpath']]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    cursor.execute("DELETE FROM hosted_bots WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 My Bots", callback_data="my_bots"))
    send_or_edit(chat_id, "🗑️ Bot & logs deleted.", markup, msg_id)

# ==================== USER PROCESSORS ====================
def process_claim_code(message):
    if not message.text:
        bot.reply_to(message, "❌ Please send a text code.")
        return
    code = message.text.strip()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prime_codes WHERE code = ?", (code,))
    row = cursor.fetchone()
    if row:
        add_prime_days(message.from_user.id, row['days'])
        cursor.execute("DELETE FROM prime_codes WHERE code = ?", (code,))
        conn.commit()
        bot.reply_to(message, f"🎉 Activated *{row['days']} days* of Prime VIP!", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Invalid code.")
    conn.close()

def process_gift_prime(message):
    if not message.text or not message.text.strip().isdigit():
        bot.reply_to(message, "❌ Invalid numeric Telegram ID.")
        return
    try:
        friend_id = int(message.text.strip())
        add_prime_days(friend_id, 7)
        bot.reply_to(message, f"🎁 Gifted *7 days* Prime to `{friend_id}`!", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ Error occurred.")

@bot.message_handler(commands=['logs'])
def admin_logs_cmd(message):
    """Admin: /logs <file_id|user_id>  OR prompt."""
    if message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    target = None
    if len(parts) >= 2 and parts[1].strip().isdigit():
        target = int(parts[1].strip())
    if target is not None:
        # Prefer File/Bot ID if exists in hosted_bots
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM hosted_bots WHERE id = ?", (target,))
        as_bot = cursor.fetchone()
        conn.close()
        if as_bot:
            _admin_send_bot_log(message.chat.id, target)
            return
        _admin_show_user_bots_logs(message.chat.id, target)
        return
    waiting_states[message.from_user.id] = {"action": "admin_logs_uid"}
    bot.reply_to(
        message,
        f'{pe("bell", "📜")} <b>Admin Logs</b>\n'
        f'Send <b>File ID</b> (request me dikhta hai) ya <b>User ID</b>.\n\n'
        f'Examples:\n'
        f'• <code>/logs 12</code> → File ID 12 ke logs\n'
        f'• <code>/logs 8824515191</code> → us user ke saare bots\n'
        f'Cancel: <code>cancel</code>',
        parse_mode="HTML",
    )


def _admin_show_user_bots_logs(chat_id, target_uid):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM hosted_bots WHERE user_id = ? ORDER BY id DESC",
        (target_uid,),
    )
    bots = cursor.fetchall()
    conn.close()
    if not bots:
        bot.send_message(
            chat_id,
            f'{pe("cross", "❌")} User <code>{target_uid}</code> ke koi bots nahi.',
            parse_mode="HTML",
        )
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    lines = [
        f'{pe("bell", "📜")} <b>Logs — user</b> <code>{target_uid}</code>',
        "━━━━━━━━━━━━━━━━━━━━",
        f"Total bots: <b>{len(bots)}</b>",
        "Select a bot:",
        "",
    ]
    for b in bots:
        alive = b["status"] == "running" and b["pid"] and is_process_alive(b["pid"])
        st = "🟢 RUN" if alive else ("⏳ PEND" if b["status"] == "pending" else "🔴 STOP")
        fname = b["filename"] or "?"
        lines.append(f"• {st} <code>{html_mod.escape(fname)}</code> (id {b['id']})")
        markup.add(
            ibtn(
                f"{st} {fname[:28]}",
                callback_data=f"adminlog_{b['id']}",
                style="primary" if alive else "danger",
                icon="bell",
            )
        )
    bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML", reply_markup=markup)


def _admin_send_bot_log(chat_id, bot_id, msg_id=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosted_bots WHERE id = ?", (bot_id,))
    b = cursor.fetchone()
    conn.close()
    if not b:
        bot.send_message(chat_id, "❌ Bot not found.")
        return
    logpath = b["logpath"]
    fname = b["filename"] or "?"
    uid = b["user_id"]
    if not logpath or not os.path.exists(logpath):
        bot.send_message(
            chat_id,
            f'{pe("cross", "❌")} Log missing for <code>{html_mod.escape(fname)}</code>',
            parse_mode="HTML",
        )
        return
    try:
        with open(logpath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        last = "".join(lines[-50:]).strip() or "No log lines yet."
        if len(last) > 3500:
            last = last[-3500:]
        alive = b["status"] == "running" and b["pid"] and is_process_alive(b["pid"])
        st = "🟢 Running" if alive else f"Status: {b['status']}"
        text = (
            f'{pe("bell", "📜")} <b>Logs</b>\n'
            f'User: <code>{uid}</code>\n'
            f'File: <code>{html_mod.escape(fname)}</code>\n'
            f'{st} | PID: <code>{b["pid"] or "N/A"}</code>\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'<pre>{html_mod.escape(last)}</pre>'
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(
            ibtn("Refresh", callback_data=f"adminlog_{bot_id}", style="primary", icon="refresh"),
            ibtn("User bots", callback_data=f"adminlogs_user_{uid}", style="danger", icon="user"),
        )
        if msg_id:
            try:
                bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML", reply_markup=markup)
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Log read error: {str(e)[:120]}")


@bot.message_handler(commands=['genkey'])
def gen_key_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        days = int(message.text.split()[1])
    except Exception:
        days = 30
    code = "PRIME-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO prime_codes (code, days) VALUES (?, ?)", (code, days))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"🎟️ *Prime Code*\n`{code}` ({days} days)", parse_mode="Markdown")

# ==================== FLASK / RENDER HEALTH SERVER ====================
app = Flask(__name__)

@app.get("/")
def home():
    return "Rᴜsʜᴇʀ Kɪɴɢ 👑 is running!", 200

@app.get("/health")
def health():
    return {"status": "ok", "bot": "Rᴜsʜᴇʀ Kɪɴɢ 👑"}, 200

def run_web_server():
    import os
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)

# ==================== START ====================
if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    print(f"👑 {OWNER_NAME}")
    print(f"⚡ {brand()} v5.2 (Admin Approval)")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ FREE hosting enabled | Limit: {config['free_limit']} bots | Must-join: OFF")
    try:
        uname = get_bot_username()
        print(f"✅ Bot Username: @{uname}")
    except Exception as e:
        print(f"⚠️ get_me failed: {e}")
    print(f"✅ Token loaded: {'Yes' if BOT_TOKEN else 'No'}")

    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=10
    )
