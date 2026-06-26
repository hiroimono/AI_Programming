# Gateway (.NET) — Nasıl Çalıştırırım?

> **Hızlı özet:** ASP.NET Core Web API, port **5000** (HTTP) / **5001** (HTTPS).
> Tek bir terminal, tek bir komut.

## Ön koşullar (bir kerelik)

- .NET 9 SDK kurulu (`dotnet --version`).
- HTTPS dev sertifikası onaylı: `dotnet dev-certs https --trust` (bir defa).
- `appsettings.Development.json` veya `.env` içinde DB connection string ve auth secret'ları set.

## Başlatma

```powershell
cd Gateway\src\Gateway.API
dotnet run
```

Hazır olduğunda terminalde:

```text
Now listening on: https://localhost:5001
Now listening on: http://localhost:5000
Application started. Press Ctrl+C to shut down.
```

## Doğrulama

| Servis         | URL                              |
| -------------- | -------------------------------- |
| Swagger UI     | <https://localhost:5001/swagger> |
| Health (varsa) | <https://localhost:5001/health>  |

İlk açılışta tarayıcı sertifika uyarısı verebilir — kabul et (dev cert).

## Durdurma

`Ctrl + C`.

## Tek tıkla alternatif (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **Gateway (.NET)**.

## Hangi app'lerle birlikte çalışır?

- **Level-2 (AI Writing Assistant):** Mecburi — auth + konuşma DB'si Gateway'de.
- **Level-1 (AI Classifier):** Opsiyonel — Level-1 doğrudan kendi backend'ine bağlanır.
- **Level-3+ (gelecek):** Mecburi.

## Bağımlı/Sıralı başlatma

Gateway DB migration'larını ilk kez çalıştırmak için:

```powershell
cd Gateway\src\Gateway.API
dotnet ef database update
```

(EF Core tools kurulu değilse: `dotnet tool install --global dotnet-ef`.)
