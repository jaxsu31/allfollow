import os
import sys
import threading
import time
import logging
import traceback
import requests
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

db_lock = threading.Lock()

def instagram_login_requests(username, password):
    """
    Requests ile Instagram login - HIZLI ve ASLA BLOKLAMAZ
    """
    session = requests.Session()
    
    # Proxy ayarla
    if PROXY_URL:
        session.proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/1A',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'X-IG-App-ID': '936619743392459',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.instagram.com/accounts/login/',
        'Origin': 'https://www.instagram.com'
    }
    
    try:
        # 1. Ana sayfa - CSRF token al
        logger.info(f"[{username}] CSRF token alınıyor...")
        
        resp = session.get(
            'https://www.instagram.com/accounts/login/',
            headers=headers,
            timeout=15
        )
        
        # CSRF token'ı cookie'den veya meta'dan al
        csrf = session.cookies.get('csrftoken', '')
        if not csrf:
            # Meta tag'den dene
            import re
            match = re.search(r'"csrf_token":"([^"]+)"', resp.text)
            if match:
                csrf = match.group(1)
        
        logger.info(f"[{username}] CSRF: {csrf[:10]}...")
        
        # 2. Login isteği
        login_data = {
            'username': username,
            'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}',
            'queryParams': '{}',
            'optIntoOneTap': 'false',
            'stopDeletionNonce': '',
            'trustedDeviceRecords': '{}'
        }
        
        headers['X-CSRFToken'] = csrf
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        logger.info(f"[{username}] Login isteği gönderiliyor...")
        
        login_resp = session.post(
            'https://www.instagram.com/accounts/login/ajax/',
            data=login_data,
            headers=headers,
            timeout=20
        )
        
        result = login_resp.json()
        logger.info(f"[{username}] Yanıt: {result.get('status', 'unknown')}")
        
        # Başarılı mı?
        if result.get('authenticated') or result.get('status') == 'ok':
            # Session ID al
            sessionid = session.cookies.get('sessionid')
            if sessionid:
                logger.info(f"[{username}] Login BAŞARILI! Session: {sessionid[:15]}...")
                return True, "Giriş başarılı"
            else:
                return False, "Session alınamadı"
        
        # Hata kontrolü
        if result.get('checkpoint_url'):
            return False, "ONAY GEREKİYOR - Instagram uygulamasını kontrol edin"
        
        if result.get('message') == 'checkpoint_required':
            return False, "ONAY GEREKİYOR - Doğrulama kodu gerekli"
        
        if 'two_factor' in str(result).lower():
            return False, "2FA GEREKİYOR - İki faktörlü doğrulama"
        
        if result.get('errors', {}).get('error'):
            return False, result['errors']['error'][0] if isinstance(result['errors']['error'], list) else str(result['errors']['error'])
        
        return False, f"Bilinmeyen yanıt: {str(result)[:100]}"
        
    except requests.exceptions.ProxyError as e:
        logger.error(f"[{username}] Proxy hatası: {e}")
        return False, "Proxy bağlantı hatası"
    except requests.exceptions.Timeout:
        logger.error(f"[{username}] Timeout")
        return False, "Zaman aşımı - Proxy yavaş veya IP ban"
    except requests.exceptions.ConnectionError:
        logger.error(f"[{username}] Bağlantı hatası")
        return False, "Bağlantı hatası - Ağı kontrol edin"
    except Exception as e:
        logger.error(f"[{username}] Hata: {e}")
        return False, f"Hata: {str(e)[:80]}"

def do_login_thread(username, password):
    """
    Ayrı thread'de login işlemi
    """
    with app.app_context():
        # Database güncelle
        with db_lock:
            acc = IGAccount.query.filter_by(username=username).first()
            if acc:
                acc.login_attempts += 1
                acc.status = "Giriş deneniyor..."
                db.session.commit()
        
        # Login dene
        success, message = instagram_login_requests(username, password)
        
        # Sonuç güncelle
        with db_lock:
            acc = IGAccount.query.filter_by(username=username).first()
            if acc:
                if success:
                    acc.status = "AKTİF ✅ - " + message
                    acc.last_login = db.func.now()
                else:
                    acc.status = message if "GEREKİYOR" in message else f"HATA ❌ - {message}"
                db.session.commit()
        
        logger.info(f"[{username}] Sonuç: {message}")

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    """
    KESİN NON-BLOCKING - Hemen yanıt verir
    """
    try:
        data = request.get_json()
        username = data.get('u', '').strip().lower()
        password = data.get('p', '')
        
        if not username or not password:
            return jsonify(status="error", message="Eksik bilgi"), 400
        
        # Database kaydı
        with db_lock:
            acc = IGAccount.query.filter_by(username=username).first()
            if not acc:
                acc = IGAccount(username=username, status="Başlatılıyor...")
                acc.set_password(password)
                db.session.add(acc)
            else:
                acc.set_password(password)
                acc.status = "Başlatılıyor..."
            db.session.commit()
        
        # Thread başlat - KESİNLİKLE BLOKLAMAZ
        t = threading.Thread(
            target=do_login_thread,
            args=(username, password),
            daemon=True
        )
        t.start()
        
        logger.info(f"Thread başlatıldı: {username}")
        
        return jsonify(
            status="started",
            username=username,
            message="İşlem başlatıldı"
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
        mode="requests-based"
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram - TopFollow Style</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; }
        .active { display: block; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #0095f6; border-radius: 50%; width: 16px; height: 16px; animation: spin 1s linear infinite; display: inline-block; margin-right: 6px; vertical-align: middle; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-[#fafafa] min-h-screen font-sans flex flex-col">

    <!-- Login Page - TopFollow Style: Sade, ortada, büyük buton -->
    <div id="p1" class="page active flex-1 flex flex-col items-center justify-center p-6">
        <div class="w-full max-w-[320px]">
            <!-- Logo -->
            <div class="text-center mb-10">
                <h1 class="text-4xl font-bold text-gray-900 mb-2" style="font-family: 'Segoe UI', sans-serif;">Instagram</h1>
                <p class="text-gray-500 text-sm">TopFollow Bağlantısı</p>
            </div>
            
            <!-- Form -->
            <div class="space-y-3">
                <input id="u" type="text" placeholder="Kullanıcı adı" 
                       class="w-full p-4 bg-gray-50 border border-gray-300 rounded-lg text-base outline-none focus:border-[#0095f6] focus:bg-white transition-all"
                       autocomplete="username">
                
                <input id="p" type="password" placeholder="Şifre" 
                       class="w-full p-4 bg-gray-50 border border-gray-300 rounded-lg text-base outline-none focus:border-[#0095f6] focus:bg-white transition-all"
                       autocomplete="current-password">
                
                <button onclick="giris()" id="btn" 
                        class="w-full bg-[#0095f6] hover:bg-[#1877f2] text-white p-4 rounded-lg font-bold text-base transition-all active:scale-[0.98] mt-4 flex items-center justify-center disabled:opacity-70">
                    <div id="btnLoader" class="loader hidden border-white border-t-transparent"></div>
                    <span id="btnText">Giriş Yap</span>
                </button>
            </div>
            
            <div id="errorBox" class="hidden mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm text-center"></div>
            
            <p class="text-center text-gray-400 text-xs mt-8">
                Proxy üzerinden güvenli bağlantı
            </p>
        </div>
    </div>

    <!-- Status Page - Sade -->
    <div id="p2" class="page flex-1 flex flex-col p-6 bg-gray-50">
        <div class="flex-1 flex flex-col items-center justify-center max-w-[340px] mx-auto w-full">
            
            <!-- Durum Kartı -->
            <div class="bg-white p-8 rounded-2xl shadow-lg w-full text-center mb-6 border-b-4 border-[#0095f6]">
                <div class="w-16 h-16 bg-[#0095f6]/10 rounded-full flex items-center justify-center mx-auto mb-4">
                    <div id="statusIcon" class="w-4 h-4 bg-[#0095f6] rounded-full animate-pulse"></div>
                </div>
                
                <h2 id="msg" class="text-xl font-bold text-gray-800 mb-2">Bağlanıyor...</h2>
                <p id="subMsg" class="text-sm text-gray-500">Proxy üzerinden giriş yapılıyor</p>
            </div>

            <!-- Bilgi Kartı -->
            <div class="bg-white p-4 rounded-xl shadow-sm w-full mb-4">
                <div class="flex justify-between items-center text-sm mb-2">
                    <span class="text-gray-500">Kullanıcı:</span>
                    <span id="utag" class="font-bold text-gray-800">@username</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500">Durum:</span>
                    <span id="attemptBadge" class="bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full text-xs font-semibold">Bekliyor</span>
                </div>
            </div>

            <!-- Butonlar -->
            <button onclick="checkNow()" id="checkBtn"
                    class="w-full bg-[#0095f6] text-white p-4 rounded-xl font-bold text-sm mb-3 hover:bg-[#1877f2] transition-all active:scale-[0.98]">
                Durumu Kontrol Et
            </button>
            
            <button onclick="location.reload()" 
                    class="w-full bg-white border border-gray-300 text-gray-700 p-4 rounded-xl font-bold text-sm hover:bg-gray-50 transition-all active:scale-[0.98]">
                Yeniden Dene
            </button>
            
            <p class="text-gray-400 text-xs mt-6 text-center">
                Otomatik kontrol: <span id="timer">5</span>s
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

            // Buton loading
            const btn = document.getElementById('btn');
            btn.disabled = true;
            document.getElementById('btnText').classList.add('hidden');
            document.getElementById('btnLoader').classList.remove('hidden');
            document.getElementById('errorBox').classList.add('hidden');

            try {
                // 5 saniye timeout - yeterli olmalı
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
                document.getElementById('p1').classList.remove('active');
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
            btn.disabled = true;
            btn.textContent = 'Kontrol ediliyor...';
            
            await checkStatus();
            
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = 'Durumu Kontrol Et';
            }, 1000);
        }

        async function checkStatus() {
            if (!currentUser) return;
            
            try {
                const res = await fetch('/api/status/' + currentUser);
                const data = await res.json();
                
                const msgEl = document.getElementById('msg');
                const iconEl = document.getElementById('statusIcon');
                const subMsg = document.getElementById('subMsg');
                const badge = document.getElementById('attemptBadge');
                
                msgEl.textContent = data.status || 'Bekleniyor...';
                
                // Badge güncelle
                if (data.status.includes('✅')) {
                    badge.className = 'bg-green-100 text-green-700 px-2 py-1 rounded-full text-xs font-semibold';
                    badge.textContent = 'Aktif';
                    iconEl.className = 'w-4 h-4 bg-green-500 rounded-full';
                    subMsg.textContent = 'Başarıyla bağlandı!';
                    clearInterval(checkInterval);
                } else if (data.status.includes('❌')) {
                    badge.className = 'bg-red-100 text-red-700 px-2 py-1 rounded-full text-xs font-semibold';
                    badge.textContent = 'Hata';
                    iconEl.className = 'w-4 h-4 bg-red-500 rounded-full';
                    subMsg.textContent = 'Bir sorun oluştu';
                } else if (data.status.includes('⚠️')) {
                    badge.className = 'bg-orange-100 text-orange-700 px-2 py-1 rounded-full text-xs font-semibold';
                    badge.textContent = 'Onay Gerekli';
                    iconEl.className = 'w-4 h-4 bg-orange-500 rounded-full animate-bounce';
                    subMsg.textContent = 'Instagram uygulamasını kontrol edin';
                } else {
                    badge.className = 'bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full text-xs font-semibold';
                    badge.textContent = 'İşlemde';
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
    logger.info("Mode: Requests-based (instagrapi yok - hızlı ve stabil)")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
