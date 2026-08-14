import logging

from google import genai
from google.genai import types

from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Gemini calls the AI's turn "model"; our interface calls it "assistant".
# This mapping keeps that quirk inside the provider.
_ROLE_MAP = {"user": "user", "assistant": "model"}


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        history: list[dict] | None = None,
        label: str = "chat",
    ) -> str:
        contents = []

        for turn in history or []:
            role = _ROLE_MAP.get(turn["role"], "user")
            contents.append(
                types.Content(role=role, parts=[types.Part(text=turn["text"])])
            )

        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        # Usage metadata field names change between SDK versions, so read them
        # defensively — a logging line must never break a working API call.
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            logger.info(
                "LLM call | label=%s | model=%s | turns=%s | in=%s | out=%s | total=%s",
                label,
                self._model,
                len(contents),
                getattr(usage, "prompt_token_count", None),
                getattr(usage, "candidates_token_count", None),
                getattr(usage, "total_token_count", None),
            )
        else:
            logger.info(
                "LLM call | label=%s | model=%s | turns=%s | usage=unavailable",
                label,
                self._model,
                len(contents),
            )

        return response.text