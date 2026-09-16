# SAHYOG Pipeline

Four services, one pipeline: a citizen speaks or types a report, uploads a
photo, and gets a real spoken back-and-forth confirming what the system
understood - before a ticket is ever raised. See
`4.Orchestrator/README.md` for the full conversational flow diagram,
voice-agent details (what's real speech-to-speech vs. text), and API
reference.

**Voice coverage, stated plainly**: Hindi, Bengali, Odia, Urdu, Nepali,
Maithili, and English are fully supported (speech-to-text, translation,
and spoken replies). Mundari, Kurukh, Kharia, and Khortha are not
supported by Bhashini or any other mainstream speech AI - see
`4.Orchestrator/README.md`'s "Voice agent" section for why, and what the
right fix looks like (human transcription, not a workaround).

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

**Bring up Ollama and Postgres** (see `4.Orchestrator/README.md` section 0
for the exact Docker commands and model pulls).

**Start everything:**

```powershell
python start_pipeline.py
```

This starts all four services and streams their combined output - tagged
by service name, timestamped - into one file: `logs/sahyog.log`. Press
Ctrl+C to stop everything cleanly.

Then open:
- `http://127.0.0.1:8005/` - citizen report wizard (voice or text, photo,
  location, with every step confirmed back before submission)
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
