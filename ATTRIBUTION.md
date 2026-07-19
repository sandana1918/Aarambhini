# Open-Source Attribution

Aarambhini is built on open-source software. This document lists the significant
libraries and frameworks it leverages, with the version used, the license, the
role each plays in the build, and a link to the original project. Aarambhini
itself is released under the MIT License (see [LICENSE](LICENSE)).

Roles are described as: **direct integration** (imported and called in our code),
**framework** (the app is built on top of it), or **tooling** (used to build,
type-check, or lint, not shipped at runtime).

## Orchestration and AI

| Library | Version | License | Role | Source |
|---|---|---|---|---|
| LangGraph | >=1.0,<2.0 | MIT | Framework. The seven-agent crew is a LangGraph `StateGraph` with a MongoDB checkpointer, three self-correcting loops, and two `interrupt()` pauses. | https://github.com/langchain-ai/langgraph |
| langgraph-checkpoint-mongodb | >=0.1.0 | MIT | Direct integration. Durable checkpointing of graph state to MongoDB Atlas so a run survives a restart. | https://github.com/langchain-ai/langgraph |
| google-genai | >=1.0.0 | Apache-2.0 | Direct integration. The Google Gemini SDK, used for agent reasoning and photo (vision) reading. | https://github.com/googleapis/python-genai |

## Backend (Python / FastAPI)

| Library | Version | License | Role | Source |
|---|---|---|---|---|
| FastAPI | >=0.110 | MIT | Framework. The HTTP API layer, routing, and request validation. | https://github.com/fastapi/fastapi |
| Uvicorn | >=0.29 | BSD-3-Clause | Direct integration. The ASGI server that runs the API. | https://github.com/encode/uvicorn |
| Pydantic | >=2.6 | MIT | Direct integration. Typed request/response schemas. | https://github.com/pydantic/pydantic |
| Motor | >=3.4 | Apache-2.0 | Direct integration. Async MongoDB driver for the web layer. | https://github.com/mongodb/motor |
| PyMongo | >=4.6 | Apache-2.0 | Direct integration. Sync MongoDB client for the LangGraph checkpointer and GridFS image storage. | https://github.com/mongodb/mongo-python-driver |
| python-multipart | >=0.0.9 | Apache-2.0 | Direct integration. Parses multipart form uploads (voice note, photo). | https://github.com/Kludex/python-multipart |
| certifi | >=2024.0 | MPL-2.0 | Direct integration. CA bundle for MongoDB Atlas TLS. | https://github.com/certifi/python-certifi |

## Data, media, and utilities

| Library | Version | License | Role | Source |
|---|---|---|---|---|
| pandas | >=2.0 | BSD-3-Clause | Direct integration. Reads the price-benchmark and packaging reference data for the deterministic pricing and packing agents. | https://github.com/pandas-dev/pandas |
| Pillow | >=10.0 | HPND (MIT-style) | Direct integration. Reads product photos and computes the perceptual hash for stolen-photo detection. | https://github.com/python-pillow/Pillow |
| requests | >=2.31 | Apache-2.0 | Direct integration. HTTP client for the Sarvam AI (speech/translate/TTS) and Shopify Admin APIs. | https://github.com/psf/requests |
| python-dotenv | >=1.0 | BSD-3-Clause | Direct integration. Loads environment configuration from `.env`. | https://github.com/theskumar/python-dotenv |
| qrcode | >=7.4 | BSD | Direct integration. Builds the optional provenance / trust QR for a listing. | https://github.com/lincolnloop/python-qrcode |
| Streamlit | >=1.36 | Apache-2.0 | Framework. Powers the legacy single-file `app.py` UI (secondary to the Next.js frontend). | https://github.com/streamlit/streamlit |

## Frontend (Next.js / React)

| Library | Version | License | Role | Source |
|---|---|---|---|---|
| Next.js | 16.2.10 | MIT | Framework. The web application (App Router, SSR, the three-step sell flow). | https://github.com/vercel/next.js |
| React | 19.2.4 | MIT | Framework. The UI component model. | https://github.com/facebook/react |
| React DOM | 19.2.4 | MIT | Direct integration. React's DOM renderer. | https://github.com/facebook/react |
| Tailwind CSS | ^4 | MIT | Framework. Utility-first styling across the UI. | https://github.com/tailwindlabs/tailwindcss |
| TypeScript | ^5 | Apache-2.0 | Tooling. Static typing for the frontend. | https://github.com/microsoft/TypeScript |
| ESLint + eslint-config-next | ^9 / 16.2.10 | MIT | Tooling. Linting. | https://github.com/eslint/eslint |

## Testing

| Library | Version | License | Role | Source |
|---|---|---|---|---|
| pytest | >=8.0 | MIT | Tooling. The 65-test suite (Tier 1 pure functions, Tier 2 real-graph runs). Not shipped in the Docker image. | https://github.com/pytest-dev/pytest |
| pytest-asyncio | >=0.24 | Apache-2.0 | Tooling. Async test support. | https://github.com/pytest-dev/pytest-asyncio |

## Hosted services and APIs (not open source, leveraged via API)

These are third-party platforms and APIs the project calls. They are not
open-source dependencies, listed here for full transparency.

| Service | Role |
|---|---|
| Google Gemini API | Multimodal reasoning and vision for the LLM agents. |
| Sarvam AI (Saarika, Mayura, Bulbul) | Indian-language speech-to-text, translation, and text-to-speech. |
| MongoDB Atlas | Managed database (listings, checkpoints, GridFS images). |
| Shopify Admin API | Optional push of an approved listing to a real storefront. |
| Render | Backend (Docker) hosting. |
| Vercel | Frontend hosting. |

Versions reflect the constraints in `requirements.txt`, `backend/requirements.txt`,
`requirements-dev.txt`, and `frontend/package.json`. Licenses are the projects'
own as of this writing; refer to each source link for the authoritative text.
