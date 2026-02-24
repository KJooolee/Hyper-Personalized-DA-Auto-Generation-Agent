from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM APIs
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Image Generation APIs
    fal_key: str = ""
    replicate_api_token: str = ""

    # Model Configuration
    stage1_model: str = "gpt-4o-mini"
    stage2_model: str = "gpt-4o"
    stage4_model: str = "gpt-4o-mini"
    image_gen_model: str = "fal-ai/flux/dev"

    # Pipeline Configuration
    max_eval_iterations: int = 3
    eval_pass_score: int = 80

    # Image Configuration
    image_width: int = 1080
    image_height: int = 1080


@lru_cache
def get_settings() -> Settings:
    return Settings()
