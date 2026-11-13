"""Application configuration using Pydantic Settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base directory: root of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    # API Server Configuration
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_url: str = Field(default="http://127.0.0.1:8000", alias="API_URL")

    # Evaluation Store
    evaluation_data_dir: Path = Field(
        default=BASE_DIR / "data" / "evaluations",
        alias="EVALUATION_DATA_DIR"
    )

    # Timeouts & Request Limits
    model_timeout_seconds: int = Field(default=60, alias="MODEL_TIMEOUT_SECONDS")
    max_input_bytes: int = Field(default=1_048_576, alias="MAX_INPUT_BYTES")  # 1 MB

    # Model Provider Settings
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    chatgpt_model_id: str = Field(default="gpt-4o", alias="CHATGPT_MODEL_ID")

    qwen_api_key: str = Field(default="", alias="QWEN_API_KEY")
    qwen_base_url: str = Field(default="", alias="QWEN_BASE_URL")
    qwen_model_id: str = Field(default="qwen/qwen3.8-27b", alias="QWEN_MODEL_ID")

    gpt_oss_api_key: str = Field(default="", alias="GPT_OSS_API_KEY")
    gpt_oss_base_url: str = Field(default="", alias="GPT_OSS_BASE_URL")
    gpt_oss_model_id: str = Field(default="openai/gpt-oss-120b", alias="GPT_OSS_MODEL_ID")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
