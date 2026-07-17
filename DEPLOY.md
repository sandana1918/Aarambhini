# Deploying Aarambhini

Two pieces: the **API** (a long-running container) and the **web app** (Vercel).
Mongo is already Atlas, and photos live in GridFS *inside* Mongo — there is no
S3 or volume to provision.

> **The backend must NOT be serverless.** One listing takes ~15s across six
> agents and three loops, and the SSE stream stays open the whole time. A
> typical function timeout cuts that off mid-run.

---

## 1. Before you deploy — two things that will fail closed

**`SESSION_SECRET` is mandatory outside dev.** `backend/auth.py` raises rather
than issue a forgeable token, so the API will refuse every login without it.
Generate one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Do not seed the demo sellers into production.** All seven share the password
`aarambhini-demo`, which is public in this repo. `python -m backend.seed` is
safe (reference data + demo sellers — skip it in prod); `seed_demo` is
demo-only. For a real deployment, seed **reference data only** and register real
sellers through `/register`.

---

## 2. API → Render (Railway / Fly / Cloud Run are equivalent)

`render.yaml` is a blueprint: New → Blueprint → point at this repo.

The Docker build context is the **repo root**, not `backend/` — `backend/main.py`
imports `orchestrator`, `llm` and `graph_store` from the root, and the agents
read `data/compliance_rules.json` at runtime.

Set these by hand (they're `sync: false`, never committed):

| Key | Value |
|---|---|
| `MONGODB_URI` | your Atlas string |
| `GEMINI_API_KEY` | |
| `SARVAM_API_KEY` | STT + translate + TTS, one key |
| `SESSION_SECRET` | the generated string above |
| `CORS_ORIGINS` | your exact Vercel origin, e.g. `https://aarambhini.vercel.app` |

Everything else has a default in `render.yaml`.

> **`CORS_ORIGINS` blank does not mean "allow all".** It falls back to a
> localhost-only regex, so your deployed site would be refused by its own API.
> Set it to the real origin, with no trailing slash.

Check `GET /health` → `{"status":"ok","db":"connected"}`.

## 3. Web → Vercel

Import the repo, then:

- **Root Directory: `frontend`** — the repo root is the Python API.
- **Environment variable:** `NEXT_PUBLIC_API_URL` = your API's URL
  (e.g. `https://aarambhini-api.onrender.com`, no trailing slash).

`NEXT_PUBLIC_*` is inlined at **build** time, so changing it needs a redeploy,
not just a restart.

Framework, build command and output are auto-detected (Next.js 16, Turbopack).

## 4. After the first deploy — verify, don't assume

```bash
API=https://<your-api>
curl -s $API/health                       # {"status":"ok","db":"connected"}
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST $API/listings/000000000000000000000000/approve \
  -H 'Content-Type: application/json' -d '{"approved":true}'   # expect 401
```

**Then check SSE is not buffered** — this is the one that silently ruins the
demo. Many proxies hold the response until it closes, which turns the live agent
timeline into a 15-second freeze and then everything at once. The API already
sends `X-Accel-Buffering: no`, but verify on the real host:

```bash
curl -N -H "Authorization: Bearer <token>" \
  -F "voice_text=I make handmade jute bags, 40 pieces, cost 200 rupees each" \
  -F "photo=@some-photo.jpg" \
  $API/listings/run/stream
```

Events must arrive **one at a time over ~15s**. If they all land at the end,
the host is buffering — that's a host setting, not a code bug.

## 5. Known operational limits

- **Login throttling is in-memory and per-process.** The container runs one
  worker on purpose; scale past one and the 5-attempt lockout silently
  weakens. Move it to Mongo/Redis before scaling.
- **Free tiers sleep.** A cold start plus a 15s run makes a poor first
  impression for a judge — hit `/health` to warm it first.
- **No password reset.** A seller who forgets hers needs a database edit.
- **Mongo down = everything down.** The LangGraph checkpointer needs it; there
  is no degraded mode.
