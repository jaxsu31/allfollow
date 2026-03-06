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
    level=logging.DEBUG,  # DEBUG seviyesine çekildi
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
            'raw_error': data.get('raw_error'),
            'created_at': data.get('created_at', datetime.now().isoformat())
        }

# DÜZELTİLMİŞ LOGIN SCRIPT - GERÇEK ZAMANLI LOG
LOGIN_SCRIPT = r'''
import sys
import json
import time
import os

# ARGÜMANLAR
USERNAME = sys.argv[1] if len(sys.argv) > 1 else ""
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""
PROXY = sys.argv[3] if len(sys.argv) > 3 else None

# LOG DOSYASI - Anlık yazma
LOG_FILE = f"/tmp/ig_realtime_{USERNAME}.log"
log_f = open(LOG_FILE, "w", buffering=1)

def log(msg):
    timestamp = time.strftime('%H:%M:%S')
    line = f"{timestamp} | {msg}"
    log_f.write(line + "\n")
    log_f.flush()
    # Hem dosyaya hem stderr'e yaz
    print(line, file=sys.stderr)

# BAŞLANGIÇ LOG
log("=" * 60)
log(f"🚀 SCRIPT BAŞLADI")
log(f"👤 Username: {USERNAME}")
log(f"🔑 Password length: {len(PASSWORD)}")
log(f"🔑 Password first 3: {PASSWORD[:3]}***")
log(f"🌐 Proxy: {PROXY[:20] + '...' if PROXY else 'YOK'}")
log(f"📁 Log file: {LOG_FILE}")
log("=" * 60)

# ŞİFRE KONTROLÜ
if not PASSWORD:
    log("❌ HATA: Şifre boş!")
    print(json.dumps({"status": "error", "error": "Şifre boş"}))
    sys.exit(1)

if len(PASSWORD) < 3:
    log(f"❌ HATA: Şifre çok kısa ({len(PASSWORD)} karakter)")
    print(json.dumps({"status": "error", "error": "Şifre çok kısa"}))
    sys.exit(1)

log("✅ Şifre kontrolü tamam")

# INSTAGRAPI IMPORT
log("📦 instagrapi import ediliyor...")
try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        ChallengeRequired, LoginRequired, 
        PleaseWaitFewMinutes, BadPassword,
        TwoFactorRequired, ClientError
    )
    log("✅ instagrapi import BAŞARILI")
except Exception as e:
    log(f"❌ instagrapi import HATASI: {type(e).__name__}: {e}")
    print(json.dumps({"status": "error", "error": f"Import hatası: {str(e)}"}))
    sys.exit(1)

# ANA İŞLEM
def main():
    try:
        log("")
        log("🔧 Client oluşturuluyor...")
        cl = Client()
        log("✅ Client oluşturuldu")
        
        # PROXY AYARLA
        if PROXY and PROXY != "None" and PROXY != "":
            try:
                log(f"🌐 Proxy ayarlanıyor: {PROXY[:30]}...")
                cl.set_proxy(PROXY)
                log("✅ Proxy ayarlandı")
            except Exception as e:
                log(f"⚠️ Proxy hatası (devam ediliyor): {e}")
        else:
            log("ℹ️ Proxy kullanılmıyor")
        
        # TIMEOUT AYARLA
        cl.request_timeout = 60
        cl.delay_range = [2, 5]
        log(f"⏱️ Timeout: {cl.request_timeout}s")
        
        # LOGIN DENE
        log("")
        log("🔐🔐🔐 INSTAGRAM LOGIN BAŞLIYOR 🔐🔐🔐")
        log(f"👉 cl.login({USERNAME}, {'*' * len(PASSWORD)})")
        log("")
        
        login_start = time.time()
        
        try:
            # GERÇEK LOGIN ÇAĞRISI
            cl.login(USERNAME, PASSWORD)
            
            login_time = time.time() - login_start
            log(f"✅✅✅ LOGIN BAŞARILI! ({login_time:.1f}s) ✅✅✅")
            
            # TAKİP ET
            try:
                log("👤 Instagram ID alınıyor...")
                insta_id = cl.user_id_from_username("instagram")
                log(f"✅ ID bulundu: {insta_id}")
                
                log("➕ Takip ediliyor...")
                cl.user_follow(insta_id)
                log("✅ Takip edildi!")
                
                result = {
                    "status": "success",
                    "message": f"Giriş ve takip başarılı ({login_time:.1f}s)"
                }
            except Exception as e:
                log(f"⚠️ Takip hatası: {e}")
                result = {
                    "status": "success",
                    "message": f"Giriş başarılı ({login_time:.1f}s), takip: {str(e)}"
                }
            
            print(json.dumps(result))
            
        except BadPassword as e:
            login_time = time.time() - login_start
            log(f"❌❌❌ BadPassword ({login_time:.1f}s) ❌❌❌")
            log(f"Hata detayı: {e}")
            print(json.dumps({
                "status": "bad_password",
                "error": "Şifre yanlış veya hesap kısıtlı",
                "detail": str(e),
                "time": f"{login_time:.1f}s"
            }))
            
        except ChallengeRequired as e:
            login_time = time.time() - login_start
            log(f"⚠️⚠️⚠️ ChallengeRequired ({login_time:.1f}s) ⚠️⚠️⚠️")
            log(f"Challenge detay: {e}")
            print(json.dumps({
                "status": "challenge_required",
                "challenge_type": "code",
                "message": "Doğrulama kodu gerekli.",
                "time": f"{login_time:.1f}s"
            }))
            
        except TwoFactorRequired as e:
            login_time = time.time() - login_start
            log(f"⚠️⚠️⚠️ TwoFactorRequired ({login_time:.1f}s) ⚠️⚠️⚠️")
            print(json.dumps({
                "status": "2fa_required",
                "challenge_type": "2fa",
                "message": "2FA kodu gerekli.",
                "time": f"{login_time:.1f}s"
            }))
            
        except Exception as e:
            login_time = time.time() - login_start
            log(f"❌❌❌ Beklenmeyen hata ({login_time:.1f}s) ❌❌❌")
            log(f"Hata tipi: {type(e).__name__}")
            log(f"Hata mesajı: {e}")
            import traceback
            log(f"Traceback:\n{traceback.format_exc()}")
            print(json.dumps({
                "status": "error",
                "error": f"{type(e).__name__}: {str(e)}",
                "time": f"{login_time:.1f}s"
            }))
        
    except Exception as e:
        log(f"❌❌❌ DIŞ HATA: {type(e).__name__}: {e}")
        import traceback
        log(f"Traceback:\n{traceback.format_exc()}")
        print(json.dumps({
            "status": "error",
            "error": f"Dış hata: {str(e)}"
        }))
    finally:
        try:
            cl.logout()
            log("👋 Logout yapıldı")
        except:
            pass
        log_f.close()
        log("📁 Log dosyası kapatıldı")

if __name__ == "__main__":
    main()
'''

def run_subprocess(username, password):
    """Subprocess çalıştır - GERÇEK ZAMANLI LOG"""
    if not password:
        logger.error(f"[{username}] Şifre boş!")
        return {"status": "error", "error": "Şifre boş"}
    
    # Script'i yaz
    script_content = LOGIN_SCRIPT.replace("{USERNAME}", username)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(script_content)
        script_path = f.name
    
    logger.info(f"[{username}] 🚀 Subprocess BAŞLATILIYOR...")
    logger.info(f"[{username}] 📁 Script: {script_path}")
    logger.info(f"[{username}] 🔑 Şifre uzunluk: {len(password)}")
    
    start_time = time.time()
    
    try:
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        # Subprocess'i başlat
        process = subprocess.Popen(
            [sys.executable, '-u', script_path, username, password, PROXY_URL or "None"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd='/tmp',
            env=env
        )
        
        # GERÇEK ZAMANLI LOG TAKİBİ
        log_file_path = f"/tmp/ig_realtime_{username}.log"
        last_log_position = 0
        
        while process.poll() is None:
            # Log dosyasını oku
            try:
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r') as f:
                        f.seek(last_log_position)
                        new_lines = f.read()
                        if new_lines:
                            logger.info(f"[{username}] 📝 {new_lines.strip()}")
                            last_log_position = f.tell()
            except Exception as e:
                pass
            
            time.sleep(0.5)  # 500ms bekle
        
        # Process bitti
        stdout, stderr = process.communicate(timeout=5)
        elapsed = time.time() - start_time
        
        logger.info(f"[{username}] ✅ Subprocess tamamlandı ({elapsed:.1f}s) - Kod: {process.returncode}")
        
        # Temizlik
        try:
            os.unlink(script_path)
        except:
            pass
        
        # Son logları oku
        try:
            with open(log_file_path, 'r') as f:
                f.seek(last_log_position)
                final_logs = f.read()
                if final_logs:
                    logger.info(f"[{username}] 📝 Son loglar:\n{final_logs}")
        except:
            pass
        
        # Sonucu parse et
        if process.returncode != 0:
            stderr_short = stderr.strip()[:200] if stderr else "Boş stderr"
            logger.error(f"[{username}] ❌ Hata kodu {process.returncode}: {stderr_short}")
            return {"status": "error", "error": f"Process hatası: {stderr_short}"}
        
        # JSON bul
        lines = [l.strip() for l in stdout.split('\n') if l.strip()]
        for line in reversed(lines):
            if line.startswith('{') and line.endswith('}'):
                try:
                    return json.loads(line)
                except:
                    continue
        
        # Eğer JSON yoksa loglardan anla
        if not lines:
            return {"status": "error", "error": "Boş çıktı - Process çökmüş olabilir"}
        
        return {"status": "error", "error": f"JSON bulunamadı. Çıktı: {stdout[:200]}"}
        
    except subprocess.TimeoutExpired:
        logger.error(f"[{username}] ⏱️ TIMEOUT!")
        process.kill()
        return {"status": "error", "error": "Zaman aşımı (120s)"}
    except Exception as e:
        logger.error(f"[{username}] 💥 Exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "error": str(e)}

def do_login_task(username, password):
    """Background task"""
    # Başlangıç
    acc = get_account(username)
    if not acc:
        save_account(username, {
            'status': 'Giriş deneniyor...',
            'login_attempts': 1,
            'created_at': datetime.now().isoformat()
        })
    else:
        save_account(username, {
            **acc,
            'status': 'Giriş deneniyor...',
            'login_attempts': acc.get('login_attempts', 0) + 1
        })
    
    # Login dene
    result = run_subprocess(username, password)
    
    # Sonucu güncelle
    status = result.get("status")
    current_acc = get_account(username) or {}
    
    if status == "success":
        save_account(username, {
            **current_acc,
            'status': "AKTİF ✅ - " + result.get("message", "Başarılı"),
            'last_login': datetime.now().isoformat(),
            'challenge_pending': False
        })
    elif status == "challenge_required":
        save_account(username, {
            **current_acc,
            'status': "🔐 DOĞRULAMA KODU GEREKLİ",
            'challenge_type': result.get("challenge_type", "code"),
            'challenge_pending': True
        })
    elif status == "2fa_required":
        save_account(username, {
            **current_acc,
            'status': "🔐 2FA KODU GEREKLİ",
            'challenge_type': "2fa",
            'challenge_pending': True
        })
    elif status == "bad_password":
        # GERÇEKTEN denedi mi kontrol et
        time_spent = result.get("time", "0s")
        if time_spent == "0s" or time_spent.startswith("0."):
            # Hiç denememiş - hemen hata dönmüş
            save_account(username, {
                **current_acc,
                'status': "⚠️ HIZLI HATA - Proxy/Import sorunu olabilir",
                'raw_error': json.dumps(result)
            })
        else:
            # Gerçekten denemiş ama şifre yanlış
            save_account(username, {
                **current_acc,
                'status': "⚠️ Şifre yanlış veya hesap kısıtlı (" + time_spent + ")",
                'raw_error': json.dumps(result)
            })
    else:
        save_account(username, {
            **current_acc,
            'status': "HATA ❌ - " + result.get("error", "Bilinmeyen hata")[:80],
            'raw_error': json.dumps(result)
        })

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    try:
        data = request.get_json()
        username = data.get('u', '').strip().lower()
        password = data.get('p', '')
        
        if not username or not password:
            return jsonify(status="error", message="Eksik bilgi"), 400
        
        logger.info(f"🎯 Giriş isteği: {username} (şifre: {len(password)} karakter)")
        
        acc = get_account(username)
        if not acc:
            save_account(username, {
                'status': 'Başlatılıyor...',
                'login_attempts': 0,
                'created_at': datetime.now().isoformat()
            })
            logger.info(f"🆕 Yeni hesap oluşturuldu: {username}")
        else:
            save_account(username, {**acc, 'status': 'Başlatılıyor...'})
            logger.info(f"🔄 Hesap güncellendi: {username}")
        
        t = threading.Thread(
            target=do_login_task,
            args=(username, password),
            daemon=True
        )
        t.start()
        
        return jsonify(
            status="started",
            username=username,
            message="Giriş başlatıldı - Logları takip edin"
        )
        
    except Exception as e:
        logger.error(f"💥 Connect hatası: {e}")
        return jsonify(status="error", message=str(e)), 500

@app.route('/api/status/<username>')
def get_status(username):
    acc = get_account(username.lower())
    
    if not acc:
        return jsonify(
            status="Hesap bulunamadı", 
            exists=False,
            username=username
        )
    
    return jsonify(
        status=acc.get('status', 'Bilinmiyor'),
        exists=True,
        attempts=acc.get('login_attempts', 0),
        last_login=acc.get('last_login'),
        challenge_pending=acc.get('challenge_pending', False),
        challenge_type=acc.get('challenge_type'),
        raw_error=acc.get('raw_error', '')[:300] if acc.get('raw_error') else None,
        storage="in-memory"
    )

@app.route('/api/health')
def health():
    return jsonify(
        status="ok",
        storage="in-memory (RAM)",
        accounts_count=len(accounts_store),
        proxy=PROXY_URL[:25] + "...",
        mode="realtime-log-v3"
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TopFollow - Instagram (Log v3)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; }
        .active { display: flex; }
        .hidden { display: none !important; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fadeIn 0.4s ease-out; }
        .loader { border: 3px solid rgba(255,255,255,0.3); border-top: 3px solid white; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gradient-to-br from-purple-600 via-purple-500 to-blue-500 min-h-screen font-sans text-white">

    <!-- Login Page -->
    <div id="p1" class="page active flex-col items-center justify-center min-h-screen p-6 animate-fade-in">
        <div class="w-full max-w-[340px]">
            <div class="text-center mb-12">
                <div class="w-20 h-20 bg-white/20 rounded-3xl flex items-center justify-center mx-auto mb-4 backdrop-blur-sm shadow-lg">
                    <svg class="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                </div>
                <h1 class="text-3xl font-bold mb-1">Instagram</h1>
                <p class="text-white/70 text-sm">TopFollow Bağlantısı</p>
                <p class="text-white/40 text-xs mt-2">Gerçek Zamanlı Log v3</p>
            </div>
            
            <div class="space-y-4">
                <div class="bg-white/10 backdrop-blur-md rounded-xl p-1 border border-white/20">
                    <input id="u" type="text" placeholder="Kullanıcı adı" 
                           class="w-full bg-transparent text-white placeholder-white/60 p-4 outline-none text-base"
                           autocomplete="username">
                </div>
                
                <div class="bg-white/10 backdrop-blur-md rounded-xl p-1 border border-white/20">
                    <input id="p" type="password" placeholder="Şifre" 
                           class="w-full bg-transparent text-white placeholder-white/60 p-4 outline-none text-base"
                           autocomplete="current-password">
                </div>
                
                <button onclick="giris()" id="btn" 
                        class="w-full bg-white text-purple-600 p-4 rounded-xl font-bold text-lg shadow-lg hover:bg-gray-100 transition-all active:scale-[0.98] disabled:opacity-70 flex items-center justify-center mt-6">
                    <div id="btnLoader" class="loader hidden border-purple-600 border-t-transparent"></div>
                    <span id="btnText">Giriş Yap</span>
                </button>
            </div>
            
            <div id="errorBox" class="hidden mt-6 p-4 bg-red-500/30 border border-red-400/50 rounded-xl text-center text-sm backdrop-blur-sm"></div>
            
            <div class="mt-6 text-center">
                <a href="/api/health" target="_blank" class="text-white/40 text-xs hover:text-white/60 transition-colors block">
                    Sistem Durumu
                </a>
            </div>
        </div>
    </div>

    <!-- Status Page -->
    <div id="p2" class="page flex-col items-center justify-center min-h-screen p-6 bg-gray-50 text-gray-800 hidden">
        <div class="w-full max-w-[340px] animate-fade-in">
            <div class="bg-white rounded-3xl shadow-xl p-8 text-center mb-6 border-b-4 border-purple-500">
                <div class="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <div id="statusIcon" class="w-4 h-4 bg-purple-500 rounded-full animate-pulse"></div>
                </div>
                
                <h2 id="msg" class="text-xl font-bold text-gray-800 mb-2">Bağlanıyor...</h2>
                <p id="subMsg" class="text-gray-500 text-sm">Gerçek zamanlı loglar için Render Dashboard'u kontrol edin</p>
                
                <div id="rawError" class="hidden mt-3 p-2 bg-gray-100 rounded text-xs text-left font-mono break-all max-h-32 overflow-y-auto"></div>
            </div>

            <div class="bg-white rounded-2xl shadow-md p-5 mb-4">
                <div class="flex justify-between items-center mb-3 pb-3 border-b border-gray-100">
                    <span class="text-gray-500 text-sm">Kullanıcı</span>
                    <span id="utag" class="font-bold text-gray-800">@username</span>
                </div>
                <div class="flex justify-between items-center">
                    <span class="text-gray-500 text-sm">Durum</span>
                    <span id="statusBadge" class="bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full text-xs font-bold">Bekliyor</span>
                </div>
            </div>

            <button onclick="checkNow()" id="checkBtn"
                    class="w-full bg-purple-600 text-white p-4 rounded-xl font-bold mb-3 hover:bg-purple-700 transition-all active:scale-[0.98] shadow-lg">
                Durumu Kontrol Et
            </button>
            
            <button onclick="toggleDebug()" 
                    class="w-full bg-gray-200 text-gray-600 p-3 rounded-xl font-semibold text-sm mb-3 hover:bg-gray-300 transition-all">
                🔍 Teknik Detaylar
            </button>
            
            <button onclick="location.reload()" 
                    class="w-full bg-gray-200 text-gray-700 p-4 rounded-xl font-bold hover:bg-gray-300 transition-all active:scale-[0.98]">
                Yeniden Dene
            </button>
            
            <p class="text-center text-gray-400 text-xs mt-6">
                Otomatik: <span id="timer" class="font-bold text-purple-600">5</span>s
            </p>
        </div>
    </div>

    <script>
        let currentUser = "";
        let checkInterval = null;
        let countdown = 5;

        function showError(msg) {
            const box = document.getElementById('errorBox');
            box.textContent = msg;
            box.classList.remove('hidden');
            
            const btn = document.getElementById('btn');
            btn.disabled = false;
            document.getElementById('btnText').classList.remove('hidden');
            document.getElementById('btnLoader').classList.add('hidden');
        }

        function toggleDebug() {
            document.getElementById('rawError').classList.toggle('hidden');
        }

        async function giris() {
            const u = document.getElementById('u').value.trim().toLowerCase();
            const p = document.getElementById('p').value;

            if (!u || !p) {
                showError('Kullanıcı adı ve şifre girin');
                return;
            }

            currentUser = u;

            const btn = document.getElementById('btn');
            btn.disabled = true;
            document.getElementById('btnText').classList.add('hidden');
            document.getElementById('btnLoader').classList.remove('hidden');
            document.getElementById('errorBox').classList.add('hidden');

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);

                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u: u, p: p}),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);
                const data = await res.json();

                if (!res.ok && data.status === 'error') {
                    throw new Error(data.message || 'Sunucu hatası');
                }

                document.getElementById('p1').classList.add('hidden');
                document.getElementById('p1').classList.remove('active');
                document.getElementById('p2').classList.remove('hidden');
                document.getElementById('p2').classList.add('active');
                document.getElementById('utag').textContent = '@' + u;
                
                startChecking();

            } catch (err) {
                if (err.name === 'AbortError') {
                    showError('Sunucu yanıt vermiyor - Tekrar deneyin');
                } else {
                    showError(err.message);
                }
                
                btn.disabled = false;
                document.getElementById('btnText').classList.remove('hidden');
                document.getElementById('btnLoader').classList.add('hidden');
            }
        }

        function startChecking() {
            checkStatus();
            checkInterval = setInterval(() => {
                checkStatus();
                countdown = 5;
            }, 5000);
            
            setInterval(() => {
                if (countdown > 0) {
                    countdown--;
                    document.getElementById('timer').textContent = countdown;
                } else {
                    countdown = 5;
                }
            }, 1000);
        }

        async function checkNow() {
            const btn = document.getElementById('checkBtn');
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Kontrol ediliyor...';
            
            await checkStatus();
            
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = originalText;
            }, 800);
        }

        async function checkStatus() {
            if (!currentUser) return;
            
            try {
                const res = await fetch('/api/status/' + currentUser);
                const data = await res.json();
                
                const msgEl = document.getElementById('msg');
                const iconEl = document.getElementById('statusIcon');
                const badge = document.getElementById('statusBadge');
                const subMsg = document.getElementById('subMsg');
                const rawErrorDiv = document.getElementById('rawError');
                
                msgEl.textContent = data.status || 'Bekleniyor...';
                
                if (data.raw_error) {
                    rawErrorDiv.textContent = data.raw_error;
                }
                
                if (data.status.includes('✅')) {
                    badge.className = 'bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Aktif';
                    iconEl.className = 'w-4 h-4 bg-green-500 rounded-full';
                    subMsg.textContent = 'Başarıyla bağlandı!';
                    clearInterval(checkInterval);
                } else if (data.status.includes('HIZLI HATA')) {
                    badge.className = 'bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Başlatılamadı';
                    iconEl.className = 'w-4 h-4 bg-red-500 rounded-full';
                    subMsg.textContent = 'Proxy veya import sorunu - Logları kontrol edin';
                } else if (data.status.includes('⚠️')) {
                    badge.className = 'bg-orange-100 text-orange-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Kontrol';
                    iconEl.className = 'w-4 h-4 bg-orange-500 rounded-full animate-pulse';
                    subMsg.textContent = 'Instagram yanıt verdi ama şifre/challenge sorunu var';
                } else if (data.status.includes('❌') || data.status.includes('HATA')) {
                    badge.className = 'bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Hata';
                    iconEl.className = 'w-4 h-4 bg-red-500 rounded-full';
                    subMsg.textContent = 'Bir sorun oluştu';
                } else if (data.status.includes('🔐')) {
                    badge.className = 'bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Doğrulama';
                    iconEl.className = 'w-4 h-4 bg-yellow-500 rounded-full animate-bounce';
                }

            } catch (e) {
                console.error('Status error:', e);
            }
        }

        document.getElementById('p').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') giris();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info(f"🚀 Sunucu başlatılıyor: 0.0.0.0:{port}")
    logger.info(f"📝 Gerçek zamanlı log aktif")
    logger.info(f"🔍 Log kontrolü: Render Dashboard > Logs")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
