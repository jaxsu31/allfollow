@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    u, p = data.get('u'), data.get('p')
    cl = Client()
    
    # 1. IP ve Cihaz Sabitleme (TopFollow Mantığı)
    existing_user = User.query.filter_by(username=u).first()
    if existing_user and existing_user.device_data:
        cl.set_settings(json.loads(existing_user.device_data))
    else:
        # Yeni hesaplar için TR lokasyonlu cihaz kimliği oluştur
        cl.set_device({"app_version": "269.0.0.18.75", "android_version": 26, "device": "Samsung Galaxy S9"})
        cl.set_locale("tr_TR")
        cl.set_country("TR")

    # 2. Rastgele Proxy Seçimi (Listedeki 50 IP'den biri)
    if PROXY_LIST:
        cl.set_proxy(random.choice(PROXY_LIST))

    try:
        # Giriş denemesi
        cl.login(u, p)
        login_ok = True
    except Exception as e:
        err_msg = str(e).lower()
        print(f"DEBUG: Giriş Hatası -> {err_msg}") # Render loglarında hatayı gör

        # Instagram "Bu siz misiniz?" diye soruyorsa (Challenge)
        if "checkpoint" in err_msg or "challenge" in err_msg:
            # Eğer uygulama içi onay gerekiyorsa (kod gelmiyorsa)
            if "choice" in err_msg or "select_verify_method" in err_msg:
                return jsonify(status="error", msg="Instagram uygulamasını aç ve 'Bendim' butonuna bas, sonra tekrar giriş yap!")
            
            # SMS/Email kodu gerekiyorsa
            return jsonify(status="challenge", msg="Doğrulama kodu gerekli! Lütfen bekleyin.")
        
        # Giriş başarılı ama küçük bir hata fırlatmışsa (user_id varsa sorun yoktur)
        login_ok = True if getattr(cl, 'user_id', None) else False

    if login_ok:
        # Giriş başarılıysa cihazı kaydet (Bir daha konum hatası vermemesi için)
        if not existing_user:
            existing_user = User(
                username=u, 
                password=p, 
                ref_code=str(uuid.uuid4())[:6].upper(),
                device_data=json.dumps(cl.get_settings()) # Cihazı buraya kitliyoruz
            )
            db.session.add(existing_user)
        
        session['user'] = u
        db.session.commit()
        return jsonify(status="success")
    
    return jsonify(status="error", msg="Instagram erişimi reddetti. Lütfen şifrenizi veya hesabınızı kontrol edin.")
