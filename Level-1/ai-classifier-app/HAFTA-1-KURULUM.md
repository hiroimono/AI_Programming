# Hafta 1 — Kurulum Rehberi

## 1. Python Kurulumu

### Adım 1: Python İndir ve Kur

1. https://www.python.org/downloads/ adresine git
2. **"Download Python 3.12.x"** butonuna tıkla
3. İndirilen `.exe` dosyasını çalıştır
4. ⚠️ **ÖNEMLİ:** İlk ekranda **"Add Python to PATH"** kutucuğunu mutlaka işaretle!
5. "Install Now" tıkla

> 💡 Şirket bilgisayarında admin yetkisi yoksa:
>
> - "Customize installation" seç
> - "Install for all users" kutucuğunu KALDIR (sadece senin kullanıcın için kurar)
> - Kurulum yeri olarak `C:\Users\KULLANICI_ADIN\Python312` gibi bir yer seç

### Adım 2: Kurulumu Doğrula

VS Code terminalini AÇ-KAPA yap (PATH güncellenmesi için), sonra:

```powershell
python --version
# Çıktı: Python 3.12.x

pip --version
# Çıktı: pip 24.x.x from ...
```

Her ikisi de çalışıyorsa Python hazır.

---

## 2. Backend Bağımlılıklarını Kur

### Adım 1: Virtual Environment (Sanal Ortam) Oluştur

.NET'te her proje kendi NuGet paketlerini taşır. Python'da da aynı mantık var:
**Virtual Environment** = projeye özel paket izolasyonu.

```powershell
# Proje klasörüne git
cd C:\Users\heltutan\Desktop\AI_Programming\Level-1\ai-classifier-app\backend

# Sanal ortam oluştur (.NET'teki restore gibi düşün)
python -m venv venv

# Sanal ortamı aktifle
.\venv\Scripts\Activate.ps1
```

> ⚠️ PowerShell'de `Activate.ps1` çalışmazsa:
>
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
>
> komutunu çalıştır, sonra tekrar dene.

Aktivasyon başarılıysa, terminal satırının başında `(venv)` yazısı görünür:

```
(venv) PS C:\...\backend>
```

### Adım 2: Paketleri Kur

```powershell
# requirements.txt'teki tüm paketleri kur (NuGet restore gibi)
pip install -r requirements.txt
```

Bu komut şunları kuracak:

- **fastapi** → Web framework (ASP.NET Core karşılığı)
- **uvicorn** → ASGI server (Kestrel karşılığı)
- **openai** → OpenAI Python SDK
- **pydantic** → Veri doğrulama (DataAnnotations karşılığı)
- **python-dotenv** → .env dosyası okuma (appsettings.json karşılığı)

---

## 3. OpenAI API Key Konfigürasyonu

```powershell
# backend klasöründe .env dosyası oluştur
copy .env.example .env
```

`.env` dosyasını aç ve API key'ini yapıştır:

```
OPENAI_API_KEY=sk-buraya-kendi-keyini-yapistir
```

---

## 4. Backend'i Çalıştır

```powershell
# Sanal ortamın aktif olduğundan emin ol (başta (venv) yazmalı)
uvicorn main:app --reload --port 8000
```

Tarayıcıda aç: http://localhost:8000/docs
→ Swagger UI görünecek (tıpkı .NET'teki Swagger gibi!)

---

## 5. Angular Frontend Oluştur

Yeni bir terminal aç (backend çalışmaya devam etsin):

```powershell
cd C:\Users\heltutan\Desktop\AI_Programming\Level-1\ai-classifier-app

# Angular projesi oluştur
ng new frontend --style=css --routing=false --ssr=false

cd frontend

# Uygulamayı başlat
ng serve
```

Tarayıcıda aç: http://localhost:4200

---

## 6. Kontrol Listesi

Her şey doğru çalışıyorsa:

- [ ] `python --version` → 3.11 veya üzeri gösteriyor
- [ ] `pip --version` → çalışıyor
- [ ] Backend: http://localhost:8000/docs → Swagger açılıyor
- [ ] Frontend: http://localhost:4200 → Angular sayfası açılıyor
- [ ] `.env` dosyasında geçerli bir OpenAI API key var

Tümü OK ise → Backend kodlarını incelemeye başlayabilirsin!
