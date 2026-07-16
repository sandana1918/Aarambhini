<p align="center">
  <img src="frontend/public/logo.png" alt="Aarambhini — agentic co-founder for women sellers" width="520">
</p>

**Aarambhini** *(“she who begins”)* is an **agentic AI co-founder for Bharat's women sellers**.

A seller speaks one voice note in her own language and adds one phone photo. A crew of
seven AI agents — wired as a LangGraph state machine — hears her, reads the photo, writes
the listing, prices it, makes it legally compliant, forecasts returns and plans packaging,
**checking and re-doing each other's work** through three self-correcting loops. It pauses
twice to ask her, and **nothing goes live without her tap**.

Built for **ScriptedBy{Her} 2.0**. It is an on-ramp to existing marketplaces — not another storefront.

---

## The crew

| Agent | Role | How it works |
|---|---|---|
| **Mukhiya** | The Manager | Not a file — it *is* the graph plus the gates: the quality rubric, loop routing, and the approval gate. *Deterministic* |
| **Suno** | The Ear + Cataloguer | One vision call: hears the voice note (any Indian language), reads the photo, extracts facts, fills the Meesho-style attributes, and runs the photo + authenticity gate. *Gemini vision* |
| **Likho** | The Pen | Writes title, description, keywords and maker story. On a loop it appends the exact compliance label or a size guide — verbatim. *Gemini* |
| **Daam** | The Pricer | `price = cost + shipping + overhead + margin`; `discount floor = break-even`. Re-prices to absorb label cost. *Deterministic* |
| **Niyam** | The Rulekeeper | Reads the rules base, decides required labels/licences, drafts the exact label text, and **blocks** until it's applied. *Gemini + rules* |
| **Wapsi** | The Returns Guard | Forecasts why a product may be returned — and **learns from this category's real return history**. *Gemini + data* |
| **Packaging** | The Packer | Builds a packing plan from the category's fragile/perishable flags. *Deterministic* |

Money and law are deterministic on purpose, so the numbers are defensible. Every LLM agent
has a deterministic fallback, so a run never fails outright.

## The three self-correcting loops

This is what makes it *agentic*, not just "AI" — the graph contains real cycles:

1. **Quality** — Mukhiya sends a thin listing back to Likho to rewrite richer.
2. **Compliance** — Niyam demands a label; Likho appends it **and** Daam re-prices so the margin survives the extra cost.
3. **Returns** — high return risk sends Likho back to add a size/colour guide.

## Two human-in-the-loop pauses

Real LangGraph `interrupt()`s — the graph pauses with its state checkpointed to MongoDB, so
a run survives a server restart:

- **Clarify** — asks only for a *blocking* gap (e.g. no price stated). She isn't interrogated for everything else.
- **Approval** — she approves, **edits the price**, or rejects. `/approve` resumes the same run.

## Architecture

<p align="center"><img src="docs/hld-diagram.png" alt="High-level design" width="760"></p>

Full detail — schemas, per-agent behaviour, sequence diagrams: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

**Stack:** Next.js 16 · FastAPI · LangGraph (Mongo checkpointer) · MongoDB Atlas · Sarvam Saarika (STT) · Google Gemini (reasoning + vision)

## Setup

**Prerequisites:** Python 3.11+, Node 18+, a MongoDB Atlas connection string, a Gemini API key, and (optionally) a Sarvam key for speech.

```bash
# 1. Install
pip install -r requirements.txt           # agents, orchestrator, graph store
pip install -r backend/requirements.txt   # FastAPI web layer
npm --prefix frontend install

# 2. Configure
cp .env.example .env                      # then fill in your keys

# 3. Seed the database (idempotent)
python -m backend.seed_demo               # reference data + a realistic marketplace
```

`.env` keys:

| Key | Purpose |
|---|---|
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Agent reasoning + photo reading (must be multimodal) |
| `MONGODB_URI` / `DB_NAME` | MongoDB Atlas |
| `STT_PROVIDER` | `sarvam` (default) or `gemini` |
| `SARVAM_API_KEY` / `SARVAM_STT_MODEL` | Speech-to-text (`saarika:v2.5`) |
| `CORS_ORIGINS` | Production origins; dev allows any localhost |

Nothing is hardcoded — no key ever lives in the source.

## Run

```bash
uvicorn backend.main:app --port 8000              # API
npm --prefix frontend run dev -- --port 3001      # web
```

Open **http://localhost:3001** → *Start selling*. Record or type a description, add a photo,
set your margin, and watch the agents stream in live.

Seeding options:

```bash
python -m backend.seed         # reference data only (rules, benchmarks, 3 sellers)
python -m backend.seed_demo    # full marketplace: 7 sellers, 10 listings, returns history
python -m backend.seed --dry-run
```

Exercise pieces standalone:

```bash
python -m agents.daam          # pure pricing arithmetic (no API key needed)
python -m agents.niyam         # rules-based compliance
python -m agents.packaging     # packing plans
python -m agents.suno          # intake + attributes (needs a key)
streamlit run app.py           # alternative single-file UI
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /listings/run` | Run the crew (multipart: `voice_text`, `photo`, `desired_margin_pct`) |
| `POST /listings/run/stream` | Same, streamed live over SSE — one event per agent |
| `POST /listings/transcribe` | Speech → text (Sarvam, Gemini fallback) |
| `POST /listings/{id}/clarify` | Answer a blocking question; resumes the paused run |
| `POST /listings/{id}/approve` | Approve / edit price / reject; resumes the paused run |
| `POST /listings/{id}/return` | Log a real buyer return — **Wapsi learns from this** |
| `GET /listings/{id}` · `GET /health` | Fetch a listing · health + DB check |

## Project layout

```
orchestrator.py       LangGraph state machine — the crew, loops, interrupts
llm.py                the one model seam: llm(), llm_json(), transcribe_audio()
graph_store.py        Mongo checkpointer · GridFS photos · pHash · return stats
agents/               suno · likho · daam · niyam · wapsi · packaging
data/                 compliance_rules.json · price_benchmarks.csv · listing_attributes.json
backend/              FastAPI app, models, db, routers, seed + seed_demo
frontend/             Next.js app — /sell flow, voice recorder, live timeline
docs/                 ARCHITECTURE.md + diagrams
```

## Honesty notes

These matter more than the demo:

- **Compliance is guidance, not legal advice.** Rules are accurate at the *category* level, carry
  `needs_legal_review: true`, and cite official sources. Verified against current Indian law
  (Legal Metrology PCR 2011, FSSAI's 2026 turnover tiers, BIS hallmarking, Toys QCO, AYUSH)
  — re-verify before production.
- **Wapsi learns only from returns logged on Aarambhini itself** (`return_events`) — never any
  other marketplace's private data. With no history it says so and reasons from category patterns.
- **Photo authenticity is layered and conservative.** A pHash match under a *different* seller
  hard-blocks as a stolen photo; watermark / stock / AI-looking are *advisory* flags that never
  auto-reject — a false accusation against a real artisan is worse than a miss.
  **AI-generated-image detection is not reliably solved**, and we don't claim it is.
- **No EXIF check, by design.** WhatsApp strips metadata, so "no EXIF = fake" would false-flag
  most rural sellers.
- Anything not built yet is listed as such in the architecture doc rather than implied.

## Swapping providers

Every model call goes through **`llm.py`** — `llm()`, `llm_json()`, `transcribe_audio()`.
Point those at another provider (Bhashini, Whisper, Azure OpenAI) and the whole crew follows.
No agent, API or UI change.
