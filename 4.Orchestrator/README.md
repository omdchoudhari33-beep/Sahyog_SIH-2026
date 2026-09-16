# Sahyog Pipeline Orchestrator

Chains the three stage services into a conversational citizen-report flow,
with a real spoken back-and-forth, not just voice-in/text-out:

```
POST /conversation/describe
    │  (voice or text; Agent 1 does ASR + Bhashini translate)
    ▼
Agent 2 classifies the report (domain, severity, suggested track)
    │
    ▼
"Here's what I understood: X. Is this correct?"  ◄── spoken back via Bhashini TTS
    │
    ▼  citizen confirms or corrects the text
POST /conversation/{id}/confirm
    │
    ▼
"Now please take or upload a photo of the spot."
    │
    ▼  citizen uploads a photo
POST /conversation/{id}/photo
    │  Agent 2's vision model checks the photo against the CONFIRMED text -
    │  a mismatch is reported back, not silently accepted
    ▼
No GPS in the photo? → ask for location (device GPS, or a typed place name
    │                    geocoded via OpenStreetMap, shown back to verify)
    ▼
POST /conversation/{id}/location   (only if needed)
    │
    ▼
"Ready to submit - please confirm." → citizen confirms
    │
    ▼
POST /conversation/{id}/finalize  →  Agent 3: dedup, priority, track suggestion
```

This is deliberately a validation loop, not a fire-and-forget submission -
"AI assisting, not deciding": the citizen confirms what the AI understood
at each step before a ticket is raised.

A simpler one-shot `POST /submit` (no back-and-forth, all-or-nothing) still
exists too - see "One-shot alternative" below.

**To run everything, see the root `README.md`** - `python start_pipeline.py`
starts all four services with one combined, timestamped log file
(`logs/sahyog.log`) instead of four separate terminal windows.

## UI

The orchestrator serves the frontend directly - no separate build/dev
server needed:

- `http://127.0.0.1:8005/` - citizen report wizard (voice recording or
  typed text, photo upload, location sharing or typed place name). Every
  system prompt is shown as text **and** spoken aloud via Bhashini TTS in
  whichever language the citizen picked.
- `http://127.0.0.1:8005/dashboard` - operator queue (Track A / Track B /
  Reject-Merge), proxied through the orchestrator so the browser never
  talks to Agent 3 directly.

## Voice agent: what's actually voice-to-voice, and what isn't

- **Speech-to-text**: `faster-whisper`, running fully locally (no API,
  no cost). Auto-detects the spoken language.
- **Translation** (native-script source language → English, and English →
  native script for spoken replies): Bhashini's NMT pipeline
  (`ai4bharat/indictrans-v2-all-gpu--t4`).
- **Text-to-speech**: Bhashini TTS (`ai4bharat/indic-tts-coqui-*`).
- **Bhashini auth note**: this deployment's key authenticates with a
  single `Authorization: <inference key>` header, not the `userID` +
  `ulcaApiKey` header pair shown in Bhashini's public sample code - that
  pair scheme was tried first and rejected by the server. Found by testing
  directly against the API, not from documentation. The discovery endpoint
  (`getModelsPipeline`) also degrades under repeated use (returns a
  response missing `pipelineInferenceAPIEndPoint`) - `bhashini.py` calls
  the inference endpoint directly with hardcoded, individually-verified
  service IDs instead of discovering them per request.
- **Language coverage - verified by testing, not assumed**: Hindi,
  Bengali, Odia, Urdu, Nepali, Maithili, and English work (ASR via
  faster-whisper is broader; Bhashini translation/TTS is limited to this
  list). **Mundari, Kurukh, Kharia, and Khortha are not supported by
  Bhashini at all** (confirmed via the discovery endpoint returning
  "sourceLanguage is not supported") - these are outside Bhashini's
  scope (India's 22 constitutionally scheduled languages), not a bug or
  a missing API key. No mainstream speech AI (Whisper, Google, Azure)
  covers them either - there's essentially no digital speech corpus for
  them. Reports in these languages need a human-transcription path, which
  is not yet built (see Known limitations).
- Speech is always a best-effort overlay: if Bhashini can't handle the
  language, or is unreachable, the text-only conversation still works -
  nothing about the pipeline depends on speech succeeding.

## 0. Bring up Ollama and Postgres (Docker)

Agent 2's vision/text models and Agent 3's database aren't running yet.
From any terminal:

```powershell
# Ollama (local LLMs - all image/text processing stays in-house)
docker run -d --name ollama -p 11434:11434 -v ollama:/root/.ollama ollama/ollama
docker exec ollama ollama pull llama3.2:3b
docker exec ollama ollama pull llava

# Postgres with PostGIS + pgvector, for Agent 3
cd "3.Triage and route"
docker compose up -d --build
# wait a few seconds for it to become healthy, then:
psql "postgresql://postgres:postgres@localhost:5432/dno_triage" -f schema.sql
```

Verify both are reachable before starting the agents:

```powershell
curl http://localhost:11434/api/tags
Test-NetConnection -ComputerName 127.0.0.1 -Port 5432
```

If you have an NVIDIA GPU and want Ollama to use it, add `--gpus=all` to
the `docker run` command above (requires the NVIDIA Container Toolkit).
Without it, Ollama still works on CPU, just slower per request - and the
first call after any ~5-minute idle gap pays a model cold-load cost
(tens of seconds to a couple of minutes) on top of that, regardless of
hardware tier, since Ollama unloads idle models by default.

**Corporate network / TLS-inspecting proxy (e.g. Zscaler)**: if `pip
install`, Hugging Face model downloads, or outbound API calls (Bhashini,
Nominatim) fail with `CERTIFICATE_VERIFY_FAILED`, install
`pip-system-certs` in each service's venv - it makes Python trust the
Windows certificate store the same way `curl` already does:
```powershell
.venv\Scripts\pip install pip-system-certs
```

## Run all four services (separate terminals, distinct ports)

```powershell
# Agent 1 - Language Normalizer
cd "1.Language normalizer"
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then edit in your Bhashini credentials
uvicorn app.main:app --port 8001

# Agent 2 - Evidence Extractor (talks to Ollama at localhost:11434)
cd "2.Evidence Extractor"
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --port 8002

# Agent 3 - Triage & Route (talks to Postgres at localhost:5432)
cd "3.Triage and route"
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --port 8003

# Orchestrator + UI
cd "4.Orchestrator"
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --port 8005
```

Then open `http://127.0.0.1:8005/` in a browser.

## Try the conversational flow (without the UI)

```bash
# 1. Describe the problem
curl -X POST http://127.0.0.1:8005/conversation/describe \
  -F "text=There is a big pothole in the middle of the road near the market" \
  -F "source_language=en"
# -> {"session_id": "...", "state": "awaiting_confirmation",
#     "understood_statement": "...", "domain": "ROADS_BRIDGES", ...}

# 2. Confirm (or correct) it
curl -X POST http://127.0.0.1:8005/conversation/<session_id>/confirm \
  -H "Content-Type: application/json" -d '{"confirmed": true}'

# 3. Attach a photo - checked against the confirmed text, not trusted blindly
curl -X POST http://127.0.0.1:8005/conversation/<session_id>/photo \
  -F "image=@pothole.jpg" -F "device_lat=23.3441" -F "device_lon=85.3096"
# add -F "force=true" to proceed anyway if the vision model flags a mismatch

# 4. Only if the photo had no GPS: share a location
curl -X POST http://127.0.0.1:8005/conversation/<session_id>/location \
  -H "Content-Type: application/json" -d '{"latitude": 23.3441, "longitude": 85.3096}'
# or, when GPS isn't available (permission denied, corporate firewall, desktop testing):
curl -X POST http://127.0.0.1:8005/conversation/<session_id>/location \
  -H "Content-Type: application/json" -d '{"address_text": "Ranchi, Jharkhand"}'
# -> geocoded via OpenStreetMap Nominatim; response includes "resolved_place"
#    so you can verify it found the right spot

# 5. Raise the ticket
curl -X POST http://127.0.0.1:8005/conversation/<session_id>/finalize
# -> {"state": "completed", "ticket": {"ticket_id": 42, ...}, "message": "..."}
```

Hear a step spoken aloud directly:

```bash
curl -X POST http://127.0.0.1:8005/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Your report has been recorded", "language": "hi"}' \
  -o reply.wav
```

Then check the operator queue on Agent 3 directly:

```bash
curl http://127.0.0.1:8003/dno/tickets
```

## One-shot alternative: `POST /submit`

Runs the whole pipeline in a single call with no confirmation checkpoints
- useful for scripted testing, not for the citizen-facing UI:

```bash
curl -X POST http://127.0.0.1:8005/submit \
  -F "text=Sadak mein bada gaddha hai school ke paas" \
  -F "source_language=hi" \
  -F "image=@pothole.jpg" \
  -F "device_lat=23.3441" \
  -F "device_lon=85.3096"
```

`status` in the response is one of:
- `routed` - made it through all three stages into the active queue.
- `review_required` - ASR confidence too low; stopped after Agent 1.
- `geo_required` - no EXIF GPS and no device coordinates; stopped after Agent 2.

## Known limitations

- **Mundari, Kurukh, Kharia, and Khortha have no AI speech path at all**
  (see "Voice agent" above) - reports in these languages need a
  human-transcription queue, which isn't built yet. The right design is
  explicit, not a silent failure: detect/ask, skip AI transcription
  entirely, and route the raw audio to a human reviewer.
- Voice notes recorded in the browser are relayed through
  `/api/v1/audio/upload` and `/api/v1/speak` on Agent 1 (no auth on either
  - they trust anything reaching them, fine for a localhost demo, not for
  the public internet). WhatsApp/IVR ingestion still isn't built.
- No auth between services generally - add a gateway in front of the
  orchestrator before exposing this beyond a local demo.
- Conversation sessions are in-memory only (`app/conversation.py`) -
  restarting the orchestrator loses any in-progress conversation. Fine for
  a demo; swap for Redis/a DB before real deployment.
- `population_impact` is a fixed default (`DEFAULT_POPULATION_IMPACT`)
  since no stage currently estimates it.
- Nominatim (the free geocoding fallback) is rate-limited to ~1
  request/second on its public instance - fine for citizen-facing lookups,
  not for bulk geocoding.
