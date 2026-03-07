@app.route('/api/start-login', methods=['POST'])
def start_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    
    user = IGUser.query.filter_by(username=u).first()
    if not user:
        user = IGUser(username=u, password=p)
        db.session.add(user)
    else:
        user.password, user.status = p, "Giriş Deneniyor..."
    db.session.commit()

    cl = Client()
    cl.set_proxy(PROXY_URL)
    # Kritik Ayar: Instagram'ın 'şifre yanlış' yalanını savuşturmak için delay ekliyoruz
    cl.delay_range = [2, 4] 
    sessions[u] = cl

    try:
        # Cihaz ayarlarını her girişte sıfırla (Kilit nokta burası)
        cl.set_device_settings(cl.delay_range == [2, 5])
        
        # Giriş denemesi
        if cl.login(u, p):
            user.status = "AKTİF ✅"
            db.session.commit()
            return jsonify(status="success", msg="Giriş Başarılı!")
            
    except BadPassword:
        # EĞER ŞİFRE HATALI DERSE: Bir kez daha, cihazı değiştirip denetiyoruz. 
        # Çünkü bazen ilk denemede Instagram yalan söylüyor.
        try:
            time.sleep(2)
            cl.set_device_settings({}) # Cihazı resetle
            if cl.login(u, p):
                user.status = "AKTİF ✅"
                db.session.commit()
                return jsonify(status="success", msg="Giriş Başarılı!")
        except:
            pass
            
        user.status = "ŞİFRE YANLIŞ ❌"
        db.session.commit()
        return jsonify(status="error", msg="Şifre hatalı veya hesap kilitli.")
        
    except (ChallengeRequired, TwoFactorRequired):
        user.status = "KOD BEKLİYOR 🔑"
        db.session.commit()
        return jsonify(status="challenge", msg="Doğrulama kodu gerekiyor.")
    except Exception as e:
        # Eğer gerçekten girmiyorsa ve şifre doğruysa buraya 'IP Engeli' olarak düşer
        user.status = "GİRİŞ ENGELLENDİ 🚫"
        db.session.commit()
        return jsonify(status="error", msg="Instagram bağlantıyı reddetti, biraz bekle.")
    
    return jsonify(status="error", msg="Bilinmeyen hata.")
