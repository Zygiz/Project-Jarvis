from app.config import settings
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider


def get_llm() -> LLMProvider:
    """Build the LLM provider named in LLM_PROVIDER."""
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}")


__all__ = ["LLMProvider", "get_llm"]