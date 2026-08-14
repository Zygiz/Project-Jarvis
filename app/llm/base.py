from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """The contract every LLM provider must fulfil.

    Anything that can turn a prompt into text can be a provider —
    Gemini, Anthropic, a local Ollama model, or a fake one for tests.
    """

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        history: list[dict] | None = None,
        label: str = "chat",
    ) -> str:
        """Send a prompt with optional conversation history, return the reply.

        history is a list of {"role": "user"|"assistant", "text": str},
        oldest first. Providers translate these role names internally.
        """
        ...