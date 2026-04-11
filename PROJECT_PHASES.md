# 7-Day Delivery Plan

This repository is best pushed in 7 phases so the history stays readable and each day has a clear scope.

## Commit strategy

- Make small local commits during the day if needed.
- End each day with one clean push-ready commit for that phase.
- If you want a cleaner GitHub history, squash the same-day commits before pushing.

## Phase 1 - Repo and baseline cleanup

Scope:
- Root Git repo only
- Clean ignore rules
- Frontend folder structure fixed
- Backend environment bootstrapped

Suggested commits:
- `chore: initialize root git repo`
- `chore: normalize repo structure and ignore files`

## Phase 2 - Backend API stabilization

Scope:
- FastAPI routes
- request/response models
- health check and ingestion endpoints
- error handling and CORS

Suggested commits:
- `feat: stabilize api contracts`
- `fix: harden backend request validation`

## Phase 3 - RAG and knowledge ingestion

Scope:
- PDF ingestion flow
- Indian Kanoon ingestion
- vector store seeding
- prompt loading and utility cleanup

Suggested commits:
- `feat: improve knowledge ingestion pipeline`
- `feat: seed legal knowledge base`

## Phase 4 - Agent workflow and brief quality

Scope:
- eligibility, rights, advocate, critic agent flow
- graph orchestration
- brief generation quality
- revision loop and source grounding

Suggested commits:
- `feat: refine agent orchestration`
- `fix: improve brief generation consistency`

## Phase 5 - Frontend presentation and UX

Scope:
- legal-grade visual polish
- navigation/header
- form usability
- briefing/output layout
- responsive behavior

Suggested commits:
- `feat: redesign frontend presentation`
- `feat: refine lawyer-facing case input flow`

## Phase 6 - Reliability and testing

Scope:
- install/build checks
- API integration verification
- edge cases
- dependency cleanup

Suggested commits:
- `test: add verification for core flows`
- `fix: resolve build and runtime issues`

## Phase 7 - Documentation and release readiness

Scope:
- README cleanup
- setup instructions
- architecture notes
- final review and release notes

Suggested commits:
- `docs: finalize project documentation`
- `chore: prepare release-ready history`

## Recommended daily order

1. Work on one phase only.
2. Commit local checkpoints as needed.
3. Rebase or squash within the day if the history gets noisy.
4. Push one finished phase per day.

