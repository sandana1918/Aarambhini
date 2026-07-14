# Aarambhini — Backend (FastAPI + MongoDB Atlas)

Production API layer. Reuses the LangGraph agent crew at the repo root and adds
persistence, seeded real-India compliance rules, and an approval-gated publish flow.

## Setup
```bash
pip install -r requirements.txt          # root: agents + LangGraph
pip install -r backend/requirements.txt  # backend: FastAPI + Motor
```
Add to `.env` (never committed):
```
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
DB_NAME=aarambhini
```

## Seed the database
```bash
python -m backend.seed --dry-run   # validate data, no DB needed
python -m backend.seed             # upsert into Atlas (idempotent)
```
Seeds **13 categories** of real Indian compliance regimes (Legal Metrology,
FSSAI, BIS hallmarking, Toys QCO, Cosmetics Rules 2020, AYUSH …) — each cited with
`source_url`, `effective_date`, and flagged `needs_legal_review=true`.

## Run
```bash
uvicorn backend.main:app --reload   # from the repo root
```
Open `/docs` for the interactive API. Key routes:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | service + DB status |
| POST | `/sellers` | register a seller |
| POST | `/listings/run` | run the agent crew, persist a draft |
| POST | `/listings/{id}/approve` | approval gate → publish + audit log |
| GET | `/compliance/{category}` | seeded rule + price benchmark |

## Layout
```
backend/
  main.py            FastAPI app + lifespan (indexes on startup)
  config.py          env settings
  db.py              Motor client, collection names, indexes
  models.py          Pydantic schemas (match the HLD)
  seed.py            compliance + benchmarks seeder
  routers/           sellers · listings · rules
  data/              compliance_rules.json (13 cats) · price_benchmarks.csv
```

> Honesty: every compliance rule is `needs_legal_review=true` and must be verified
> against the current official text before any legal assertion is shown to a seller.
