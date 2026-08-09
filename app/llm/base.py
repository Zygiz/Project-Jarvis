from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """The contract every LLM provider must fulfil.

    Anything that can turn a prompt into text can be a provider —
    Gemini, Anthropic, a local Ollama model, or a fake one for tests.
    """

    @abstractmethod
    def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt, return the model's text reply."""
        ...