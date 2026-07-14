# Aarambhini 🪡

An **agentic AI co-founder for rural women sellers**. A seller speaks one voice
note in her own language and uploads one phone photo; a crew of AI agents turns it
into a complete, returns-proofed, compliance-checked, marketplace-ready listing —
and visibly **checks and re-does each other's work** before pausing for her approval.

Built for **ScriptedBy{Her} 2.0** (Prototype round).

## The crew

| Agent | Role |
|-------|------|
| **Mukhiya** | Orchestrator — runs the crew and the loops |
| **Suno** | Ear — voice + photo → structured facts; rejects bad photos |
| **Likho** | Pen — writes the listing; appends required labels on demand |
| **Daam** | Pricer — deterministic cost-plus + discount floor |
| **Niyam** | Rulekeeper — the adversary; blocks until labels are applied |
| **Wapsi** | Returns — reasons about likely returns + mitigations |

The **hero moment** is the compliance loop: Niyam rejects Likho and Daam's first
pass, Likho re-runs to append the exact label text, Daam re-prices to absorb the
label overhead, Niyam rechecks — all visible in the Agent Activity Log.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit .env and add your GEMINI_API_KEY
```

`GEMINI_API_KEY` is read from `.env` — never hardcoded. The model must be
multimodal (default `gemini-2.0-flash`) so Suno can read the photo.

## Run

```bash
streamlit run app.py
```

Or exercise pieces standalone (proves nothing is hardcoded):

```bash
python llm.py                 # smoke-test the LLM wrapper
python -m agents.suno         # parse the Hindi jute-bag example
python -m agents.daam         # pure pricing arithmetic (no key needed)
python -m agents.niyam        # rules-based compliance
python orchestrator.py        # full run (needs a photo to pass Suno's gate)
```

> Note: Suno's photo gate rejects runs with no photo, so a text-only
> `python orchestrator.py` returns `needs_retake` by design — use the Streamlit
> app (with a photo) to see the full flow.

## Demo scenarios

- **A · Hero:** jute bags + good photo → compliance loop fires → approve → publish.
- **B · Photo reject:** dark/blurry photo → Suno stops the pipeline.
- **C · Different category:** "terracotta pots, 20 pieces, ₹150 cost" → different
  rules + price. Nothing is hardcoded to jute.
- **D · Food edge:** "homemade mango pickle" → Niyam flags FSSAI + perishable.

## Honesty note

Wapsi **reasons** about likely returns and learns over time — it does **not**
query any real marketplace's return database. The compliance rules in
`data/compliance_rules.json` are accurate at the category level; verify exact
legal text before production.

## Swapping the LLM

Every model call goes through `llm(prompt, image=None)` in `llm.py`. Point that one
function at a different provider (e.g. Azure OpenAI) and the whole crew follows.
