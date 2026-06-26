# Gateway (.NET) — How to Run

> **Quick reference:** ASP.NET Core Web API, port **5000** (HTTP) / **5001** (HTTPS).
> One terminal, one command.

## Prerequisites (one-time)

- .NET 9 SDK installed (`dotnet --version`).
- HTTPS dev certificate trusted: `dotnet dev-certs https --trust` (once).
- `appsettings.Development.json` or `.env` has DB connection string and auth secrets set.

## Start

```powershell
cd Gateway\src\Gateway.API
dotnet run
```

Ready when you see:

```text
Now listening on: https://localhost:5001
Now listening on: http://localhost:5000
Application started. Press Ctrl+C to shut down.
```

## Verify

| Service             | URL                              |
| ------------------- | -------------------------------- |
| Swagger UI          | <https://localhost:5001/swagger> |
| Health (if defined) | <https://localhost:5001/health>  |

On first open the browser may warn about the cert — accept it (dev cert).

## Stop

`Ctrl + C`.

## One-click alternative (VS Code)

`Ctrl + Shift + P` → **Tasks: Run Task** → **Gateway (.NET)**.

## Which apps require it?

- **Level-2 (AI Writing Assistant):** Required — auth + conversation DB live in Gateway.
- **Level-1 (AI Classifier):** Optional — Level-1 talks to its own backend directly.
- **Level-3+ (upcoming):** Required.

## DB migrations (first time / after entity changes)

```powershell
cd Gateway\src\Gateway.API
dotnet ef database update
```

(If EF Core tools aren't installed: `dotnet tool install --global dotnet-ef`.)
