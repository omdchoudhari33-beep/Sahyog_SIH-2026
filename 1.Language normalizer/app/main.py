from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.webhook import router

app = FastAPI(title=settings.app_name)
# Lets the citizen-portal Next.js app call this service straight from the
# browser. Origins come from FRONTEND_ORIGINS (comma-separated, defaults to
# the local dev server) so a real deployment can point this at the real
# frontend domain instead of only ever working for localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
