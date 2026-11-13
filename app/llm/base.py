"""Base interface for LLM provider adapters."""
from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class BaseChatAdapter(ABC):
    """Abstract interface that all LLM provider adapters must implement."""

    def __init__(self, model_id: str, provider_name: str, timeout_seconds: int = 60):
        self.model_id = model_id
        self.provider_name = provider_name
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[T]
    ) -> T:
        """Invokes the model and returns a validated Pydantic object conforming to response_model."""
        pass

