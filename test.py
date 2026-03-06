import os
import sys
import json
import time
import logging
import traceback
import subprocess
import tempfile
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "secret-key-123")

# BELLEK İÇİ VERİ DEPOLAMA
accounts_lock = threading.Lock()
accounts_store = {}

# PROXY
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"
logger.info(f"Proxy: {PROXY_URL[:30]}...")

def get_account(username):
    with accounts_lock:
        return accounts_store.get(username.lower())

def save_account(username, data):
    with accounts_lock:
        accounts_store[username.lower()] = {
            'username': username,
            'password_hash': data.get('password_hash', ''),
            'status': data.get('status', 'Beklemede'),
            'login_attempts': data.get('login_attempts', 0),
            'last_login': data.get('last_login'),
            'challenge_pending': data.get('challenge_pending', False),
            'challenge_type': data.get('challenge_type'),
            'challenge_auto_open': data.get('challenge_auto_open', False),
            'raw_error': data.get('raw_error'),
            'created_at': data.get('created_at', datetime.now().isoformat())
        }

# GELİŞMİŞ LOGIN SCRIPT - Challenge algılama iyileştirildi
LOGIN_SCRIPT = r'''
import sys
import json
import time
import os

USERNAME = sys.argv[1] if len(sys.argv) > 1 else ""
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""
PROXY = sys.argv[3] if len(sys.argv) > 3 else None

LOG_FILE = f"/tmp/ig_smart_{USERNAME}.log"
log_f = open(LOG_FILE, "w", buffering=1)

def log(msg):
    timestamp = time.strftime('%H:%M:%S')
    line = f"{timestamp} | {msg}"
    log_f.write(line + "\n")
    log_f.flush()

log("=" * 50)
log(f"🚀 SCRIPT BAŞLADI")
log(f"👤 Username: {USERNAME}")
log(f"🔑 Password: {'*' * len(PASSWORD)} ({len(PASSWORD)} chars)")
log("=" * 50)

if not PASSWORD:
    log("❌ Şifre boş!")
    print(json.dumps({"status": "error", "error": "Şifre boş"}), flush=True)
    sys.exit(1)

# INSTAGRAPI IMPORT
log("📦 Import başlıyor...")
try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        ChallengeRequired, LoginRequired, 
        PleaseWaitFewMinutes, BadPassword,
        TwoFactorRequired, ClientError
    )
    log("✅ Import OK")
except Exception as e:
    log(f"❌ Import HATASI: {e}")
    print(json.dumps
