"""Backend-agnostic judge interface for headless LLM evaluation."""

from abc import ABC, abstractmethod


class LLMJudge(ABC):
    """Abstract base class for LLM judge backends.

    A judge takes a text prompt and returns a text response.
    Implementations are responsible for connecting to their respective
    LLM backend and handling errors gracefully.
    """

    @abstractmethod
    def judge(self, prompt: str) -> str:
        """Send a prompt to the LLM and return its response.

        Args:
            prompt: The text prompt to evaluate.

        Returns:
            The LLM's text response.

        Raises:
            RuntimeError: If the backend is unavailable or returns an error.
        """
