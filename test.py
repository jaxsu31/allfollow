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
    print(json.dumps({"status": "error", "error": f"Import hatası: {e}"}), flush=True)
    sys.exit(1)

# ... (rest of your login logic here) ...

log("🏁 Script tamamlandı")
log_f.close()
'''  # <-- THIS CLOSING ''' WAS MISSING!
