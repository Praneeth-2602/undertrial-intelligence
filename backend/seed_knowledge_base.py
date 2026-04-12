"""
seed_knowledge_base.py — run once to populate ChromaDB.

Usage:
    cd backend
    python seed_knowledge_base.py

Layers:
    1. Hardcoded SC excerpts  — always runs, no API needed
    2. IPC + CrPC PDFs        — downloads from legislative.gov.in
    3. Indian Kanoon cases    — real case law (needs INDIAN_KANOON_API_TOKEN)
"""

import os, sys, time, httpx
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from rag.pipeline import ingest_pdf, search_and_ingest_kanoon, get_vector_store
from langchain.schema import Document

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
INDIAN_KANOON_TOKEN = os.getenv("INDIAN_KANOON_API_TOKEN", "")

# ── Statute PDFs ──────────────────────────────────────────────────────────────
STATUTES = [
    {
        "url": "https://legislative.gov.in/sites/default/files/A1860-45.pdf",
        "filename": "ipc_1860.pdf",
        "metadata": {"category": "statute", "court": "central", "title": "Indian Penal Code 1860", "source": "legislative.gov.in"},
    },
    {
        "url": "https://legislative.gov.in/sites/default/files/A1973-2.pdf",
        "filename": "crpc_1973.pdf",
        "metadata": {"category": "statute", "court": "central", "title": "Code of Criminal Procedure 1973", "source": "legislative.gov.in"},
    },
]

# ── Indian Kanoon search queries ──────────────────────────────────────────────
# Keep these intentionally narrow to avoid unnecessary paid API usage.
KANOON_QUERIES = [
    {"query": "\"section 436A\" ANDD bail", "text": "undertrial", "limit": 3, "note": "Section 436A undertrial bail"},
    {"query": "\"section 167(2)\" ANDD \"default bail\"", "text": "remand", "limit": 3, "note": "Section 167 default bail"},
    {"query": "\"Article 21\" ANDD \"speedy trial\"", "text": "undertrial bail", "limit": 2, "note": "Article 21 speedy trial"},
    {"query": "\"Arnesh Kumar\" ANDD \"section 41\"", "text": "arrest guidelines", "limit": 2, "note": "Arnesh Kumar guidelines"},
]

# ── Hardcoded SC excerpts ─────────────────────────────────────────────────────
HARDCODED_EXCERPTS = [
    {
        "content": """Section 436A CrPC - Maximum period for which an undertrial prisoner can be detained:
Where a person has undergone detention for a period extending up to one-half of the maximum
period of imprisonment specified for that offence under that law, he shall be released by the
Court on his personal bond with or without sureties.

Explanation: In computing the period of detention under this section for granting bail, the
period of detention passed due to delay in proceeding caused by the accused shall be excluded.""",
        "metadata": {"category": "statute", "court": "central", "title": "Section 436A CrPC - Default Bail", "source": "hardcoded_excerpt", "section": "436A"},
    },
    {
        "content": """Section 167(2) CrPC - Remand Limits and Default Bail:
No Magistrate shall authorise the detention of the accused person in custody for a total
period exceeding—
(i)  ninety days, where the investigation relates to an offence punishable with death,
     imprisonment for life or imprisonment for a term of not less than ten years;
(ii) sixty days, where the investigation relates to any other offence.
On expiry of said period, the accused person shall be released on bail if he furnishes bail.""",
        "metadata": {"category": "statute", "court": "central", "title": "Section 167(2) CrPC - Remand Limits", "source": "hardcoded_excerpt", "section": "167"},
    },
    {
        "content": """Hussainara Khatoon v. State of Bihar (1979) AIR 1369 - Supreme Court of India
Justice P.N. Bhagwati held: The right to speedy trial is a fundamental right implicit in
Article 21. No procedure which does not ensure a reasonably quick trial can be regarded as
reasonable, fair and just. The State directed to release undertrials in custody longer than
their maximum sentence. State must provide free legal aid to indigent accused.""",
        "metadata": {"category": "constitutional", "court": "Supreme Court of India", "title": "Hussainara Khatoon v. State of Bihar (1979)", "source": "hardcoded_excerpt", "citation": "AIR 1979 SC 1369"},
    },
    {
        "content": """Arnesh Kumar v. State of Bihar (2014) 8 SCC 273 - Supreme Court of India
Police must satisfy themselves about the necessity of arrest under Section 41 CrPC before
arresting any person where the offence is punishable with imprisonment up to 7 years.
Magistrates must apply their mind before authorising detention. Section 41A CrPC notice
must be issued mandatorily where arrest is not required. Non-compliance attracts departmental action.""",
        "metadata": {"category": "constitutional", "court": "Supreme Court of India", "title": "Arnesh Kumar v. State of Bihar (2014)", "source": "hardcoded_excerpt", "citation": "2014 8 SCC 273"},
    },
    {
        "content": """Sanjay Chandra v. CBI (2012) 1 SCC 40 - Supreme Court of India
Bail principles: Nature and gravity of accusation, antecedents, risk of flight, interests
of justice. Long incarceration before being proved guilty defeats Article 21.
Pre-trial detention should not be punitive. Courts must balance individual liberty against
societal interest in ensuring the accused faces trial.""",
        "metadata": {"category": "constitutional", "court": "Supreme Court of India", "title": "Sanjay Chandra v. CBI (2012)", "source": "hardcoded_excerpt", "citation": "2012 1 SCC 40"},
    },
    {
        "content": """Article 21 - Protection of life and personal liberty:
No person shall be deprived of his life or personal liberty except according to procedure
established by law. Expanded scope includes: right to speedy trial (Hussainara Khatoon, 1979),
right to free legal aid, right against solitary confinement (Sunil Batra, 1978), right
against handcuffing (Prem Shankar Shukla, 1980), right to bail in cases of inordinate delay
(Common Cause, 1996). Procedure must be right, just and fair — not arbitrary (Maneka Gandhi, 1978).""",
        "metadata": {"category": "constitutional", "court": "Supreme Court of India", "title": "Article 21 - Right to Life and Personal Liberty", "source": "hardcoded_excerpt", "section": "Article 21"},
    },
]

# ── Seeding functions ─────────────────────────────────────────────────────────

def download_pdf(url: str, dest: Path) -> bool:
    if dest.exists():
        print(f"  ✓ Already downloaded: {dest.name}")
        return True
    try:
        print(f"  ↓ Downloading {dest.name}...")
        with httpx.stream("GET", url, timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        print(f"  ✓ Saved {dest.name} ({dest.stat().st_size // 1024} KB)")
        return True
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return False

def seed_hardcoded():
    print("\n⚖️  Seeding landmark SC excerpts (no API needed)...")
    store = get_vector_store()
    docs = [Document(page_content=e["content"], metadata=e["metadata"]) for e in HARDCODED_EXCERPTS]
    store.add_documents(docs)
    print(f"  ✅ {len(docs)} excerpts ingested")

def seed_statutes():
    print("\n📚 Seeding statutes (IPC + CrPC)...")
    for s in STATUTES:
        dest = RAW_DIR / s["filename"]
        if download_pdf(s["url"], dest):
            try:
                count = ingest_pdf(str(dest), s["metadata"])
                print(f"  ✅ {count} chunks — {s['metadata']['title']}")
            except Exception as e:
                print(f"  ✗ Ingestion error: {e}")
        time.sleep(1)

def seed_kanoon_dev():
    if not INDIAN_KANOON_TOKEN:
        print("\n⚠️  INDIAN_KANOON_API_TOKEN not set — skipping live case law seeding.")
        print("   Docs: https://api.indiankanoon.org/access/")
        print("   Add to .env: INDIAN_KANOON_API_TOKEN=your_token")
        return

    print(f"\n🔍 Seeding {len(KANOON_QUERIES)} focused queries from Indian Kanoon...")
    total = 0
    for q in KANOON_QUERIES:
        print(f"\n  [{q['note']}]")
        try:
            count = search_and_ingest_kanoon(query=q["query"], text=q["text"], limit=q["limit"])
            total += count
            time.sleep(1)
        except Exception as e:
            print(f"  ✗ Error: {e}")
    print(f"\n  ✅ Indian Kanoon total: {total} chunks")

def verify_store():
    print("\n🔍 Verifying vector store...")
    store = get_vector_store()
    results = store.similarity_search("bail eligibility undertrial section 436A", k=3)
    print(f"  ✅ Store live — {len(results)} sample results:")
    for r in results:
        title = r.metadata.get("title", r.metadata.get("case_id", "untitled"))
        print(f"    → {title[:72]}")

if __name__ == "__main__":
    print("=" * 60)
    print("  Undertrial Intelligence System — Knowledge Base Seeder")
    print("  Legal data: Indian Kanoon + legislative.gov.in + SC excerpts")
    print("=" * 60)

    seed_hardcoded()
    seed_statutes()
    seed_kanoon_dev()
    verify_store()

    print("\n✅ Done! Start the backend: uvicorn main:app --reload")
