"""
공유 OpenAI 클라이언트 팩토리

기업 프록시 환경의 SSL 인증서 오류를 처리합니다.
SSL_VERIFY=false 또는 CA_BUNDLE_PATH 설정으로 동작을 제어합니다.
"""
import ssl
import warnings

import certifi
import httpx
from openai import AsyncOpenAI

from da_agent.config import get_settings


def _build_ssl_context() -> ssl.SSLContext | bool | str:
    """환경설정에 따라 SSL 컨텍스트를 반환합니다.

    Returns:
        - ssl.SSLContext: 커스텀 CA 번들 사용 시
        - str (certifi 경로): 기본 동작
        - False: SSL 검증 완전 비활성화 (비권장, 프록시 환경 임시 우회용)
    """
    settings = get_settings()

    if not settings.ssl_verify:
        warnings.warn(
            "SSL verification is disabled (SSL_VERIFY=false). "
            "This is insecure and should only be used in development.",
            stacklevel=3,
        )
        return False

    if settings.ca_bundle_path:
        # 기업 CA 인증서를 certifi 기본 번들과 합쳐서 사용
        ctx = ssl.create_default_context(cafile=certifi.where())
        ctx.load_verify_locations(cafile=settings.ca_bundle_path)
        return ctx

    # 기본값: certifi CA 번들 (시스템 인증서보다 최신 유지)
    return certifi.where()


def create_openai_client() -> AsyncOpenAI:
    """SSL 설정이 적용된 AsyncOpenAI 클라이언트를 생성합니다."""
    settings = get_settings()
    ssl_config = _build_ssl_context()
    http_client = httpx.AsyncClient(verify=ssl_config)
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        http_client=http_client,
    )
