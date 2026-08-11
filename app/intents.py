"""Structured intents the LLM may request.

The LLM never acts directly — it returns one of these shapes, which the
application validates before deciding whether to execute anything.
Anything that fails validation is rejected, not guessed at.
"""

from typing import Literal, Union

from pydantic import BaseModel, Field


class ChatIntent(BaseModel):
    """No action needed — just answer the user conversationally."""

    action: Literal["chat"]


class CreateReminderIntent(BaseModel):
    """The user wants a reminder created."""

    action: Literal["create_reminder"]
    task: str = Field(min_length=1, max_length=500)
    when: str = Field(
        min_length=1,
        description="The time expression exactly as the user phrased it, "
        "e.g. 'next Friday', 'tomorrow at 14:00'.",
    )


Intent = Union[ChatIntent, CreateReminderIntent]