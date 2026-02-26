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
    # Stage 1 (extractor) / Stage 3b (layout analyzer): 빠른 Vision 분석
    stage1_model: str = "claude-haiku-4-5-20251001"
    # Stage 2 (architect): 한국어 광고 카피 생성 — 고품질 모델 사용
    stage2_model: str = "claude-sonnet-4-6"
    # Stage 4 (evaluator): 가이드라인 적합성 평가
    stage4_model: str = "claude-haiku-4-5-20251001"
    image_gen_model: str = "fal-ai/flux/dev"

    # Pipeline Configuration
    max_eval_iterations: int = 3
    eval_pass_score: int = 80

    # Image Configuration
    image_width: int = 1000
    image_height: int = 1000

    # SSL / Proxy Configuration
    # 기업 프록시 환경에서 SSL 검증 오류 발생 시 false로 설정
    ssl_verify: bool = True
    # 커스텀 CA 인증서 경로 (기업 CA 번들 경로, 비워두면 certifi 기본값 사용)
    ca_bundle_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
