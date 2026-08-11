import logging

from sqlalchemy import select

from app.database import get_session
from app.llm import get_llm
from app.models import Message

from app.intent_parser import parse_intent
from app.intents import CreateReminderIntent

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
        reply = (
            f"Got it — reminder for '{intent.task}' at '{intent.when}'. "
            "(Not actually saved yet — storage comes next.)"
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