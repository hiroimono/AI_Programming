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

## Current status

**Phases 0–4 complete.** Service is feature-complete and end-to-end
verified in-process. JWT-protected endpoints expose document ingest
(`POST/GET/DELETE /api/documents`) and semantic retrieval
(`POST /api/retrieve`). Not yet integrated with Level-2 BE — that's
Phase 5.

For the full architecture, request flows, design decisions, and the
public HTTP contract, read:

- **EN:** [`ARCHITECTURE-AND-DECISIONS-EN.md`](./ARCHITECTURE-AND-DECISIONS-EN.md)
- **TR:** [`MIMARI-VE-KARARLAR-TR.md`](./MIMARI-VE-KARARLAR-TR.md)

## Local development

```powershell
# From the RAG-Service/ folder:
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy the env template and edit (DATABASE_URL, OPENAI_API_KEY, INTERNAL_JWT_SECRET):
Copy-Item .env.example .env

# Run on port 8100:
uvicorn rag_service.main:app --reload --port 8100
```

Verify:

```powershell
curl http://localhost:8100/api/health
# → {"status":"ok","service":"rag-service","version":"0.2.0"}
```

Or use the VS Code task: **RAG Service: Start**.

## Layout

```text
RAG-Service/
├─ rag_service/
│  ├─ main.py                # FastAPI app + lifespan + router mount
│  ├─ config.py              # pydantic-settings
│  ├─ db.py                  # async SQLAlchemy engine
│  ├─ auth.py                # internal JWT verify dependency
│  ├─ storage.py             # filesystem blob storage
│  ├─ chunker.py             # tiktoken sliding window
│  ├─ embedder.py            # OpenAI embeddings
│  ├─ retriever.py           # pgvector cosine top-k
│  ├─ pipeline.py            # ingest + retrieve orchestrator
│  ├─ schemas.py             # Pydantic request/response models
│  ├─ parsers/               # pdf/docx/xlsx/txt
│  ├─ models/                # SQLAlchemy ORM (level2, level3)
│  └─ routers/               # documents + retrieve endpoints
├─ alembic/                  # schema-aware migrations
├─ requirements.txt
├─ .env.example
├─ README.md
├─ ARCHITECTURE-AND-DECISIONS-EN.md
└─ MIMARI-VE-KARARLAR-TR.md
```
