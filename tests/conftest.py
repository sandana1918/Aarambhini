"""Shared test setup.

Two tiers live in this suite (see HANDOVER.md §14):

* Tier 1 — pure functions. No network, no DB, no model key. These run in
  milliseconds and are where the highest-value regressions were actually
  caught this project: the category fallback that let food publish with no
  FSSAI prompt, the fabricated age_group that drove a wrong safety label, the
  timing leak in login. Bugs like that live in a function, not in the wiring.

* Tier 2 — the graph itself, with every model call forced to fail. Every
  agent has a documented deterministic fallback (HANDOVER.md item 2: "a run
  degrades, never hard-fails") — Tier 2 proves that promise rather than just
  asserting it in a docstring, and proves the three self-correcting loops
  actually iterate, not just that they're wired into the graph.

Env vars below are set BEFORE any project module is imported, because
graph_store.py and llm.py both read them at import time (though neither
connects eagerly — pymongo and the Gemini client are both lazy). Real values
from .env are used if present so a developer's local Atlas connection still
works for tests that want it; a placeholder is set only where nothing is
already configured, so an unconfigured CI runner can still collect and run
the Tier 1 suite without any secret.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

os.environ.setdefault("MONGODB_URI", "mongodb://test-placeholder:27017")
os.environ.setdefault("SESSION_SECRET", "test-secret-not-for-real-use")
os.environ.setdefault("APP_ENV", "dev")

# orchestrator.py builds its LangGraph at IMPORT time (`_GRAPH = build_graph()`),
# and build_graph() asks graph_store.checkpointer() for a MongoDBSaver — whose
# constructor calls create_index() on two collections. That is a real network
# round-trip, which means `import orchestrator` alone would dial Atlas even for
# a test that only wants a pure function like _blocking_gaps. Patched here, at
# conftest module level, so it is in place before ANY test file's top-level
# `import orchestrator` runs (pytest imports every conftest.py in the tree
# before collecting test modules). langgraph's own in-memory MemorySaver keeps
# the graph fully functional — Tier 2's real graph.invoke() calls still work,
# they just checkpoint to memory instead of Atlas.
import graph_store  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

graph_store.checkpointer = lambda: MemorySaver()
