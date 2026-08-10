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
    ) -> str:
        contents = []

        for turn in history or []:
            role = _ROLE_MAP.get(turn["role"], "user")
            contents.append(
                types.Content(role=role, parts=[types.Part(text=turn["text"])])
            )

        contents.append(
            types.Content(role="user", parts=[types.Part(text=prompt)])
        )

        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        logger.info(
            "LLM call complete | model=%s | turns=%s", self._model, len(contents)
        )
        return response.text