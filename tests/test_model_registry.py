"""Tests for ModelRegistry and provider adapter instantiation."""
import pytest
from app.core.config import Settings
from app.services.model_registry import ModelRegistry
from app.llm.base import BaseChatAdapter

def test_model_registry_disabled_by_default():
    """Models with empty keys are marked disabled and cannot be instantiated."""
    empty_settings = Settings(
        openai_api_key="",
        qwen_api_key="",
        gpt_oss_api_key="",
        gpt_oss_base_url=""
    )
    registry = ModelRegistry(empty_settings)
    options = registry.list_options()
    
    assert len(options) == 3
    for opt in options:
        assert opt.enabled is False
    
    with pytest.raises(ValueError, match="is currently disabled"):
        registry.get_adapter("chatgpt_paid")

def test_model_registry_instantiates_enabled_models():
    """When API keys are configured, all models become enabled and instantiate through BaseChatAdapter."""
    configured_settings = Settings(
        openai_api_key="sk-test-openai-key",
        chatgpt_model_id="gpt-4o",
        qwen_api_key="sk-test-qwen-key",
        qwen_base_url="https://dashscope.example.com/compatible-mode/v1",
        qwen_model_id="qwen-2.5-72b-instruct",
        gpt_oss_api_key="sk-test-oss-key",
        gpt_oss_base_url="http://localhost:8080/v1",
        gpt_oss_model_id="gpt-oss-120b"
    )
    registry = ModelRegistry(configured_settings)
    options = registry.list_options()
    
    for opt in options:
        assert opt.enabled is True
        adapter = registry.get_adapter(opt.key)
        assert isinstance(adapter, BaseChatAdapter)
        assert adapter.model_id is not None
        assert hasattr(adapter, "generate_structured")

