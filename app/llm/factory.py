"""Factory for creating LLM provider adapters."""
from typing import Dict, Any
from app.llm.base import BaseChatAdapter
from app.llm.providers.openai_compatible import OpenAICompatibleAdapter

def create_adapter(config: Dict[str, Any]) -> BaseChatAdapter:
    """Instantiates a provider adapter given a model configuration dictionary."""
    provider_type = config.get("provider_type", "openai_compatible")
    
    if provider_type == "openai_compatible":
        return OpenAICompatibleAdapter(
            model_id=config["model_id"],
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
            provider_name=config.get("provider_name", "openai_compatible"),
            timeout_seconds=config.get("timeout_seconds", 60)
        )
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")

