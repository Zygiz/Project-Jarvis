"""Background job that sends due reminders."""

import logging
from datetime import datetime

from sqlalchemy import select
from telegram import Bot

from app.config import settings
from app.database import get_session
from app.models import Reminder

logger = logging.getLogger(__name__)


async def send_due_reminders() -> None:
    """Find reminders that are due and unsent, send them, mark them sent.

    Runs every minute. The database is the source of truth, so a container
    restart never loses or double-sends a reminder.
    """
    now = datetime.utcnow()

    with get_session() as session:
        stmt = select(Reminder).where(
            Reminder.due_at <= now,
            Reminder.sent.is_(False),
        )
        due = session.execute(stmt).scalars().all()
        # Read the values out while the session is open.
        payloads = [(r.id, r.recipient, r.task) for r in due]

    if not payloads:
        return

    bot = Bot(token=settings.telegram_bot_token)

    for reminder_id, recipient, task in payloads:
        try:
            await bot.send_message(chat_id=recipient, text=f"Reminder: {task}")
        except Exception:
            logger.exception("Failed to send reminder | id=%s", reminder_id)
            continue  # leave sent=False so it retries next tick

        with get_session() as session:
            stored = session.get(Reminder, reminder_id)
            if stored is not None:
                stored.sent = True

        logger.info("Reminder sent | id=%s | recipient=%s", reminder_id, recipient)