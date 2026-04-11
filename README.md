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
        ↓
LangGraph Supervisor (sequential analysis + revision loop)
   ├── Eligibility Agent  →  Groq (Llama 3.3 70B)
   ├── Rights Agent       →  Groq (Llama 3.3 70B)
   ├── Advocate Agent     →  Gemini 2.0 Flash
   └── Critic Agent       →  Gemini 2.0 Flash
        ↓
Structured source provenance + lawyer review data
        ↓
FastAPI  →  React frontend
```

**Total cost: low** — Groq free tier + Gemini free tier + local Ollama embeddings + capped Indian Kanoon usage

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
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env    # fill in your API keys
```

### 3. Get API keys (both free)

- **Groq**: https://console.groq.com → Create API key
- **Gemini**: https://aistudio.google.com → Get API key

### 4. Set up local embeddings

```bash
# Install Ollama: https://ollama.com
ollama pull nomic-embed-text   # 274MB, CPU-safe
```

### 5. Seed the knowledge base (one-time)

```python
# Run from backend/
from rag.pipeline import ingest_pdf

# Ingest IPC/CrPC (download PDFs from legislative.gov.in)
ingest_pdf("data/raw/ipc.pdf", {"category": "statute", "court": "central"})
ingest_pdf("data/raw/crpc.pdf", {"category": "statute", "court": "central"})

# Ingest key SC judgments (download from indiankanoon.org)
ingest_pdf("data/raw/hussainara_khatoon.pdf", {"category": "constitutional", "court": "Supreme Court"})
```

### 6. Start backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 7. Start frontend

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
│   │   ├── state.py           # Shared LangGraph state
│   │   ├── eligibility_agent.py
│   │   ├── rights_agent.py
│   │   ├── advocate_agent.py
│   │   ├── critic_agent.py
│   │   └── graph.py           # LangGraph orchestrator
│   ├── rag/
│   │   └── pipeline.py        # Ingestion + retrieval
│   ├── utils/
│   │   └── llm_config.py      # Groq + Gemini + Ollama clients
│   ├── main.py                # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/                   # Vite + React frontend
│   ├── package.json
│   └── index.html
├── data/
│   ├── raw/                   # Put PDFs here
│   └── chroma_db/             # Auto-created vector store
├── prompts/                   # Store prompt templates here
└── .env.example
```

---

## Key legal references used

- **Section 436A CrPC** — default bail after half of max sentence
- **Section 167 CrPC** — 60/90 day remand limits
- **Article 21** — Right to life and personal liberty
- **Hussainara Khatoon v. State of Bihar (1979)** — right to speedy trial
- **Maneka Gandhi v. Union of India (1978)** — expanded Article 21

---

## Analyze API response

`POST /analyze` returns the core reports plus lawyer-review metadata:

- `eligibility_report`
- `rights_report`
- `final_brief`
- `plain_summary`
- `critic_feedback`
- `critic_verdict`
- `revisions_done`
- `retrieved_sources`
- `eligibility_sources`
- `rights_sources`
- `revision_history`

The source arrays contain compact metadata and excerpts so a lawyer can inspect the authorities used to ground the analysis.

---

## Resume description

> Built an agentic RAG system using LangGraph, ChromaDB, and Groq/Gemini
> that generates bail eligibility briefs for undertrial prisoners in India.
> Three specialist agents (eligibility, rights, advocate) work over a
> legal knowledge base built from IPC, CrPC, and Supreme Court
> precedents, with a critic agent performing hallucination detection,
> revision feedback, and source-grounded review metadata for advocates.
> Deployed to NGOs and legal aid clinics as a zero-cost
> alternative to legal consultation.
