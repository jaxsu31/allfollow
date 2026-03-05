import os
import sys
import threading
import time
import logging
import traceback
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# DETAYLI LOGGING
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# instagrapi import ve versiyon kontrolü
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
    import instagrapi
    logger.info(f"instagrapi versiyonu: {instagrapi.__version__}")
except ImportError as e:
    logger.error(f"instagrapi import hatası: {e}")
    logger.error("Kurulum: pip install instagrapi==2.0.0")
    raise

load_dotenv()

app = Flask(__name__)

# DATABASE - SQLite varsayılan (basit olsun)
db_path = os.path.abspath("ig_accounts.db")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "anti-delay-v72")
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

logger.info(f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}")

try:
    db = SQLAlchemy(app)
    logger.info("SQLAlchemy başarıyla başlatıldı")
except Exception as e:
    logger.error(f"SQLAlchemy hatası: {e}")
    raise

# Rate limiter
try:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["10 per minute"]
    )
    logger.info("Rate limiter aktif")
except Exception as e:
    logger.error(f"Rate limiter hatası: {e}")
    limiter = None

# PROXY - Boşlukları temizle
PROXY_URL = os.getenv("PROXY_URL", "").strip()
if PROXY_URL:
    logger.info(f"Proxy aktif: {PROXY_URL[:20]}...")
else:
    logger.info("Proxy kullanılmıyor")

class IGAccount(db.Model):
    __tablename__ = 'ig_accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(200), default="Beklemede")
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())
    login_attempts = db.Column(db.Integer, default=0)
    error_log = db.Column(db.Text)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

db_lock = threading.Lock()

def test_proxy():
    """Proxy çalışıyor mu test et"""
    if not PROXY_URL:
        return True
    
    try:
        import requests
        proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
        response = requests.get(
            'http://httpbin.org/ip', 
            proxies=proxies, 
            timeout=10
        )
        logger.info(f"Proxy test başarılı: {response.json()}")
        return True
    except Exception as e:
        logger.error(f"Proxy test başarısız: {e}")
        return False

def create_client():
    """Instagrapi client oluştur - HATA YAKALAMA ile"""
    try:
        cl = Client()
        
        # Proxy ayarla
        if PROXY_URL:
            try:
                cl.set_proxy(PROXY_URL)
                logger.debug("Proxy ayarlandı")
            except Exception as e:
                logger.error(f"Proxy ayarlama hatası: {e}")
                # Proxy'siz devam et
        
        # Timeout ayarları
        cl.request_timeout = 30
        
        # Delay ayarları (bot koruması için)
        cl.delay_range = [2, 5]
        
        logger.debug("Client oluşturuldu")
        return cl
        
    except Exception as e:
        logger.error(f"Client oluşturma hatası: {e}")
        logger.error(traceback.format_exc())
        raise

def background_bot(username, password):
    """Arka plan botu - DETAYLI LOG"""
    logger.info(f"Background bot başladı: {username}")
    
    with app.app_context():
        cl = None
        
        try:
            # Database kaydı bul/güncelle
            with db_lock:
                try:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if not acc:
                        logger.error(f"Hesap bulunamadı: {username}")
                        return
                    
                    acc.login_attempts += 1
                    acc.status = "Giriş yapılıyor..."
                    db.session.commit()
                    logger.debug(f"Hesap durumu güncellendi: {username}")
                except Exception as db_err:
                    logger.error(f"Database hatası: {db_err}")
                    return

            # Client oluştur
            try:
                cl = create_client()
            except Exception as client_err:
                logger.error(f"Client oluşturulamadı: {client_err}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "HATA: Client oluşturulamadı"
                    acc.error_log = str(client_err)
                    db.session.commit()
                return

            # LOGIN DENE
            logger.info(f"Instagram login deneniyor: {username}")
            
            try:
                cl.login(username, password)
                logger.info(f"Login başarılı: {username}")
                
            except ChallengeRequired as e:
                logger.warning(f"Challenge required: {username} - {e}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "ONAY GEREKİYOR ⚠️ - Instagram uygulamasını kontrol edin"
                    db.session.commit()
                return
                
            except TwoFactorRequired as e:
                logger.warning(f"2FA gerekli: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "2FA GEREKİYOR ⚠️ - İki faktörlü doğrulama kodu girin"
                    db.session.commit()
                return
                
            except BadPassword as e:
                logger.warning(f"Yanlış şifre: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "HATA ❌ - Yanlış şifre"
                    db.session.commit()
                return
                
            except PleaseWaitFewMinutes as e:
                logger.warning(f"Rate limit: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "BEKLEME ⏳ - Çok fazla deneme, 10dk sonra tekrar dene"
                    db.session.commit()
                return
                
            except LoginRequired as e:
                logger.error(f"LoginRequired hatası: {username} - {e}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "HATA ❌ - Cookie/session hatası"
                    db.session.commit()
                return
                
            except RateLimitError as e:
                logger.warning(f"Rate limit (yeni): {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "BEKLEME ⏳ - IP limiti, proxy değiştirin"
                    db.session.commit()
                return
                
            except UnknownError as e:
                logger.error(f"Unknown error: {username} - {e}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = f"HATA ❌ - Bilinmeyen hata: {str(e)[:50]}"
                    acc.error_log = str(e)
                    db.session.commit()
                return
                
            except Exception as login_err:
                logger.error(f"Login hatası: {username} - {type(login_err).__name__}: {login_err}")
                logger.error(traceback.format_exc())
                
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    error_msg = str(login_err)
                    
                    if "checkpoint" in error_msg.lower():
                        acc.status = "ONAY GEREKİYOR ⚠️ - Güvenlik kontrolü"
                    elif "password" in error_msg.lower():
                        acc.status = "HATA ❌ - Şifre hatalı"
                    elif "network" in error_msg.lower():
                        acc.status = "HATA ❌ - Ağ/Proxy hatası"
                    elif "verification" in error_msg.lower():
                        acc.status = "ONAY GEREKİYOR ⚠️ - Doğrulama kodu"
                    else:
                        acc.status = f"HATA ❌ - {error_msg[:80]}"
                    
                    acc.error_log = f"{type(login_err).__name__}: {error_msg}"
                    db.session.commit()
                return

            # Başarılı login sonrası
            with db_lock:
                try:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "AKTİF ✅ - Giriş başarılı"
                    acc.last_login = db.func.now()
                    db.session.commit()
                    logger.info(f"Durum güncellendi (aktif): {username}")
                except Exception as db_err:
                    logger.error(f"Database güncelleme hatası: {db_err}")

            # Instagram'ı takip et
            try:
                logger.info(f"Instagram takip ediliyor: {username}")
                instagram_user_id = cl.user_id_from_username("instagram")
                cl.user_follow(instagram_user_id)
                
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "AKTİF ✅ - Takip tamamlandı"
                    db.session.commit()
                logger.info(f"Takip başarılı: {username}")
                
            except Exception as follow_err:
                logger.warning(f"Takip hatası: {username} - {follow_err}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "AKTİF ✅ (Takip edilemedi)"
                    db.session.commit()

        except Exception as e:
            logger.error(f"Beklenmeyen genel hata ({username}): {e}")
            logger.error(traceback.format_exc())
            
            try:
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    if acc:
                        acc.status = "KRİTİK HATA ❌"
                        acc.error_log = f"{type(e).__name__}: {str(e)}"
                        db.session.commit()
            except:
                pass
                
        finally:
            if cl:
                try:
                    cl.logout()
                    logger.debug(f"Logout yapıldı: {username}")
                except:
                    pass

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
    logger.info(f"Connect isteği geldi: {request.remote_addr}")
    
    try:
        data = request.get_json()
        logger.debug(f"Gelen veri: {data}")
        
        if not data:
            logger.error("JSON verisi boş")
            return jsonify(status="error", message="Veri gönderilmedi"), 400
        
        username = data.get('u', '').strip().lower()
        password = data.get('p', '')
        
        logger.info(f"Login denemesi: {username}")
        
        if not username or not password:
            logger.warning("Boş kullanıcı adı veya şifre")
            return jsonify(status="error", message="Kullanıcı adı ve şifre gerekli"), 400
        
        # Database işlemi
        try:
            with db_lock:
                acc = IGAccount.query.filter_by(username=username).first()
                
                if not acc:
                    acc = IGAccount(username=username, status="Yeni Kayıt")
                    acc.set_password(password)
                    db.session.add(acc)
                    logger.info(f"Yeni hesap oluşturuldu: {username}")
                else:
                    acc.set_password(password)
                    acc.status = "Bağlanıyor..."
                    logger.info(f"Mevcut hesap güncellendi: {username}")
                
                db.session.commit()
                
        except Exception as db_err:
            logger.error(f"Database hatası: {db_err}")
            logger.error(traceback.format_exc())
            return jsonify(status="error", message="Database hatası"), 500
        
        # Background thread başlat
        try:
            thread = threading.Thread(
                target=background_bot,
                args=(username, password),
                daemon=True
            )
            thread.start()
            logger.info(f"Background thread başlatıldı: {username}")
            
        except Exception as thread_err:
            logger.error(f"Thread başlatma hatası: {thread_err}")
            return jsonify(status="error", message="İşlem başlatılamadı"), 500
        
        return jsonify(status="started", username=username)
        
    except Exception as e:
        logger.error(f"Connect endpoint hatası: {e}")
        logger.error(traceback.format_exc())
        return jsonify(status="error", message=f"Sunucu hatası: {str(e)}"), 500

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
            last_login=acc.last_login.isoformat() if acc.last_login else None,
            error=acc.error_log[:200] if acc.error_log else None
        )
    except Exception as e:
        logger.error(f"Status endpoint hatası: {e}")
        return jsonify(status="Hata", error=str(e)), 500

@app.route('/api/debug')
def debug_info():
    """Debug bilgileri"""
    try:
        import instagrapi
        return jsonify({
            "instagrapi_version": instagrapi.__version__,
            "database": app.config['SQLALCHEMY_DATABASE_URI'],
            "proxy": bool(PROXY_URL),
            "proxy_working": test_proxy() if PROXY_URL else None
        })
    except Exception as e:
        return jsonify(error=str(e))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; opacity: 0; transition: all 0.3s ease; }
        .active { display: block; opacity: 1; }
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-10px); }
            75% { transform: translateX(10px); }
        }
        .shake { animation: shake 0.5s ease-in-out; }
        .loader {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #0095f6;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-[#fafafa] min-h-screen font-sans">

    <!-- Login Page -->
    <div id="p1" class="page active flex flex-col items-center justify-center min-h-screen p-4">
        <div class="bg-white border border-gray-300 p-8 w-full max-w-[350px] flex flex-col items-center shadow-sm">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" 
                 class="w-44 mb-8" alt="Instagram">
            
            <div id="errorBox" class="hidden w-full mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-xs text-center"></div>
            
            <input id="u" type="text" placeholder="Kullanıcı adı" 
                   class="w-full p-2.5 mb-2 bg-gray-50 border border-gray-300 rounded text-xs outline-none focus:border-gray-400">
            
            <input id="p" type="password" placeholder="Şifre" 
                   class="w-full p-2.5 mb-4 bg-gray-50 border border-gray-300 rounded text-xs outline-none focus:border-gray-400">
            
            <button onclick="giris()" id="btn" 
                    class="w-full bg-[#0095f6] text-white py-2 rounded font-semibold text-sm opacity-100 hover:opacity-90 transition-opacity flex items-center justify-center gap-2">
                <span id="btnText">Giriş Yap</span>
                <div id="btnLoader" class="loader hidden border-white border-t-transparent"></div>
            </button>
        </div>
    </div>

    <!-- Status Page -->
    <div id="p2" class="page min-h-screen bg-gray-50 p-6">
        <div class="max-w-md mx-auto">
            <h1 class="text-center font-black text-purple-600 mb-6 text-2xl italic">ALLFOLLOW</h1>
            
            <div class="bg-white p-6 rounded-3xl shadow-lg border-b-4 border-purple-500 text-center mb-4">
                <p class="text-xs text-gray-400 font-bold uppercase mb-2">Durum</p>
                <div class="flex items-center justify-center gap-2">
                    <div id="statusIcon" class="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                    <h2 id="msg" class="text-lg font-bold text-purple-600">BAĞLANILIYOR...</h2>
                </div>
                <p id="errorDetail" class="text-[10px] text-red-500 mt-2 hidden"></p>
            </div>

            <div class="bg-white p-4 rounded-2xl border flex items-center justify-between shadow-sm mb-4">
                <div>
                    <p class="text-[10px] text-gray-400 font-bold uppercase">Kullanıcı</p>
                    <p id="utag" class="font-bold text-gray-800"></p>
                </div>
                <div class="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center text-purple-600 font-bold text-sm">IG</div>
            </div>

            <div class="bg-white p-3 rounded-xl border text-xs space-y-2">
                <div class="flex justify-between">
                    <span class="text-gray-500">Deneme:</span>
                    <span id="attempts" class="font-semibold">0</span>
                </div>
                <div class="flex justify-between">
                    <span class="text-gray-500">Son kontrol:</span>
                    <span id="lastCheck" class="font-semibold">-</span>
                </div>
            </div>

            <button onclick="location.reload()" class="w-full mt-4 bg-gray-200 text-gray-700 py-3 rounded-xl font-semibold text-sm hover:bg-gray-300 transition-colors">
                Yeniden Dene
            </button>
            
            <button onclick="testDebug()" class="w-full mt-2 bg-blue-100 text-blue-600 py-2 rounded-xl font-semibold text-xs hover:bg-blue-200 transition-colors">
                Debug Bilgisi
            </button>
        </div>
    </div>

    <script>
        let currentUser = "";
        let checkInterval;

        function showError(msg) {
            const box = document.getElementById('errorBox');
            box.textContent = msg;
            box.classList.remove('hidden');
            document.getElementById('p1').classList.add('shake');
            setTimeout(() => document.getElementById('p1').classList.remove('shake'), 500);
        }

        async function giris() {
            const u = document.getElementById('u').value.trim().toLowerCase();
            const p = document.getElementById('p').value;
            
            if (!u || !p) {
                showError('Kullanıcı adı ve şifre girin');
                return;
            }

            document.getElementById('btn').disabled = true;
            document.getElementById('btnText').classList.add('hidden');
            document.getElementById('btnLoader').classList.remove('hidden');

            try {
                console.log('Gönderilen:', {u: u, p: '***'});
                
                const res = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u: u, p: p})
                });

                const data = await res.json();
                console.log('Yanıt:', data);

                if (data.status === 'error') {
                    throw new Error(data.message);
                }

                currentUser = u;
                document.getElementById('p1').classList.remove('active');
                setTimeout(() => {
                    document.getElementById('p2').classList.add('active');
                    document.getElementById('utag').textContent = '@' + u;
                    startChecking();
                }, 300);

            } catch (err) {
                console.error('Hata:', err);
                showError('Sunucu hatası: ' + err.message);
                document.getElementById('btn').disabled = false;
                document.getElementById('btnText').classList.remove('hidden');
                document.getElementById('btnLoader').classList.add('hidden');
            }
        }

        function startChecking() {
            checkStatus();
            checkInterval = setInterval(checkStatus, 5000);
        }

        async function checkStatus() {
            if (!currentUser) return;
            
            try {
                const res = await fetch('/api/status/' + currentUser);
                const data = await res.json();
                console.log('Status:', data);

                document.getElementById('msg').textContent = data.status || 'Bekleniyor...';
                document.getElementById('attempts').textContent = data.attempts || 0;
                document.getElementById('lastCheck').textContent = new Date().toLocaleTimeString('tr-TR');

                if (data.error) {
                    document.getElementById('errorDetail').textContent = data.error;
                    document.getElementById('errorDetail').classList.remove('hidden');
                }

                // Renkler
                const msg = document.getElementById('msg');
                const icon = document.getElementById('statusIcon');
                
                if (data.status.includes('✅')) {
                    msg.className = 'text-lg font-bold text-green-500';
                    icon.className = 'w-2 h-2 bg-green-500 rounded-full';
                    clearInterval(checkInterval);
                } else if (data.status.includes('❌')) {
                    msg.className = 'text-lg font-bold text-red-500';
                    icon.className = 'w-2 h-2 bg-red-500 rounded-full';
                } else if (data.status.includes('⚠️')) {
                    msg.className = 'text-lg font-bold text-orange-500';
                    icon.className = 'w-2 h-2 bg-orange-500 rounded-full animate-bounce';
                }

            } catch (e) {
                console.error('Check error:', e);
            }
        }

        async function testDebug() {
            try {
                const res = await fetch('/api/debug');
                const data = await res.json();
                alert(JSON.stringify(data, null, 2));
            } catch (e) {
                alert('Debug hatası: ' + e);
            }
        }

        document.getElementById('p').addEventListener('keypress', e => {
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
            logger.info("Database tabloları oluşturuldu")
        except Exception as e:
            logger.error(f"Database oluşturma hatası: {e}")
            raise
    
    # Proxy test
    if PROXY_URL:
        test_proxy()
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Sunucu başlatılıyor: 0.0.0.0:{port}")
    
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
