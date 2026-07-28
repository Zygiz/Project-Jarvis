#where the FastAPI app will live
from fastapi import FastAPI

from app.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}