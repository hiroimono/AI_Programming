# Hafta 1: Python & FastAPI Temelleri + İlk AI Çağrısı

## 🎯 Bu Hafta Ne Yapacağız?

**Uygulama:** Akıllı Müşteri Geri Bildirim Sınıflandırıcı

Bir metin kutusu. Müşteri geri bildirimi yazıyorsun. "Analiz Et" butonuna basıyorsun.
AI otomatik olarak:

- **Kategori** belirliyor (Şikayet, Öneri, Soru, Övgü)
- **Duygu analizi** yapıyor (Pozitif, Negatif, Nötr)
- **Güven skoru** veriyor (%0-100)
- **Özet** çıkarıyor
- **Aksiyon önerileri** sunuyor

Bu, bir müşteri hizmetleri ekibinin günde yüzlerce geri bildirimi elle okumak yerine
otomatik sınıflandırmasını sağlayan gerçek bir iş problemi.

---

## 📐 Mimari (Bu Hafta)

```
┌─────────────────┐     HTTP POST      ┌─────────────────┐     API Call     ┌──────────┐
│   Angular App   │ ──────────────────► │   FastAPI       │ ───────────────► │  OpenAI  │
│   (localhost:    │ ◄────────────────── │   Backend       │ ◄─────────────── │  GPT-4o  │
│    4200)         │     JSON Response   │   (localhost:   │    JSON Response │  mini    │
│                  │                     │    8000)        │                  │          │
└─────────────────┘                     └─────────────────┘                  └──────────┘
```

Çok basit: Angular → FastAPI → OpenAI → geri dön. Hepsi bu.

---

## 🔧 Günlük Plan

### Gün 1-2: Python Kurulumu + Temelleri (~2 saat)

**Python .NET/C#'tan ne kadar farklı?**

Kısa cevap: Çok az. Sadece syntax farkları var. Mantık aynı.

| C# / .NET                      | Python                         |
| ------------------------------ | ------------------------------ |
| `string name = "Ali";`         | `name = "Ali"`                 |
| `int age = 30;`                | `age = 30`                     |
| `List<string> items = new();`  | `items = []`                   |
| `Dictionary<string, int>`      | `dict` → `{"key": value}`      |
| `public class User { ... }`    | `class User: ...`              |
| `async Task<string> GetData()` | `async def get_data() -> str:` |
| `namespace MyApp { ... }`      | Dosya = modül (namespace yok)  |
| `using System.Net.Http;`       | `import httpx`                 |
| NuGet packages                 | pip packages                   |
| `appsettings.json`             | `.env` dosyası                 |
| `[ApiController]` attribute    | `@app.post("/path")` dekoratör |

**Kurulum adımları HAFTA-1-KURULUM.md dosyasında.**

### Gün 3-4: FastAPI Backend Oluşturma (~2 saat)

FastAPI, .NET'teki Minimal API'ye çok benzer:

```
// .NET Minimal API              # FastAPI (Python)
app.MapPost("/classify",         @app.post("/classify")
  async (Request req) =>         async def classify(req: Request):
  {                                  result = await process(req)
    var result = await             return result
      Process(req);
    return result;
  });
```

Bu aşamada backend kodunu yazacak ve OpenAI'a ilk çağrıyı yapacağız.

### Gün 5-6: Angular Frontend + Entegrasyon (~2 saat)

Angular tarafını zaten biliyorsun. Sadece:

1. `ng new` ile proje oluştur
2. Bir form component'i yaz
3. HttpClient ile POST at
4. Sonucu güzel göster

### Gün 7: Test + Deneyler (~1 saat)

Farklı metinlerle test et. Prompt'u değiştir. Sonuçları gözlemle.
"Prompt Engineering"in ilk adımları.

---

## 📁 Proje Yapısı

```
ai-classifier-app/
├── backend/
│   ├── main.py              ← FastAPI uygulamasının giriş noktası
│   ├── models.py            ← Pydantic modelleri (DTO'ların Python karşılığı)
│   ├── classifier.py        ← OpenAI API çağrısı ve iş mantığı
│   ├── config.py            ← Konfigürasyon yönetimi
│   ├── requirements.txt     ← NuGet packages'ın Python karşılığı
│   └── .env.example         ← API anahtarı şablonu
│
└── frontend/                ← Angular uygulaması (ng new ile oluşturulacak)
    └── src/
        └── app/
            ├── classifier/
            │   ├── classifier.component.ts
            │   ├── classifier.component.html
            │   └── classifier.component.css
            ├── services/
            │   └── api.service.ts
            └── models/
                └── classification.model.ts
```

---

## 🧠 Temel Kavramlar

### OpenAI API Nasıl Çalışır?

OpenAI'ın API'si bir REST servisi. Sen ona:

1. Bir **system prompt** (rolü ve kuralları tanımlar)
2. Bir **user message** (kullanıcının yazdığı metin)

gönderirsin. O sana JSON formatında bir yanıt döner.

```
POST https://api.openai.com/v1/chat/completions
{
  "model": "gpt-4o-mini",          ← Hangi modeli kullan
  "temperature": 0.1,               ← Ne kadar "yaratıcı" olsun (0=katı, 1=yaratıcı)
  "response_format": {"type": "json_object"},  ← JSON döndür
  "messages": [
    {"role": "system", "content": "Sen bir sınıflandırıcısın..."},
    {"role": "user", "content": "Ürününüz berbat, iade istiyorum!"}
  ]
}
```

**gpt-4o-mini** modeli:

- Çok ucuz (~$0.15 / 1M input token)
- Hızlı
- Bu tür sınıflandırma görevleri için fazlasıyla yeterli
- 1000 sınıflandırma ~$0.02 (2 kuruş) civarı maliyet

### Pydantic = C#'taki DTO + DataAnnotations

```python
# C#'ta:                              # Python'da (Pydantic):
# public class Request                 class Request(BaseModel):
# {                                        text: str = Field(
#   [Required]                                 ...,
#   [MaxLength(2000)]                          min_length=10,
#   public string Text { get; set; }           max_length=2000
# }                                        )
```

Pydantic, gelen veriyi otomatik doğrular. Yanlış veri gelirse 422 hatası döner.
Tıpkı .NET'teki ModelState.IsValid gibi ama otomatik.

---

## ⚠️ OpenAI API Key Alma

1. https://platform.openai.com/signup adresine git
2. Hesap oluştur (Google ile giriş yapabilirsin)
3. https://platform.openai.com/api-keys → "Create new secret key"
4. Key'i kopyala (sk-... ile başlar)
5. **ÖNEMLİ:** $5 kredi yüklemen gerekecek (Settings → Billing)
   - gpt-4o-mini çok ucuz, $5 ile haftalarca yeterli
   - Bu eğitimin tamamı ~$2-3 civarı API maliyeti

> 💡 Şirket bilgisayarında kısıtlama varsa Azure OpenAI da kullanılabilir.
> Kod, her iki servisi de destekleyecek şekilde yazılıyor.

---

## 🚀 Hazır mısın?

Aşağıdaki sırayla ilerle:

1. **HAFTA-1-KURULUM.md** → Python ve bağımlılıkları kur
2. **backend/** klasöründeki kodları incele ve çalıştır
3. **frontend/** Angular uygulamasını oluştur ve bağla
4. Test et, prompt'u değiştirerek dene

Her dosyada Türkçe açıklamalar ve .NET/C# karşılaştırmaları var.
