# SecOps Memory — Backend (Phase 1–3)

What exists so far: FastAPI app, config, and a working `HindsightService`
wrapper around the real `hindsight-client` SDK, plus the smoke test that
proves retain → recall actually round-trips. No LLM, no incident agent,
no frontend yet — that's Phase 4+.

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

- **Hindsight Cloud** (recommended for the hackathon — zero infra):
  set `HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io` and
  `HINDSIGHT_API_KEY=<your key>`. Apply promo code `MEMHACK99` in the
  billing section after registering for $50 in free credits.
- **Local Docker** instead:
  ```bash
  export OPENAI_API_KEY=sk-xxx
  docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
    -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
    -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
    ghcr.io/vectorize-io/hindsight:latest
  ```
  then set `HINDSIGHT_BASE_URL=http://localhost:8888` and leave
  `HINDSIGHT_API_KEY` blank.

## Phase 3 checkpoint — run this first

```bash
pytest tests/test_hindsight_smoke.py -v -s
```

This retains one synthetic incident memory, waits for Hindsight's async
processing, then recalls it and asserts it comes back. **Do not build
anything past this point until it passes.** In my sandbox this fails
cleanly with "Bank creation/connection failed" because I have no network
route to Hindsight's servers and can't run Docker here — that's expected;
run it yourself against your real Hindsight Cloud key or local instance.

## Run the API

```bash
uvicorn app.main:app --reload --port 8001
curl http://localhost:8001/health
```

`hindsight_reachable` in the response tells you immediately whether the
bank connection is live — that's the same check the smoke test uses.
The frontend connects to port `8001` by default. If you run the API on a
different port, set `NEXT_PUBLIC_API_URL` in the frontend environment to the
matching API URL before starting Next.js.

## What's next (Phase 4+, not built yet)

- `services/llm_client.py` — Groq wrapper
- `services/incident_agent.py` — the analyze → recall → generate → retain
  orchestration from the architecture diagram
- `routers/incidents.py` — `POST /incidents`, `POST /incidents/{id}/resolve`
- Frontend (Next.js)

## New in v0.4

- `POST /incidents/analyze` now returns a unique `incident_id`, severity + category, similar-incident count, estimated time to resolve, per-memory scores/tags, and supports `concise: true` (3-bullet summary mode).
- `POST /incidents/{id}/resolve` accepts optional `resolution_minutes`.
- `GET /incidents/history`, `GET /memory/timeline`, `GET /stats` power the dashboard (`/dashboard` in the frontend).
- `POST /demo/seed` (or `python seed_data.py`) pre-loads Hindsight with 6 synthetic incidents.
- History/analytics are stored in `backend/data/incidents.json`; Hindsight remains the source of truth for memory.

## Vigil trust-gated memory

- Resolved analyst experiences are tagged `trust:analyst-confirmed` and
  `source:analyst-resolution`. Protected recall requests that trust tag and
  independently rejects any returned memory without it.
- The ledger recognizes `analyst-confirmed`, `telemetry`, `llm-inferred`,
  and `raw-user-text` trust tags. Model-only inferred memories are not
  admitted to trusted recall; the current write paths are analyst resolution
  and the explicitly untrusted telemetry demo.
- Memory can raise suspicion or suggest investigation, but cannot by itself
  dismiss an alert, lower severity, or allowlist an actor.
- `POST /demo/poisoning` stores the submitted telemetry as a
  `trust:raw-user-text` Hindsight document, then compares a deliberately
  unfiltered baseline with the protected analysis. The protected analysis
  receives only validated username/user-agent indicators and remark metadata;
  the raw remark is not included in its prompt. Model behavior is observed,
  not guaranteed, and the result must not be represented as a measured success
  rate.
- `GET /memory/documents` exposes application memory IDs, source/trust tags,
  and document lengths for provenance. `DELETE /memory/documents/{id}`
  permanently revokes an application-owned Hindsight document. The dashboard
  offers this action in the memory provenance view and on recalled memories.
- Trust gating is enforced in the application as well as requested from
  Hindsight; it does not depend on Hindsight Enterprise Memory Defense.
