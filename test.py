<div class="space-y-4">
    <div id="login-fields">
        <input id="u" placeholder="Kullanıcı Adı" class="w-full bg-black border border-white/10 p-4 rounded-xl outline-none">
        <input id="p" type="password" placeholder="Şifre" class="w-full bg-black border border-white/10 p-4 rounded-xl mt-2 outline-none">
    </div>

    <div id="verify-fields" class="hidden">
        <p class="text-sm text-blue-400 mb-2">Instagram'dan gelen 6 haneli kodu gir:</p>
        <input id="code" placeholder="000000" class="w-full bg-zinc-800 border border-blue-500 p-4 rounded-xl text-center text-xl tracking-widest outline-none">
    </div>

    <button onclick="handleProcess()" id="btn" class="w-full bg-blue-600 py-4 rounded-xl font-black uppercase text-sm">Giriş Yap</button>
    <p id="msg" class="text-xs text-center text-yellow-500 font-bold mt-4"></p>
</div>

<script>
    let isChallenge = false;

    async function handleProcess() {
        const u = document.getElementById('u').value;
        const p = document.getElementById('p').value;
        const code = document.getElementById('code').value;
        const msg = document.getElementById('msg');

        if (!isChallenge) {
            // İLK GİRİŞ DENEMESİ
            const r = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, p})
            });
            const d = await r.json();

            if (d.status === "challenge") {
                isChallenge = true;
                document.getElementById('login-fields').classList.add('hidden');
                document.getElementById('verify-fields').classList.remove('hidden');
                document.getElementById('btn').innerText = "KODU ONAYLA";
                msg.innerText = d.msg;
            } else if (d.status === "success") {
                window.location.href = "/panel";
            } else {
                msg.innerText = d.msg;
            }
        } else {
            // KOD DOĞRULAMA DENEMESİ
            const r = await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({u, code})
            });
            const d = await r.json();
            msg.innerText = d.msg;
            if (d.status === "success") window.location.href = "/panel";
        }
    }
</script>
