"""Model registry resolving user-facing keys to configured provider adapters."""
from typing import Dict, List, Optional
from app.core.config import Settings, settings
from app.schemas.evaluations import ModelOption
from app.llm.base import BaseChatAdapter
from app.llm.factory import create_adapter

class ModelRegistry:
    """Registry maintaining available LLM configurations and credentials."""

    def __init__(self, current_settings: Optional[Settings] = None):
        self.settings = current_settings or settings

    def get_definitions(self) -> Dict[str, dict]:
        """Returns the dictionary of configured model metadata."""
        # 1. ChatGPT Paid Model (OpenAI API)
        chatgpt_enabled = bool(self.settings.openai_api_key.strip())
        
        # 2. Qwen Model
        qwen_enabled = bool(self.settings.qwen_api_key.strip())

        # 3. GPT-OSS 120B Model
        gpt_oss_enabled = bool(self.settings.gpt_oss_api_key.strip() or self.settings.gpt_oss_base_url.strip())

        return {
            "gpt_oss_120b": {
                "key": "gpt_oss_120b",
                "label": "GPT-OSS 120B",
                "enabled": gpt_oss_enabled,
                "provider_type": "openai_compatible",
                "provider_name": "gpt_oss_provider",
                "model_id": self.settings.gpt_oss_model_id or "gpt-oss-120b",
                "api_key": self.settings.gpt_oss_api_key,
                "base_url": self.settings.gpt_oss_base_url or None,
                "timeout_seconds": self.settings.model_timeout_seconds,
            },
            "qwen": {
                "key": "qwen",
                "label": "Qwen",
                "enabled": qwen_enabled,
                "provider_type": "openai_compatible",
                "provider_name": "qwen_provider",
                "model_id": self.settings.qwen_model_id or "qwen-2.5-72b-instruct",
                "api_key": self.settings.qwen_api_key,
                "base_url": self.settings.qwen_base_url or None,
                "timeout_seconds": self.settings.model_timeout_seconds,
            },
            "chatgpt_paid": {
                "key": "chatgpt_paid",
                "label": "GPT-6 Luna" if "luna" in (self.settings.chatgpt_model_id or "").lower() else "ChatGPT Paid Model",
                "enabled": chatgpt_enabled,
                "provider_type": "openai_compatible",
                "provider_name": "openai",
                "model_id": self.settings.chatgpt_model_id or "gpt-6-luna",
                "api_key": self.settings.openai_api_key,
                "base_url": self.settings.openai_base_url or "https://api.openai.com/v1",
                "timeout_seconds": self.settings.model_timeout_seconds,
            }
        }

    def list_options(self) -> List[ModelOption]:
        """Returns safe user-facing model options for UI/API listing without secrets."""
        definitions = self.get_definitions()
        return [
            ModelOption(
                key=defn["key"],
                label=defn["label"],
                enabled=defn["enabled"],
                model_id=defn["model_id"]
            )
            for defn in definitions.values()
        ]

    def get_adapter(self, config_key: str) -> BaseChatAdapter:
        """Instantiates and returns the configured adapter for the specified key."""
        definitions = self.get_definitions()
        if config_key not in definitions:
            raise ValueError(f"Unknown model configuration key: '{config_key}'")

        config = definitions[config_key]
        if not config["enabled"]:
            raise ValueError(
                f"Model configuration '{config_key}' ({config['label']}) is currently disabled. "
                f"Please provide the required API credentials in your environment/.env file."
            )

        return create_adapter(config)

model_registry = ModelRegistry()

