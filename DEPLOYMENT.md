# Running SAHYOG as containers

Everything - 9 backend services, the citizen-portal frontend, Postgres,
MinIO, and Ollama - builds and runs with Docker Compose from the repo root.

## First run

```bash
cp .env.example .env
# edit .env: at minimum set real values for INTERNAL_SERVICE_TOKEN,
# ADMIN_PORTAL_PASSWORD, ADMIN_FORM_PASSWORD, AGENT1_WEBHOOK_SECRET.
# Bhashini credentials can stay blank (translation runs passthrough).

docker compose up --build
```

First start pulls the `llama3.2:3b` and `llava` Ollama models (a few GB) via
the one-shot `ollama-pull` service before Agent 2 starts - this can take a
while depending on your connection. Postgres provisions its full schema
automatically on first start (see `3.Triage and route/Dockerfile.postgres`).

## What's where

| Service | Port | Notes |
|---|---|---|
| citizen-portal | 3000 | the frontend |
| orchestrator | 8005 | BFF the frontend and legacy static pages talk to |
| agent1 (Language Normalizer) | 8001 | |
| agent2 (Evidence Extractor) | 8002 | needs `ollama` healthy first |
| agent3 (Triage & Route) | 8003 | |
| agent5 (ULB Dispatch) | 8004 | |
| agent6 (Track B Innovation) | 8006 | |
| agent7 (Industry Partnership) | 8007 | |
| agent8 (Lifecycle Outcome) | 8008 | |
| agent9 (Transparency Layer) | 8009 | |
| postgres | 5432 | PostGIS + pgvector |
| minio | 9000 (API), 9001 (console) | object storage |
| ollama | 11434 | local LLM/vision models |

## Known limits of this setup

- **`NEXT_PUBLIC_*` frontend URLs are baked in at build time.** Changing
  them in `.env` requires `docker compose build citizen-portal` again, not
  just a restart - this is a Next.js constraint, not a bug.
- **No reverse proxy.** The frontend calls several backend origins directly
  from the browser (Orchestrator, Agent 1/2/3/9), same architecture as the
  non-Docker dev setup. Deploying behind a real domain means every one of
  those `NEXT_PUBLIC_*`/`FRONTEND_ORIGINS` values needs to point at that
  domain's real, publicly reachable addresses.
- **No TLS, no secrets vault, no horizontal scaling.** This makes the stack
  buildable and runnable as containers with environment-based config - it
  does not add the rest of what a production SRE setup would include.

## Running outside Docker

`start_pipeline.py` still works exactly as before, reading each service's
own `.env` file - the Docker path is additive, not a replacement.
