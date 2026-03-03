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
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///enterprise.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)


app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
limiter = Limiter(app=app, key_func=get_remote_address)

celery = Celery(app.import_name, broker=app.config["REDIS_URL"])
celery.conf.update(app.config)

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
    return (
        db.session.query(TokenBlocklist.id)
        .filter_by(jti=jwt_payload["jti"])
        .scalar()
        is not None
    )


# ---------------- FRONTEND ----------------
UI = """
<!DOCTYPE html>
<html>
<head>
<title>TopFollow Enterprise</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white p-6">
<div class="max-w-xl mx-auto">
<div id="login">
<input id="u" placeholder="Username" class="text-black p-2"/>
<input id="p" type="password" placeholder="Password" class="text-black p-2"/>
<button onclick="login()" class="bg-blue-600 p-2">Login</button>
</div>
<div id="dash" class="hidden">
<h2>Coins: <span id="coins"></span></h2>
<button onclick="toggleBot()" id="botbtn" class="bg-green-600 p-2">Toggle Bot</button>
<button onclick="logout()" class="bg-red-600 p-2">Logout</button>
</div>
</div>
<script>
async function login(){
let res=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:u.value,p:p.value})})
let data=await res.json()
if(data.token){localStorage.token=data.token;loadDash()}
}
async function loadDash(){
let res=await fetch('/api/status',{headers:{Authorization:'Bearer '+localStorage.token}})
let data=await res.json()
login.classList.add('hidden')
dash.classList.remove('hidden')
coins.innerText=data.coins
botbtn.innerText=data.active?'Stop Bot':'Start Bot'
}
async function toggleBot(){
let res=await fetch('/api/toggle',{method:'POST',headers:{Authorization:'Bearer '+localStorage.token}})
let data=await res.json()
botbtn.innerText=data.active?'Stop Bot':'Start Bot'
}
async function logout(){
await fetch('/api/logout',{method:'DELETE',headers:{Authorization:'Bearer '+localStorage.token}})
localStorage.clear()
location.reload()
}
</script>
</body>
</html>
"""

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template_string(UI)


@app.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute")
def login_api():
    data = request.json
    user = User.query.filter_by(username=data.get("u")).first()
    if user and bcrypt.check_password_hash(user.password_hash, data.get("p")):
        token = create_access_token(identity=user.id)
        return jsonify(token=token)
    return jsonify(msg="Hatalı"), 401


@app.route("/api/logout", methods=["DELETE"])
@jwt_required()
def logout_api():
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()
    return jsonify(msg="Çıkış yapıldı")


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
    if user.is_active:
        background_bot_task.delay(user.id)
    return jsonify(active=user.is_active)


@app.route("/health")
def health():
    return jsonify(status="ok")


# ---------------- START ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            pw = bcrypt.generate_password_hash("admin123").decode("utf-8")
            db.session.add(User(username="admin", password_hash=pw, is_admin=True))
            db.session.commit()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
