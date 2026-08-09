import logging

from app.database import get_session
from app.llm import get_llm
from app.models import Message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Jarvis, a personal assistant for Zygis.

Be concise and direct — replies are read on a phone in Telegram.
Skip pleasantries and filler. Answer in a few sentences unless asked for detail.
If you don't know something, say so plainly."""


def save_message(text: str, sender: str) -> None:
    """Store an incoming message."""
    with get_session() as session:
        session.add(Message(text=text, sender=sender))


def handle_message(text: str, sender: str) -> str:
    """Process an incoming message and return Jarvis's reply.

    Knows nothing about Telegram — any interface can call this.
    """
    save_message(text=text, sender=sender)

    try:
        llm = get_llm()
        reply = llm.complete(prompt=text, system=SYSTEM_PROMPT)
        logger.info("LLM reply generated | sender=%s", sender)
        return reply
    except Exception:
        logger.exception("LLM call failed | sender=%s", sender)
        return "Sorry, I couldn't reach my brain just then. Try again?"