"""Convert natural-language time phrases into UTC timestamps."""

import logging
from datetime import datetime, timezone as dt_timezone

import dateparser

from app.config import settings

logger = logging.getLogger(__name__)


def parse_when(phrase: str) -> datetime | None:
    """Parse a phrase like 'Friday 14:00' into a naive UTC datetime."""
    # dateparser fails on "next Friday" but handles "Friday" fine
    # (PREFER_DATES_FROM future already resolves it forward).
    cleaned = phrase.strip()
    if cleaned.lower().startswith("next "):
        cleaned = cleaned[5:]

    parsed = dateparser.parse(
        cleaned,
        settings={
            "TIMEZONE": settings.timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    if parsed is None:
        logger.warning("Could not parse time phrase | phrase=%r", phrase)
        return None

    utc = parsed.astimezone(dt_timezone.utc).replace(tzinfo=None)

    if utc <= datetime.utcnow():
        logger.warning("Time phrase resolved to the past | phrase=%r", phrase)
        return None

    return utc