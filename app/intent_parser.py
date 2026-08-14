"""Turn a user message into a validated Intent."""

import json
import logging

from pydantic import ValidationError

from app.intents import ChatIntent, CreateReminderIntent, Intent
from app.llm import get_llm

logger = logging.getLogger(__name__)

INTENT_PROMPT = """You classify the user's message into a structured intent.

Respond with ONLY a JSON object. No markdown, no code fences, no explanation.

Available actions:

1. Creating a reminder:
{"action": "create_reminder", "task": "<what to be reminded of>", "when": "<the time>"}

2. Anything else - questions, conversation, requests you have no action for:
{"action": "chat"}

Rules:
- Only use "create_reminder" if the user clearly wants a reminder at a time.
- For "when", use simple formats a date parser handles:
  "tomorrow at 09:00", "Friday 14:00", "in 2 hours", "25 December 10:00"
- Do NOT use the word "next". Write "Friday 14:00", not "next Friday at 14:00".
- If no time of day is given, just give the day: "Friday", "tomorrow".
- If unsure, use {"action": "chat"}."""

_INTENT_MODELS = {
    "chat": ChatIntent,
    "create_reminder": CreateReminderIntent,
}


def _strip_fences(text: str) -> str:
    """Models often wrap JSON in code fences despite being told not to."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned.strip()


def parse_intent(text: str) -> Intent:
    """Ask the LLM to classify the message, then validate the result.

    Falls back to ChatIntent on any failure. An unparseable or unknown
    intent must never become an action.
    """
    try:
        raw = get_llm().complete(prompt=text, system=INTENT_PROMPT, label="intent")
    except Exception:
        logger.exception("Intent classification call failed")
        return ChatIntent(action="chat")

    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Intent was not valid JSON | raw=%r", raw[:200])
        return ChatIntent(action="chat")

    if not isinstance(data, dict):
        logger.warning("Intent JSON was not an object")
        return ChatIntent(action="chat")

    model = _INTENT_MODELS.get(data.get("action"))
    if model is None:
        logger.warning("Unknown intent action | action=%r", data.get("action"))
        return ChatIntent(action="chat")

    try:
        intent = model.model_validate(data)
    except ValidationError as exc:
        logger.warning("Intent failed validation | %s", exc)
        return ChatIntent(action="chat")

    logger.info("Intent parsed | action=%s", intent.action)
    return intent
