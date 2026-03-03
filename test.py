import os
import random
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIG ----------------
# ---------------- CONFIG ----------------
class Config:
    # Render Dashboard -> Environment kısmına SECRET_KEY eklediysen onu alır, yoksa varsayılanı kullanır
    SECRET_KEY = os.getenv("SECRET_KEY", "cok-gizli-anahtar-123")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-ozel-anahtar-456")
    
    # Burası kritik: Eğer Environment'ta DATABASE_URL yoksa hata vermemesi için sqlite'a döner
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///fallback.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    
app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
limiter = Limiter(app=app, key_func=get_remote_address)

# Celery konfigürasyonu (Eğer Redis yoksa hata vermemesi için try-except)
try:
    celery = Celery(app.import_name, broker=app.config["REDIS_URL"])
    celery.conf.update(app.config)
except:
    celery = None

# ---------------- MODELS ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    coins = db.Column(db.Integer, default=1000)
    is_active = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TokenBlocklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------- CELERY TASK ----------------
if celery:
    @celery.task(bind=True, max_retries=3)
    def background_bot_task(self, user_id):
        with app.app_context():
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return "Bot Pasif"
            try:
                time.sleep(random.randint(3, 6))
                user.coins += 25
                db.session.commit()
                return "Coin eklendi"
            except Exception as exc:
                raise self.retry(exc=exc, countdown=60)

# ---------------- JWT BLOCKLIST ----------------
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return db.session.query(TokenBlocklist.id).filter_by(jti=jwt_payload["jti"]).scalar() is not None

# ---------------- FRONTEND (FIXED) ----------------
UI = """
<!DOCTYPE html>
<html>
<head>
    <title>TopFollow Pro v71</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white p-6 font-sans">
    <div class="max-w-md mx-auto bg-slate-800 p-8 rounded-xl shadow-2xl mt-10">
        <h1 class="text-2xl font-bold mb-6 text-center text-blue-400">TopFollow Enterprise</h1>
        
        <div id="loginSection">
            <div class="space-y-4">
                <input id="u" placeholder="Kullanıcı Adı" class="w-full text-black p-3 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"/>
                <input id="p" type="password" placeholder="Şifre" class="w-full text-black p-3 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"/>
                <button onclick="handleLogin()" class="w-full bg-blue-600 hover:bg-blue-700 p-3 rounded-lg font-bold transition">Giriş Yap</button>
                <p id="errMsg" class="text-red-500 text-sm text-center hidden">Hatalı kullanıcı adı veya şifre!</p>
            </div>
        </div>

        <div id="dashSection" class="hidden text-center">
            <div class="bg-slate-700 p-4 rounded-lg mb-6">
                <p class="text-gray-400">Mevcut Bakiyeniz</p>
                <h2 class="text-4xl font-black text-yellow-400"><span id="coinDisplay">0</span> 🪙</h2>
            </div>
            <div class="flex flex-col space-y-3">
                <button onclick="toggleBot()" id="botBtn" class="bg-green-600 hover:bg-green-700 p-3 rounded-lg font-bold transition">Botu Başlat</button>
                <button onclick="handleLogout()" class="bg-red-600/20 hover:bg-red-600 text-red-500 hover:text-white p-3 rounded-lg font-bold transition border border-red-600/50">Çıkış Yap</button>
            </div>
        </div>
    </div>

    <script>
    const loginSection = document.getElementById('loginSection');
    const dashSection = document.getElementById('dashSection');
    const coinDisplay = document.getElementById('coinDisplay');
    const botBtn = document.getElementById('botBtn');
    const errMsg = document.getElementById('errMsg');

    async function handleLogin(){
        const u = document.getElementById('u').value;
        const p = document.getElementById('p').value;
        
        try {
            let res = await fetch(window.location.origin + '/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            let data = await res.json();
            
            if(data.token){
                localStorage.token = data.token;
                loadDash();
            } else {
                errMsg.classList.remove('hidden');
            }
        } catch(e) {
            alert("Sunucuya bağlanılamadı!");
        }
    }

    async function loadDash(){
        if(!localStorage.token) return;
        
        let res = await fetch('/api/status', {
            headers: {Authorization: 'Bearer ' + localStorage.token}
        });
        
        if(res.status === 401) return handleLogout();
        
        let data = await res.json();
        loginSection.classList.add('hidden');
        dashSection.classList.remove('hidden');
        coinDisplay.innerText = data.coins;
        botBtn.innerText = data.active ? 'Botu Durdur' : 'Botu Başlat';
        botBtn.className = data.active ? 'bg-orange-600 p-3 rounded-lg font-bold' : 'bg-green-600 p-3 rounded-lg font-bold';
    }

    async function toggleBot(){
        let res = await fetch('/api/toggle', {
            method: 'POST',
            headers: {Authorization: 'Bearer ' + localStorage.token}
        });
        let data = await res.json();
        loadDash();
    }

    function handleLogout(){
        localStorage.clear();
        location.reload();
    }

    // Sayfa açıldığında token varsa dash'i yükle
    if(localStorage.token) loadDash();
    </script>
</body>
</html>
"""

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template_string(UI)

@app.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def login_api():
    data = request.json
    user = User.query.filter_by(username=data.get("u")).first()
    if user and bcrypt.check_password_hash(user.password_hash, data.get("p")):
        token = create_access_token(identity=str(user.id))
        return jsonify(token=token)
    return jsonify(msg="Hatalı"), 401

@app.route("/api/status")
@jwt_required()
def status():
    user = User.query.get(get_jwt_identity())
    return jsonify(coins=user.coins, active=user.is_active)

@app.route("/api/toggle", methods=["POST"])
@jwt_required()
def toggle():
    user = User.query.get(get_jwt_identity())
    user.is_active = not user.is_active
    db.session.commit()
    # Celery varsa görevi başlat
    if celery and user.is_active:
        background_bot_task.delay(user.id)
    return jsonify(active=user.is_active)

@app.route("/health")
def health():
    return jsonify(status="ok")

# ---------------- START ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Admin hesabı yoksa oluştur
        if not User.query.filter_by(username="admin").first():
            pw = bcrypt.generate_password_hash("admin123").decode("utf-8")
            db.session.add(User(username="admin", password_hash=pw, is_admin=True))
            db.session.commit()
            print("✅ Admin hesabı hazır: admin / admin123")
    
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
