# Aarambhini — Handover / Context Document

> Read this first. It is written so someone (or an AI agent) with **zero prior context** can
> pick the project up, understand *why* things are the way they are, and continue safely.
> Last updated: 2026-07-16.

---

## 1. What this is

**Aarambhini** *("she who begins")* — an **agentic AI co-founder for Bharat's women sellers**.

A rural woman seller speaks **one voice note in her own language** and adds **one phone photo**.
A crew of **seven AI agents** (a LangGraph state machine) produces a complete, legally
compliant, returns-proofed marketplace listing. It pauses twice to ask her, and **nothing
publishes without her approval**.

- **Positioning (important):** it is an **on-ramp to existing marketplaces — NOT another storefront.**
  Do not build a competing marketplace/browse UI without re-reading §9.
- **Context:** built for **ScriptedBy{Her} 2.0** (Meesho hackathon).
- **This is an INDIVIDUAL project** — one author. Use **"I"**, never "we", in all docs/scripts.
- **Repo:** https://github.com/sandana1918/Aarambhini

### The problem it solves
10 crore women are in Self-Help Groups; almost none sell online. Not for lack of
marketplaces — the road from product to listing is blocked at five points a first-time,
non-English-speaking seller can't cross alone: **cataloguing, pricing, compliance,
photography, returns**.

---

## 2. Current status (as of this handover)

**All four original mentor action items are complete and verified:**
1. HLD diagram + DB schemas + how each agent works → `docs/ARCHITECTURE.md`, `Aarambhini_Report.docx`
2. Speech-to-Text explored + integrated → Sarvam Saarika + Gemini fallback
3. Database integrated + seeded → MongoDB Atlas, 2 seed scripts
4. GitHub repo → created, everything pushed

**Mentor's NEW asks (not started):**
> "Please brainstorm how we can improve it further so that it will work on **all types of cases**.
> Work on **test coverage** and **deployment**." — Gubba Sai Nithin (Meesho mentor), Slack
> `#scriptedbyher-sandanas-team`

See **§10** for the audited gap list that answers this.

---

## 3. Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind 4, TypeScript |
| Backend | FastAPI + uvicorn |
| Orchestration | **LangGraph 1.2.9** (state machine, checkpointer) |
| Database | MongoDB Atlas (Motor async + pymongo sync) |
| LLM / vision | Google Gemini (`gemini-flash-lite-latest`) |
| Speech-to-text | **Sarvam Saarika** (`saarika:v2.5`), Gemini native audio as fallback |

---

## 4. Repository layout

```
orchestrator.py        LangGraph state machine — the crew, 3 loops, 2 interrupts, gates
llm.py                 THE model seam: llm(), llm_json(), transcribe_audio()
graph_store.py         sync pymongo: Mongo checkpointer · GridFS photos · pHash · return stats
app.py                 legacy Streamlit UI (still works, secondary)
agents/
  suno.py              intake + photo gate + authenticity + Meesho attributes  (Gemini vision)
  likho.py             title/description/keywords/maker story                  (Gemini)
  daam.py              pricing                                                 (DETERMINISTIC)
  niyam.py             compliance labels/licences                              (Gemini + rules)
  wapsi.py             returns forecast, LEARNS from return history            (Gemini + data)
  packaging.py         packing plan                                            (DETERMINISTIC)
  (Mukhiya = not a file — it IS the graph + its gates, in orchestrator.py)
data/                  SINGLE SOURCE OF TRUTH for reference data (see §11 trap #2)
  compliance_rules.json    13 categories, real Indian law
  price_benchmarks.csv     13 categories, shipping/fragile/perishable
  listing_attributes.json  Meesho-style per-category field specs
backend/
  main.py              FastAPI app, CORS, startup indexes, /health
  auth.py              scrypt passwords · HMAC session tokens · login throttle · ownership
  db.py                Motor client, collection names, ensure_indexes()
  models.py            Pydantic schemas
  seed.py              reference seed (rules, benchmarks, 3 sellers) + DEMO_PASSWORD
  seed_demo.py         FULL realistic seed (7 sellers, 10 listings, 74 returns)
  routers/listings.py  run · run/stream · transcribe · clarify · approve · return · GET
  routers/sellers.py   /sellers — registration (hashes the password, returns a session)
  routers/sessions.py  /sessions — login · /sessions/me
  routers/rules.py     /compliance
frontend/src/
  app/page.tsx         landing
  app/login/page.tsx   login (phone + password)
  app/register/page.tsx  registration → auto-login → /sell
  app/sell/page.tsx    THE main flow — 3 steps; redirects to /login without a session
  components/Stepper.tsx  1 Tell us → 2 The crew works → 3 Review & publish
  components/Tabs.tsx     reference panes for step 3 (NOT for anything she vouches for)
  components/          Chrome (header/logo) · VoiceRecorder · AgentTimeline · ProductDetails · icons
  lib/                 api.ts · session.ts (token store) · types.ts · recorder.ts (mic → 16kHz WAV)
docs/                  ARCHITECTURE.md + hld-diagram.png + agent-flow-diagram.png
```

---

## 5. The graph (how it actually runs)

```
START → suno → [photo_gate] ─reject→ reject → END        (bad OR stolen photo)
                     │continue
                     ↓
                  clarify  ← INTERRUPT #1 (only if a blocking gap, e.g. no price)
                     ↓
                  likho → [after_likho] ─→ review | daam | finalize
                  review → [quality_gate] ─revise→ likho          (LOOP 1: quality)
                  daam → niyam → [compliance_gate] ─loop→ likho   (LOOP 2: compliance)
                                        │done
                  packaging → wapsi → return_review
                  [return_gate] ─mitigate→ likho                  (LOOP 3: returns)
                                 │done
                  finalize → approval ← INTERRUPT #2 (seller approves/edits/rejects) → END
```

**The 3 self-correcting loops** (all loop back to Likho — one shared writer node):
1. **Quality** — Mukhiya finds a thin listing → Likho rewrites. Guard: `MAX_QUALITY_TRIES = 2`
2. **Compliance** (*the hero moment*) — Niyam demands a label → Likho appends the exact text →
   **Daam re-prices to absorb the label cost so her margin survives** → Niyam rechecks.
   Guard: `MAX_COMPLIANCE_TRIES = 3`
3. **Returns** — Wapsi says high risk → Likho adds a size/colour guide

**The 2 interrupts** are **real LangGraph `interrupt()`s** — the graph pauses with state
checkpointed to Mongo and **survives a server restart**. Resumed with `Command(resume=...)`.

**Key API:** `orchestrator.run(voice_text, image_ref, margin, thread_id, seller_id)` ·
`resume(thread_id, value)` · `stream_run(...)` (yields per-node updates) · `final_state(thread_id)`

---

## 6. Database (MongoDB Atlas, db = `aarambhini`)

| Collection | Key fields | Purpose |
|---|---|---|
| `sellers` | phone (unique), name, preferred_language, shg_name, address, packer_label, licenses | SHG sellers |
| `listings` | seller_id, thread_id, image_ref, status, suno, product_attributes, authenticity, listing, price, compliance, returns, packaging_plan, activity_log | one doc per run |
| `compliance_rules` | category (unique), required_labels, required_licenses, label_template, source_url | real Indian law |
| `price_benchmarks` | category+region (unique), typical_low/high_inr, shipping_flat_inr, fragile, perishable | pricing/packing reference |
| `image_fingerprints` | phash, seller_id, image_ref | stolen/duplicate photo detection |
| `return_events` | listing_id, category, reason | **Wapsi's learning data** |
| `audit_log` | listing_id, actor, action, payload, ts | approval trail |
| `checkpoints`, `checkpoint_writes` | thread_id, per-node state | LangGraph durable state |
| `product_images.files/.chunks` | GridFS | uploaded photos |

**`listings.status`:** `needs_clarification` → `ready_for_approval` → `published` / `rejected_by_seller`, or `needs_retake`.

---

## 7. Environment + how to run

`.env` (git-ignored — **never commit**):
```
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-flash-lite-latest
MONGODB_URI=mongodb+srv://...
DB_NAME=aarambhini
STT_PROVIDER=sarvam            # or "gemini"
SARVAM_API_KEY=...
SARVAM_STT_MODEL=saarika:v2.5
CORS_ORIGINS=                  # empty in dev = any localhost allowed
SESSION_SECRET=                # blank in dev = ephemeral per restart; REQUIRED in prod
SESSION_TTL_HOURS=12
DEMO_SELLER_PASSWORD=          # password given to seeded sellers (default: aarambhini-demo)
```

> **Demo logins:** every seeded seller's password is `aarambhini-demo`. `9990000002` is Lakshmi
> Ammal, `9990000003` is Ratna Barik; the full roster is in `backend/seed_demo.py`. Both seed
> scripts set this password **only where one is missing**, so a re-seed never clobbers a real one.

```bash
pip install -r requirements.txt          # agents/orchestrator/graph_store
pip install -r backend/requirements.txt  # web layer
npm --prefix frontend install
python -m backend.seed_demo              # full realistic seed (idempotent)

uvicorn backend.main:app --port 8000             # API
npm --prefix frontend run dev -- --port 3001     # web  →  http://localhost:3001
```

> ⚠️ **The app runs on SYSTEM Python 3.13, NOT `.venv`.** See trap #1 in §11.

**API surface:** `POST /sellers` (register → token) · `POST /sessions` (login → token) ·
`GET /sessions/me` · `POST /listings/run` ·
`/listings/run/stream` (SSE) · `/listings/transcribe` · `/listings/{id}/clarify` ·
`/listings/{id}/approve` · `/listings/{id}/return` · `GET /listings/{id}` · `GET /health` ·
`/sellers` · `/compliance`

> `clarify` · `approve` · `return` need `Authorization: Bearer <token>` **and** listing
> ownership. `run` takes the session when present; an anonymous run makes an **unowned**
> listing that can never be approved — which is why the web app signs in first.

---

## 8. Verified behaviours (proven end-to-end, not assumed)

| Feature | Evidence |
|---|---|
| Sarvam STT | spoken WAV → *"I make handmade jute bags. 40 pieces. Cost is ₹200 each."*, `detected_via: sarvam`. Forcing a bad Sarvam key → falls back to Gemini (text visibly changes to Gemini's phrasing) |
| Compliance loop | 12–13 step runs showing Likho → Likho (re-run #1) → Daam (re-price #1) → Niyam (recheck #1) |
| Clarify interrupt | no-price note → paused at `('clarify',)` → answered ₹300 → resumed to `ready_for_approval` at ₹432 |
| Approval interrupt | edit price 312 → **425** → `published`, `seller_overridden: true`, audit row written; double-approve → 409 |
| pHash | same/resized photo → Hamming **0**; inverted → **64**. Same photo, different seller → **blocked** (`needs_retake`) |
| Wapsi learning | décor 85% damaged → high risk + fragile packing; furnishing 57% size → size guide; logging 4 returns flipped toys `size_mismatch` → `damaged` |
| Live streaming | SSE steps arrive incrementally 5.3s → 16s; browser list grows 0→1→4→9→12 |
| Ownership enforcement | Lakshmi's run → `ready_for_approval` @ ₹306, `seller_id` attributed **from her session**. Ratna's token → `/approve` **404**, `/return` **404**, `/clarify` **404**; no token → **401**; listing still `ready_for_approval` after all three. Lakshmi → `published` **200**, audit `actor` resolves to **Lakshmi Ammal** (was `None`) |
| Session tokens | forged signature → 401 · expired → 401 · `''`/`nonsense`/`a.b` → 401. Browser: login → reload survives → tampered token auto-clears and bounces to `/login` |
| Register / login | register → **201** + auto-login → lands on `/sell` as the new seller · duplicate phone → **409** · password < 8 → **422** · `GET /sellers/{id}` does **not** return `password_hash` · wrong password → **401**, no session stored · 6th failed attempt → **429** for 15 min · sign out → `/login`, token gone |
| Login timing | wrong password vs unknown phone: **343ms vs 313ms** (noise). Before the dummy-hash fix it was **382ms vs 253ms** — `verify_password` short-circuited on a missing hash, so a fast reply revealed "no such seller" and undid the identical error message. Caught by measuring, not by reading |
| Seller-only fields not invented | She said only *"teddy, 4 pieces, ₹200, small size"* — yet the listing showed **Age Group: 0-1.5 Years**, invented, and that value drove the printed safety label. `listing_attributes.json` has always marked these `infer:"seller"` but only `net_quantity` was withheld from the model. Now every `infer:"seller"` field is withheld **and** dropped if returned anyway: `age_group` → `None` → asked. Same hole would have published `purity: 22K` and **`certification: "BIS Hallmark"`** she may not hold, and a `shelf_life` for food nobody measured |
| Label vs listing (age) | Real run: teddy attributed **0-1.5 Years** while the label she was told to print said **"Age Grading: 3+ Years"** — same screen, a choking-hazard toy. Root cause: `niyam.run()` never received `product_attributes`, so it drafted the label blind and invented a grading. Now: label carries **her** value, and the disagreement is raised as the **first** approval item, styled as a warning ("Please check this before printing"), citing IS 9873. Survives the compliance-loop recheck (carried forward in `niyam_node` — the agent alone returns `[]` there, since the echoed label matches and the model isn't re-called) |
| Her language at approval | Lakshmi (`ta`) → approval gate renders **Tamil** above the English, 2 Listen buttons, `/language/speak` → **200 `audio/wav`**. Same request as Ratna (`or`) → **Odia**. `preferred_language` had been collected since day one and used nowhere |
| Spoken language wins | The **Tamil-registered** account recording a **Hindi** note now gets the review in **Hindi** (`हस्तनिर्मित ऑफ-व्हाइट सूती क्रोचेट टेडी बियर`), zero Tamil on the page, and Listen requests `lang: "hi"`. Previously it answered in her *registered* Tamil while Suno's `detected_language: hi` sat unused in a decorative chip |
| Missing details, answerable | "Add these details before publishing: Age Group" is now a tap: question in **her language** + Listen + tappable options + the same voice recorder + type fallback. Tamlish *"chinna kuzhandhaigalukku, rendu vayasu"* → **`1.5-3 Years`**; "purple sparkly nonsense" → **422**, refused not guessed; an enum answer never invents a sixth option. Stranger → 404 on both new routes. Published: `age_group: 1.5-3 Years`, `missing_attributes: []` |
| Seller edits | Title + description + price editable at approval (the graph always accepted them; only the UI was missing). Through the real UI: her title, her description, ₹420 → all three in Mongo, `seller_overridden: true`, audit records `['description','price','title']`. Below break-even → warns, still lets her publish |
| Category gate | unmatched text → `None` (was `handicrafts_decor`) · hallucinated key `"food"` → rejected · `attributes_for(None)` → `{}` not a half-set · unknown → clarify asks with 13 options · known category → **0 gaps** (speak-once intact) · clarify resume applies her choice and **rebuilds** the category's attributes · a bogus key posted to `/clarify` is ignored. Live: crochet-teddy photo + matching words → `toys_games`, no interrupt, **BIS** correctly required |

---

## 9. Key design decisions — **and why** (read before changing anything)

These are deliberate. Reversing one without understanding the reason will make the product worse.

1. **Pricing + packaging are deterministic (no LLM).** Money and law must be defensible.
   `price = cost + shipping + overhead + margin`; `discount_floor = break-even`.
2. **Every LLM agent has a deterministic fallback** → a run degrades, never hard-fails.
3. **One model seam (`llm.py`).** Swapping Gemini/Sarvam → Bhashini/Whisper touches ONE file.
   Now also `translate()` (Sarvam Mayura) and `speak()` (Sarvam Bulbul TTS) — same key as STT.
   Both **degrade to the original text / no audio** rather than raising: a failed translation
   must never blank the text she is approving.
4. **Sarvam is STT primary** — India-first, handles code-mixing (Hinglish/Tamlish) and noisy
   phone audio. A demo seller speaks **Odia**, which rules out most alternatives.
5. **Audio normalised to 16 kHz mono WAV in the browser** — no server ffmpeg; every STT accepts it.
6. **NO EXIF check — deliberate.** WhatsApp strips metadata, so "no EXIF = fake" would
   false-flag almost every genuine rural seller. It is worse than useless here.
7. **Only a cross-seller pHash duplicate hard-blocks.** Watermark/stock/AI flags are
   **advisory** — *a false theft accusation against a real woman artisan is worse than a miss.*
8. **AI-generated-image detection is NOT claimed.** It isn't solved. We flag, we don't block.
9. **Clarify interrupts ONLY for a blocking gap** (missing price). Asking 6 questions would
   destroy the "speak once" promise. Everything else gets safe defaults + a checklist.
10. **`net_quantity` = units the BUYER gets per order (default 1)**, NOT her stock count.
    The model is explicitly told not to fill it.
10b. **`infer` in `listing_attributes.json` is a contract, not a hint.** `photo` = the model may
    read it; `voice` = it may hear it in her words; **`seller` = only she knows it — never
    guess**. A guessed `age_group` on a choking-hazard toy, a guessed `purity` on gold, a
    guessed `BIS Hallmark`: these are fabrications with her name on them. Seller-only fields are
    withheld from the prompt *and* dropped if the model returns them anyway, so they surface as
    a question she answers by voice.
11. **Vivran was merged into Suno** — one vision call instead of reading the photo twice.
12. **Compliance is guidance, not legal advice.** Every rule carries `needs_legal_review: true`.
13. **Wapsi learns ONLY from `return_events` on this platform** — never another marketplace's data.
14. **Positioning: on-ramp, not a storefront.** A public browse page contradicts the pitch;
    a "buyer's-eye preview" or a seller "my listings" view does not.
14a. **Steps, not tabs — and never a tab over anything she vouches for.** The flow is
    sequential (she can't review a listing before the crew writes one), so it's a 3-step
    wizard: tabs imply peers you may visit in any order, steps say "you are here". Inside
    step 3, tabs hold only *reference* panes (details · compliance · returns · packaging ·
    activity). The conflict warning, missing details, checklist and approval gate stay on the
    page: **an unopened tab reads as "no problem here"**, and "nothing publishes without her
    approval" is hollow if what she approves is hidden one click away.
14b. **Answer in the language she just SPOKE, not the one she registered with.**
    `detected_language` (this voice note) beats `preferred_language` (a tick at registration):
    a seller registered Tamil who records a Hindi note is speaking Hindi *today*, and replying
    in Tamil is the same failure as replying in English — a language she didn't choose now.
    The one exception is English input → fall back to her registered language, since typing
    English doesn't mean she wants an English review. See `spokenOrPreferred()`.
15. **The listing publishes in ENGLISH; the review is in HER language.** Buyers and the
    marketplace need English, so that stays the artifact. But asking her to approve English she
    can't read makes "nothing publishes without her approval" hollow — it *is* the problem this
    product exists to solve. So the approval gate shows her language on top, the exact English
    that publishes underneath, and a Listen button (TTS) because she may speak Tamil fluently
    and still not read it. **Never translate the compliance label text itself** — Legal
    Metrology expects the printed label in English/Hindi; translate the *explanation* of it.
    If a translation is wrong she'd be approving something she never saw, which is worse than
    English-only, so the English stays visible and is labelled as authoritative.

---

## 10. Known gaps — the audited answer to "all types of cases"

### 🔴 High risk (can actually harm a seller)
- **Category misclassification → wrong law.** *(Silent fallback fixed; the model's own
  judgement is still trusted.)* `_pick_category` used to `return "handicrafts_decor"` when no
  alias matched — so a seller whose words missed the food aliases silently became a handicraft,
  and handicrafts need no FSSAI. Proven: `niyam.run('handicrafts_decor', …)` → **no licences**;
  `niyam.run('food_packaged', …)` → **FSSAI**. That fallback was the difference.
  Now: no silent default (returns `None`), unrecognised model keys are rejected, and an unknown
  category becomes a **blocking clarify question** offering all 13 categories.
  **Still open:** a confidently *wrong* model answer passes through. Suno now returns
  `category_confidence` and a low-confidence guess her words don't corroborate is sent to her —
  but this is unit-tested only. On the one live case tried, the model answered "high", so the
  gate has never been observed firing. If the model always says "high" it buys nothing; the
  stronger fix is reconciling the photo's category against the text's and asking on disagreement.
- **A missing licence does not block publishing.** `compliance_ok = (not required_labels) or
  label_applied` — licences (FSSAI/BIS/AYUSH) are warnings only. A food seller with no FSSAI can publish.
- ~~**No auth at all.**~~ **Fixed.** Real register/login (phone + password, `hashlib.scrypt`,
  ~100ms/hash), signed session tokens, ownership enforced on `/approve` · `/clarify` · `/return`,
  and `seller_id` taken from the session rather than a spoofable form field. Login is throttled
  (5 failures → 429 for 15 min) and wrong-phone vs wrong-password are indistinguishable in both
  message *and* timing. What's still missing, in order of how much it matters:
  - **Passwords are the wrong credential for this seller** — the product's promise is that she
    speaks once instead of typing. **Phone + OTP** is the right answer; passwords were a trade
    for having no SMS provider. Revisit before real sellers touch it.
  - **No password reset.** A forgotten password needs a database edit — recovery needs the same
    verified channel OTP would give.
  - **Throttling is in-memory, per-process** — it won't hold across multiple backend instances
    (move to Mongo/Redis when the backend scales past one).
- **`GET /listings/{id}` is still open** — a guessed id exposes a seller's listing. Deliberate
  for now (the frontend reads back anonymous runs); an information-disclosure gap, not a
  publishing one.

- **The printed label is still full of blanks the app could fill.** It tells her to print
  `Mfr: <Manufacturer Name>, <Full Address>` and `BIS ISI Mark: <ISI License No.>` — while her
  own profile already holds `packer_label: {name, address}` and `licenses: {fssai, bis}`.
  `grep packer_label` across the code returns **nothing**: never read. Legal Metrology *requires*
  the packer's name and address, so the label as printed is **not compliant** — the product's
  central promise, handed back to her as a form to fill in by hand. Niyam is also never told
  she has no BIS, so it can't say so. Third instance of the same pattern
  (`preferred_language`, now `packer_label` + `licenses`): collected, seeded, never used.
- **The crew asks questions she cannot answer.** "Confirm the exact height in centimetres"
  renders as a bullet at the approval gate with no input. `dimensions` *is* an askable field but
  `required: false`, so it never enters `missing_attributes` and the voice-answer chips skip it.
- **Only title + description are translated.** Everything she must *act on* stays English: the
  approval bullets, the checklist, **the label text itself**, the compliance/returns cards,
  "high risk / size mismatch". She reads Tamil, then hits an English wall where it matters.
- **Raw enum keys leak to her** — the UI shows `Licence needed: BIS_ISI_certification`.

### 🟡 Input / photo cases
- Price **in words** ("do sau rupaye") — `_extract_rupees` is digits-only → falls to clarify (graceful).
- **Multiple products in one voice note** — the pipeline assumes one product.
- Price ranges; silence/noise-only audio; very long notes.
- **HEIC (iPhone) photos fail** — PIL can't open without `pillow-heif` → 400.
- **EXIF rotation ignored** → sideways photos stay sideways.
- Multiple products in one photo; screenshots; very large images.

### 🟡 Resilience / scale
- **Mongo down → everything fails** (checkpointer needs it). No degraded mode.
- Race if two sellers upload the same photo simultaneously.
- pHash is an **O(n) linear scan** — fine at prototype scale; needs bucketing/LSH later.

### ⬜ Not built
- **Zero tests** (verified — every `test_*.py` is inside `.venv`).
- Reverse-image search (stock photos never seen before still pass).
- Public browse page — the 10 seeded listings are invisible in the app.
- **Real marketplace publishing** — `published` is an internal status only.
- Multi-marketplace formatters; scheduled re-scoring; Bhashini option; seller accounts/auth.

### Deployment notes
- Frontend → **Vercel**. Backend → **Render/Railway/Fly/Cloud Run** (must be a long-running
  service, **not serverless** — a run takes ~15s and would hit function timeouts).
- **SSE buffering** is the big risk: many hosts/proxies buffer, which kills the live agent stream.
- Set `CORS_ORIGINS` to the real domain in prod.
- **S3 is NOT required** — GridFS lives *inside Mongo*, so images are already shared across
  instances. (An earlier doc wrongly listed S3 as a blocker; it's only a cost/CDN optimisation.)

---

## 11. Traps that already bit (do not re-learn these the hard way)

1. **System Python vs `.venv`** — the app runs on **`C:\Python313`** where LangGraph 1.2.9 is
   installed. The project's `.venv` is **stale and has no langgraph**. A `.vscode/settings.json`
   pointed at `.venv` and caused a false "langgraph isn't installed" conclusion. It's gitignored now.
2. **There were TWO data dirs** — `data/` (read by agents) and `backend/data/` (read by seed) had
   **different content** (6 stale categories vs 13 real). Consolidated to **repo-root `data/`**.
   Do not reintroduce a second copy.
3. **Stale category keys** — `food`→`food_packaged`, `cosmetics_soap`→`cosmetics_handmade`,
   `apparel`→`apparel_readymade`. Canonical keys live in `data/compliance_rules.json`.
4. **A live `PIL.Image` cannot be checkpointed** → graph state holds a GridFS `image_ref` string;
   `suno_node` loads the image. Never put the image object in state.
5. **SSE stream chunks** can be `None` or the `__interrupt__` key → the stream loop must guard
   `isinstance(delta, dict)` (this crashed once).
6. **CORS** — dev allows any localhost via regex (the frontend runs on 3001, API on 8000).
   Port 3001 previously 500'd when a non-ObjectId `seller_id` was passed → `_oid_or_none` guards it.
7. **Windows console can't print ₹ or emoji** (cp1252) → use `PYTHONIOENCODING=utf-8`.
8. **`.docx` files lock** (EBUSY) when open in Word — close before regenerating.
9. **Report/script generation** lives in the scratchpad (`make_doc.js`, `make_script.js`) using
   the npm `docx` package; verify by exporting to PDF via Word COM (no LibreOffice/poppler here).
10. **The in-app screenshotter hangs** on the landing page's infinite `pulse-ring` animation.
    Not a bug — verify via DOM instead.
11. **Mermaid `linkStyle` indices shift** whenever you add an edge; and `*/` inside a JSDoc
    comment (e.g. `w-*/h-*`) silently terminates the comment and breaks the build.
12. **Motor binds to the first event loop** — a bare `TestClient(app)` opens a new loop per
    request, so the *second* DB-touching request dies with `RuntimeError: Event loop is closed`.
    Use `with TestClient(app) as c:` (one loop for the block). This will bite on the Tier 3
    API tests immediately.
13. **`product_attributes` is keyed by `key` (`age_group`); `missing_attributes` holds LABELS
    (`"Age Group"`)** — enough to show her, not enough to fill anything. `suno.askable_fields()`
    maps back to the key + enum options. The two must always be written **together**: merging an
    attribute without recomputing `suno.missing_for()` published a listing that still asked her
    for a detail she had just given (fixed in `approval_node` and the approve route).
14. **The frontend's React Compiler lint rejects a synchronous `setState` in a `useEffect` body**
    (`react-hooks/set-state-in-effect`) — `npx tsc --noEmit` passes and it still fails lint.
    Put the work in an async callback inside the effect. Note `next lint` is gone in Next 16;
    run `npx eslint src --ext .ts,.tsx`.

---

## 12. Deliverables produced

| File | What |
|---|---|
| `README.md` | rewritten, accurate, with honesty notes |
| `docs/ARCHITECTURE.md` | HLD, state machine, ER schemas, sequence, per-agent detail (Mermaid) |
| `docs/hld-diagram.png`, `docs/agent-flow-diagram.png` | clean non-overlapping diagrams (matplotlib) |
| `Aarambhini_Report.docx` | 5-page status report for the mentor |
| `Aarambhini_Meeting_Script.docx` | 6-page word-for-word speaking script + Q&A prep |
| `HANDOVER.md` | this file |

---

## 13. Working agreements / tone

- **Individual project → always "I", never "we".** (The mentor Slack intro says *"I've built…"*.)
- **Be humble but not apologetic** — state what was built plainly, volunteer the gaps, invite correction.
- **Honesty over polish.** The project's credibility rests on saying what is *not* built
  (AI-detection, reverse-image search, publishing API) rather than implying it is.
  Several docs were corrected precisely because they overclaimed (e.g. Wapsi's docstring once
  said it "learns over time" when it did not — that's now true, but only after being built).
- **Verify, don't assume.** A stale FSSAI threshold (₹12 lakh → ₹1.5 crore, Apr 2026) was caught
  only by checking current law instead of trusting the model's memory.

---

## 14. Suggested next steps (in order)

1. **Fix the 3 red items** — ~~auth/ownership on `/approve`~~ **(done — see §8)**. Still open:
   licence-blocking (decided: explicit seller acknowledgement at the approval interrupt,
   recorded in the audit log — *not built yet*), and a category-confidence check so food can't
   silently skip FSSAI. **The category one is the highest-risk thing left in the project.**
2. **Tests, Tier 1 + 2** — pure functions (Daam maths, `_extract_rupees`, pHash/Hamming,
   Wapsi learning, `_blocking_gaps`), then **the graph with a stubbed `llm_json`** to assert the
   loops actually fire. That tests the real differentiator.
3. **Deploy** — Vercel + a long-running backend; verify SSE isn't buffered.
4. Then: HEIC/EXIF handling, a "buyer's-eye preview" (not a storefront), reverse-image search.
