import logging

from app.database import get_session
from app.models import Message

logger = logging.getLogger(__name__)


def save_message(text: str, sender: str) -> None:
    """Store an incoming message."""
    with get_session() as session:
        session.add(Message(text=text, sender=sender))


def handle_message(text: str, sender: str) -> str:
    """Process an incoming message and return Jarvis's reply.

    Knows nothing about Telegram — any interface can call this.
    In Week 4 the echo below becomes an LLM call.
    """
    save_message(text=text, sender=sender)
    return f"You said: {text}"