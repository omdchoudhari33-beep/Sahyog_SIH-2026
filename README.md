# SAHYOG Pipeline

Four services, one pipeline: a citizen speaks or types a report, uploads a
photo, and gets a real spoken back-and-forth confirming what the system
understood - before a ticket is ever raised. See
`4.Orchestrator/README.md` for the full conversational flow diagram,
voice-agent details (what's real speech-to-speech vs. text), and API
reference.

**Voice coverage, stated plainly** (individually verified per language via
Bhashini's own model-discovery endpoint, not assumed from one shared model
family label): Hindi, Bengali, Odia, and English get full speech-to-text +
translation + spoken replies. **Urdu gets speech-to-text and translation,
but not spoken replies** - Bhashini's TTS task genuinely isn't provisioned
for Urdu on this pipeline (confirmed via the discovery endpoint returning
"No supported tasks found", not a bug in this code); Urdu voice input still
works normally, it just can't talk back yet. Nepali and Maithili currently
have translation only (no speech-to-text or spoken replies, same "not
provisioned on this pipeline" reason) and aren't offered as voice options
in the UI. **Santali has no Bhashini model of any kind**, but is not
text-only any more: `1.Language normalizer/app/services/santali_local.py`
routes it to self-hosted open models instead (Meta's MMS for speech-to-
text, NLLB-200 for translation, AI4Bharat's Indic Parler-TTS for spoken
replies), run by `santali-voice-service/` - the one piece of this stack
that runs in Docker even though every pipeline agent runs natively (its
ML dependencies wouldn't load on this Windows install; see that service's
own README/comments). Mundari, Kurukh, Kharia, and Khortha remain
unsupported by Bhashini, MMS, NLLB, or any other mainstream speech/
translation model identified so far - see `4.Orchestrator/README.md`'s
"Voice agent" section for why, and what the right fix looks like (human
transcription, not a workaround).

## Quickstart

**One-time setup per service** (each has its own venv/deps):

```powershell
foreach ($dir in "1.Language normalizer", "2.Evidence Extractor", "3.Triage and route", "4.Orchestrator") {
  cd $dir
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  cd ..
}
copy "1.Language normalizer\.env.example" "1.Language normalizer\.env"   # then add your Bhashini credentials
copy "4.Orchestrator\.env.example" "4.Orchestrator\.env"
```

**Bring up Ollama, Postgres, and object storage** (see
`4.Orchestrator/README.md` section 0 for the exact Docker commands and
model pulls; see `DATABASE.md` for the full schema and object storage
architecture).

**Start everything:**

```powershell
python start_pipeline.py
```

This starts all four services and streams their combined output - tagged
by service name, timestamped - into one file: `logs/sahyog.log`. Press
Ctrl+C to stop everything cleanly.

Then open:
- `citizen-portal` (separate Next.js app - see its own README) - the
  citizen report wizard (voice or text, photo, location, with every step
  confirmed back before submission)
- `http://127.0.0.1:8005/dashboard` - operator queue

If a service's venv isn't set up yet, the script prints a warning and
skips it rather than failing the others - run the setup step above for
whichever one it names.

On a corporate network with a TLS-inspecting proxy (e.g. Zscaler), see
`4.Orchestrator/README.md` section 0 if you hit `CERTIFICATE_VERIFY_FAILED`
errors during setup or at runtime.

## Watching logs live

```powershell
Get-Content logs\sahyog.log -Wait -Tail 50
```

or filter to one service:

```powershell
Get-Content logs\sahyog.log -Wait | Select-String "agent2"
```
