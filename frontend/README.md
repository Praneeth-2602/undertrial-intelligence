# Undertrial Intelligence — React Frontend

A Vite + React app that replaces the single-file `index.html` frontend
with a properly structured, production-grade UI.

## Design direction

- **Palette**: Aged paper (`#faf7f2`) with rust red (`#a63d1f`) accents — evokes
  court ledgers and ink-on-paper documents, not a generic AI dashboard.
- **Typography**: Playfair Display (headings) · Spectral (body/prose) · IBM Plex Mono (UI labels/code)
- **No CSS framework** — CSS Modules throughout, pure CSS variables for the design system.

## Pages

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Analysis | Case input form + live pipeline tracker + BriefViewer |
| `/knowledge` | Knowledge Base | PDF ingest + Indian Kanoon search + activity log |
| `/about` | About | Architecture, legal framework, stack, disclaimer |

## Structure

```
src/
├── App.jsx              — Router + 30s health-check polling
├── index.css            — Design system (CSS variables, prose styles)
├── main.jsx             — Entry point
├── lib/
│   └── api.js           — fetch wrappers for /analyze, /ingest/*, /health
├── components/
│   ├── Header.jsx        — Sticky nav + live API status dot
│   ├── CaseForm.jsx      — 4-section form (accused, FIR, charges, detention)
│   └── BriefViewer.jsx   — Tabbed output (Brief, Summary, Eligibility, Rights, Review)
└── pages/
    ├── AnalysisPage.jsx  — Split-pane layout + pipeline step animation
    ├── KnowledgePage.jsx — PDF drag-drop + Kanoon search + log
    └── AboutPage.jsx     — System overview + legal refs + stack
```

## Setup

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

The Vite dev server proxies `/api/*` → `http://localhost:8000` so the
backend CORS config requires no changes.

## Build for production

```bash
npm run build        # outputs to dist/
npm run preview      # preview the production build
```

## Backend CORS note

`main.py` already allows `http://localhost:5173`. For production deployment,
add your deployed origin to the `allow_origins` list.
