# Aarambhini API.
#
# Build context is the REPO ROOT, not backend/ — backend/main.py imports
# orchestrator, llm and graph_store from the root, and the agents read
# data/compliance_rules.json at runtime. A backend/-only context would build
# an image that imports fine and then 500s on the first run.
#
# Must run as a long-lived service, never serverless: one listing takes ~15s
# (six agents, three loops) and the SSE stream is open for all of it, which is
# well past a typical function timeout.
FROM python:3.13-slim

# Fail fast and log straight through — no buffered stdout hiding a crash.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requirements first, so a code change doesn't reinstall the world.
# Two files, copied separately: a single COPY of both would collide on the
# identical basename.
COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt

COPY . .

EXPOSE 8000

# exec-form + `exec` so uvicorn becomes PID 1's direct child and receives
# SIGTERM on redeploy (a bare shell-form CMD swallows the signal, forcing a
# 10s kill every deploy). `sh -c` is still needed for ${PORT} expansion —
# Render/Railway/Fly assign the port at runtime.
# One worker on purpose: the login throttle in backend/auth.py is in-memory and
# per-process, so a second worker would silently halve the lockout.
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
