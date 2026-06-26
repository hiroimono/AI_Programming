# rag-service

Central **R**etrieval-**A**ugmented **G**eneration microservice. Owns all
document parsing, embedding, vector storage, and semantic search for the
SaaS portfolio.

- Consumed by **Level-2-App** (writing assistant) and **Level-3-App** (chatbot SaaS).
- Future apps (Level-4+, Notebooks) plug in via the same contract.
- Per-app data isolation via PostgreSQL **schema-per-app** (e.g. `rag_level2_writer`, `rag_level3_chatbot`).
- Shared embedding cache (`rag_shared.embedding_cache`) deduplicates identical content across apps to cut OpenAI cost.

**Architecture decision record (must-read):**

- TR: `Documents/Strategy Documents/4.1 RAG Mikroservis Mimarisi ve Schema-per-App Yaklaşımı (TR).md`
- EN: `Documents/Strategy Documents/4.2 RAG Microservice Architecture and Schema-per-App Approach (EN).md`

**Implementation plan (phase-by-phase):**

- TR: `Documents/Plans/Level-2-RAG-Addon-Plan-TR.md`
- EN: `Documents/Plans/Level-2-RAG-Addon-Plan-EN.md`

---

## Current status

**Phase 0 — scaffold.** FastAPI app with a single `/api/health` endpoint.
No database, no RAG logic yet. Later phases bring Neon + Alembic, the
RAG pipeline (parsers / chunker / embedder / retriever), the document
and search endpoints, and security middleware.

## Local development

```powershell
# From the RAG-Service/ folder:
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy the env template and edit if needed:
Copy-Item .env.example .env

# Run on port 8100:
uvicorn rag_service.main:app --reload --port 8100
```

Verify:

```powershell
curl http://localhost:8100/api/health
# → {"status":"ok","service":"rag-service","version":"0.1.0"}
```

Or use the VS Code task: **RAG Service: Start**.

## Layout

```text
RAG-Service/
├─ rag_service/        # Python package
│  ├─ __init__.py
│  ├─ main.py          # FastAPI app (Phase 0: /api/health)
│  └─ config.py        # pydantic-settings loader
├─ requirements.txt
├─ .env.example
└─ README.md
```

Folders that appear in later phases: `alembic/`, `rag_service/routers/`,
`rag_service/models/`, `rag_service/rag/`, `tests/`, `storage/` (gitignored).
