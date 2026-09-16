# Audio Agent MVP

## Run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Current scope

- Health endpoint
- Signed text webhook
- Basic phone/Aadhaar scrubbing
- Placeholder normalization and translation
- Audio, ASR, human review, mTLS, queue, and deletion are next phases
