"""
공유 OpenAI 클라이언트 팩토리

기업 프록시 환경의 SSL 인증서 오류를 처리합니다.
SSL_VERIFY=false 또는 CA_BUNDLE_PATH 설정으로 동작을 제어합니다.
"""
import os
import ssl
import warnings

import certifi
import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from da_agent.config import get_settings


def configure_ssl_globally() -> None:
    """SSL 설정을 전역으로 적용합니다.

    fal_client 등 자체 httpx 클라이언트를 생성하는 외부 라이브러리에도
    SSL 설정이 적용되도록 Python ssl 모듈을 패치합니다.
    파이프라인 시작 시 가장 먼저 호출해야 합니다.

    httpx는 내부적으로 ssl.create_default_context()를 직접 호출하므로
    ssl._create_default_https_context 패치로는 효과가 없습니다.
    ssl.create_default_context 자체를 교체해야 모든 httpx 클라이언트에 적용됩니다.
    """
    settings = get_settings()

    if not settings.ssl_verify:
        warnings.warn(
            "SSL verification disabled globally (SSL_VERIFY=false). "
            "This affects ALL HTTPS connections including fal_client. "
            "Use only in development / corporate proxy environments.",
            stacklevel=2,
        )
        # httpx는 ssl.create_default_context()를 직접 호출하므로 이 함수를 패치
        _original_create_default_context = ssl.create_default_context

        def _unverified_create_default_context(*args, **kwargs):
            ctx = _original_create_default_context(*args, **kwargs)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

        ssl.create_default_context = _unverified_create_default_context  # type: ignore[assignment]

        # http.client (urllib 계열) 도 커버
        ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001
        os.environ.setdefault("PYTHONHTTPSVERIFY", "0")

    elif settings.ca_bundle_path:
        # 기업 CA 번들을 환경변수로 지정 → requests / httpx 모두 인식
        os.environ["SSL_CERT_FILE"] = settings.ca_bundle_path
        os.environ["REQUESTS_CA_BUNDLE"] = settings.ca_bundle_path


def _build_ssl_context() -> ssl.SSLContext | bool | str:
    """환경설정에 따라 SSL 컨텍스트를 반환합니다.

    Returns:
        - ssl.SSLContext: 커스텀 CA 번들 사용 시
        - str (certifi 경로): 기본 동작
        - False: SSL 검증 완전 비활성화 (비권장, 프록시 환경 임시 우회용)
    """
    settings = get_settings()

    if not settings.ssl_verify:
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


def create_anthropic_client() -> AsyncAnthropic:
    """SSL 설정이 적용된 AsyncAnthropic 클라이언트를 생성합니다."""
    settings = get_settings()
    ssl_config = _build_ssl_context()
    http_client = httpx.AsyncClient(verify=ssl_config)
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        http_client=http_client,
    )
