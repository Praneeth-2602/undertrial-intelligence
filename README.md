# Undertrial Intelligence System

A RAG + multi-agent system that generates bail eligibility briefs,
constitutional rights reports, and plain-language summaries for
undertrial prisoners in India. Built for NGOs and legal aid clinics.

---

## Architecture

```
Data Sources (Indian Kanoon, IPC/CrPC PDFs, FIR input)
        ↓
ChromaDB (local vector store via Ollama embeddings)
        ↓ authority-aware reranking + diagnostic logging
LangGraph Supervisor (sequential analysis + revision loop)
   ├── Eligibility Agent  →  Groq (Llama 3.3 70B)  + reranked retrieval
   ├── Rights Agent       →  Groq (Llama 3.3 70B)  + reranked retrieval
   ├── Advocate Agent     →  Gemini 2.0 Flash
   └── Critic Agent       →  Gemini 2.0 Flash  + structured citation verification
        ↓
Structured source provenance + citation-grounded lawyer review
        ↓
FastAPI  →  React frontend
```

**Total cost: low** — Groq free tier + Gemini free tier + local Ollama embeddings + capped Indian Kanoon usage

---

## What's implemented

| Feature | Status |
|---|---|
| PDF ingestion with chunk quality checks | ✅ |
| Indian Kanoon search + full-text ingestion | ✅ |
| Ingestion deduplication (SHA-256 bookkeeping) | ✅ |
| Authority-aware retrieval reranking | ✅ |
| Retrieval diagnostics (scores, hit logging) | ✅ |
| LangGraph multi-agent orchestration | ✅ |
| Parallel eligibility + rights analysis | ✅ |
| Advocate drafting with prior-draft context | ✅ |
| Critic with structured citation verification | ✅ |
| Revision loop (max 2 iterations) | ✅ |
| Source provenance for lawyer review | ✅ |
| Frontend: brief viewer, sources, revision history | ✅ |
| Smoke tests + retrieval evaluation harness | ✅ |

---

## Setup

### 1. Clone and install

```bash
git clone <repo>
cd undertrial-intelligence
```

### 2. Set up backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env         # fill in your API keys
```

### 3. Required API keys

| Key | Where to get |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com → Create API key (free) |
| `GOOGLE_API_KEY` | https://aistudio.google.com → Get API key (free) |
| `INDIAN_KANOON_API_TOKEN` | https://api.indiankanoon.org → register (paid, conservative usage) |

### 4. Local embeddings (Ollama)

```bash
# Install Ollama: https://ollama.com
ollama pull nomic-embed-text    # 274MB, CPU-safe
```

### 5. Environment variables (`.env`)

```env
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.3-70b-versatile

GOOGLE_API_KEY=your_key
GEMINI_MODEL=gemini-2.0-flash-exp

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text

INDIAN_KANOON_API_TOKEN=your_token
INDIAN_KANOON_MAX_DOCS_PER_QUERY=5
INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY=2
INDIAN_KANOON_RATE_LIMIT_SECONDS=0.35

CHROMA_PERSIST_DIR=./data/chroma_db
INGESTION_LOG_PATH=./data/ingestion_log.json
```

### 6. Seed the knowledge base (one-time)

```bash
cd backend
python seed_knowledge_base.py
```

Or use the API endpoints:

```bash
# Upload a PDF
curl -X POST http://localhost:8000/ingest/pdf \
  -F "file=@data/raw/crpc.pdf" \
  -F "category=statute" -F "court=central"

# Ingest from Indian Kanoon
curl -X POST http://localhost:8000/ingest/kanoon \
  -H "Content-Type: application/json" \
  -d '{"query": "\"section 436A\" bail undertrial", "limit": 5}'
```

### 7. Start backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 8. Start frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Project structure

```
undertrial-intelligence/
├── backend/
│   ├── agents/
│   │   ├── state.py                # Shared LangGraph state + TypedDicts
│   │   ├── eligibility_agent.py    # 436A / default bail analysis
│   │   ├── rights_agent.py         # Art. 21 / speedy trial analysis
│   │   ├── advocate_agent.py       # Brief drafting (Gemini)
│   │   ├── critic_agent.py         # Hallucination detection + citation verification
│   │   ├── graph.py                # LangGraph orchestrator
│   │   └── source_utils.py         # Source record building + merging
│   ├── rag/
│   │   └── pipeline.py             # Ingestion, deduplication, reranking, retrieval
│   ├── utils/
│   │   ├── llm_config.py           # Groq + Gemini + Ollama clients
│   │   └── prompt_loader.py        # Load prompts from /prompts/
│   ├── tests/
│   │   └── test_rag_phase1.py      # Unit + smoke + retrieval evaluation tests
│   ├── main.py                     # FastAPI app
│   ├── seed_knowledge_base.py      # One-time knowledge base seeder
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/             # BriefViewer, CaseForm, Header
│   │   ├── pages/                  # AnalysisPage, KnowledgePage, AboutPage
│   │   └── lib/api.js              # API client
│   └── package.json
├── prompts/                        # Prompt templates for each agent
├── data/
│   ├── raw/                        # Place PDF documents here
│   ├── chroma_db/                  # Auto-created vector store
│   └── ingestion_log.json          # Auto-created deduplication log
└── .env.example
```

---

## API reference

### `POST /analyze`

Run the full multi-agent pipeline. Returns:

| Field | Description |
|---|---|
| `eligibility_report` | Bail eligibility under 436A / 167 CrPC |
| `rights_report` | Constitutional rights violations (Art. 21) |
| `final_brief` | Critic-approved complete legal brief |
| `plain_summary` | Plain-language summary for family |
| `critic_feedback` | Full critic review text |
| `critic_verdict` | `APPROVE` or `REVISE` |
| `revisions_done` | Number of revision iterations |
| `retrieved_sources` | List of source records used (title, excerpt, court, category) |
| `eligibility_sources` | Sources used by eligibility agent |
| `rights_sources` | Sources used by rights agent |
| `revision_history` | Per-iteration verdict, issues, citation check report |

### `GET /retrieval/diagnose?query=...&k=6`

Test retrieval without running the pipeline. Returns similarity scores,
authority scores, and combined ranking for each result. Useful for
evaluating whether the right legal authorities are being surfaced.

### `GET /ingestion/status`

Returns the deduplication log — all ingested content hashes and labels.

### `POST /ingest/pdf`

Upload a PDF. Automatically skips if same file was already ingested.

### `POST /ingest/kanoon`

Search Indian Kanoon and ingest results. Safe to call repeatedly —
duplicate documents are detected and skipped.

---

## Running tests

```bash
cd backend
python -m pytest tests/test_rag_phase1.py -v
```

Tests cover:

- Source record building and deduplication
- Chunk quality filtering
- Source authority ranking
- Retrieval reranking (statute > judgment > unknown)
- Citation extraction and verification
- Critic verdict recording and history
- Revision cap enforcement (max 2)
- API smoke tests for all endpoints
- Retrieval evaluation harness with fixed legal queries

---

## Key legal references

- **Section 436A CrPC** — default bail after half of max sentence
- **Section 167 CrPC** — 60/90 day remand limits
- **Article 21** — Right to life and personal liberty
- **Hussainara Khatoon v. State of Bihar (1979)** — right to speedy trial
- **Maneka Gandhi v. Union of India (1978)** — expanded Article 21

---

## Known limitations

- Retrieval uses vector similarity + authority reranking; no BM25 hybrid search yet
- Citation verification is pattern-based, not semantic — may miss paraphrased citations
- No authentication or audit trail (suitable for single-user NGO deployments)
- No export workflow beyond print/copy in the frontend
