import logging

from fastapi import FastAPI

from app.config import settings
from app.logging_config import setup_logging

# Configure logging BEFORE anything else, so all later logs are formatted.
setup_logging()

# Each module gets its own logger named after itself (app.main).
# That's the "%(name)s" field in the log format — it tells you who logged what.
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

logger.info("Jarvis starting up | environment=%s", settings.environment)


@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}