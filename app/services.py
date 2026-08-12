import logging

from sqlalchemy import select

from app.database import get_session
from app.llm import get_llm
from app.models import Message

from app.intent_parser import parse_intent
from app.intents import CreateReminderIntent

from app.models import Message, Reminder
from app.timeparse import parse_when

from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from app.config import settings

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 10

SYSTEM_PROMPT = """You are Jarvis, a personal assistant for Zygis.

Be concise and direct — replies are read on a phone in Telegram.
Skip pleasantries and filler. Answer in a few sentences unless asked for detail.
If you don't know something, say so plainly."""


def save_message(text: str, sender: str, role: str) -> None:
    """Store a message. role is 'user' or 'assistant'."""
    with get_session() as session:
        session.add(Message(text=text, sender=sender, role=role))


def get_recent_history(sender: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    """Return the last `limit` messages for this sender, oldest first."""
    with get_session() as session:
        stmt = (
            select(Message)
            .where(Message.sender == sender)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = session.execute(stmt).scalars().all()

        # Convert to plain dicts INSIDE the session. Once it closes the ORM
        # objects are detached and reading their attributes raises
        # DetachedInstanceError.
        history = [{"role": r.role, "text": r.text} for r in reversed(rows)]

    return history


def handle_message(text: str, sender: str) -> str:
    """Process an incoming message and return Jarvis's reply."""
    history = get_recent_history(sender)
    save_message(text=text, sender=sender, role="user")

    intent = parse_intent(text)

    if isinstance(intent, CreateReminderIntent):
        reply = create_reminder(
            task=intent.task, when=intent.when, recipient=sender
        )
        save_message(text=reply, sender=sender, role="assistant")
        return reply

    try:
        reply = get_llm().complete(prompt=text, system=SYSTEM_PROMPT, history=history)
    except Exception:
        logger.exception("LLM call failed | sender=%s", sender)
        return "Sorry, I couldn't reach my brain just then. Try again?"

    save_message(text=reply, sender=sender, role="assistant")
    logger.info("LLM reply generated | sender=%s | history=%s", sender, len(history))
    return reply


def create_reminder(task: str, when: str, recipient: str) -> str:
    """Validate the time phrase and store a reminder. Returns a user-facing reply."""
    due_at = parse_when(when)

    if due_at is None:
        return (
            f"I understood the task ('{task}') but not the timing ('{when}'). "
            "Try something like 'tomorrow at 09:00' or 'Friday 14:00'."
        )

    with get_session() as session:
        session.add(Reminder(task=task, recipient=recipient, due_at=due_at))

    local = due_at.replace(tzinfo=dt_timezone.utc).astimezone(
        ZoneInfo(settings.timezone)
    )
    logger.info("Reminder created | recipient=%s | due_at=%s", recipient, due_at)
    return f"Reminder set: {task} — {local.strftime('%a %d %b at %H:%M')}"
