from fastapi import FastAPI
from app.config import settings
from app.api.webhook import router

app = FastAPI(title=settings.app_name)
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
