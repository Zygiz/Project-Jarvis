import logging

from google import genai
from google.genai import types

from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, system: str | None = None) -> str:
        config = (
            types.GenerateContentConfig(system_instruction=system) if system else None
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )

        logger.info("LLM call complete | model=%s", self._model)
        return response.text