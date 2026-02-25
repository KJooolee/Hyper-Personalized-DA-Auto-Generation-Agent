from __future__ import annotations

import os

import fal_client
from PIL import Image

from da_agent.config import get_settings
from da_agent.models.blueprint import Blueprint
from da_agent.utils.image_utils import (
    image_to_bytes,
    load_image,
    measure_text_height,
    overlay_logo,
    overlay_product,
    overlay_text,
)

_TEXT_GAP = 10   # 텍스트 요소 간 세로 간격 (px)
_CTA_GAP = 16    # 서브카피와 CTA 사이 추가 간격 (px)


async def generate_ad_image(
    blueprint: Blueprint,
    brand_identity: dict,
    product_image_url: str | None = None,
) -> tuple[Image.Image, bytes]:
    """Stage 3: Blueprint를 바탕으로 최종 광고 이미지를 생성·합성합니다.

    Args:
        blueprint: 설계도 (카피, 이미지 프롬프트, 레이아웃 가이드)
        brand_identity: 브랜드 아이덴티티 (로고 URL, 컬러)
        product_image_url: 실제 제품 이미지 경로/URL — 제공 시 product_bbox에 직접 합성

    Returns:
        (PIL Image, PNG bytes)
    """
    settings = get_settings()

    # 1. FLUX.1 [dev] 로 배경 이미지 생성 (제품 영역은 비워 둠)
    base_image = await _generate_base_image(blueprint, settings)
    lg = blueprint.layout_guide

    # 2. 실제 제품 이미지 합성 (AI가 그린 가상 제품 대신 원본 사용)
    if product_image_url:
        product_img = await load_image(product_image_url)
        composed = overlay_product(
            base_image,
            product=product_img,
            x=lg.product_bbox.x,
            y=lg.product_bbox.y,
            width=lg.product_bbox.width,
            height=lg.product_bbox.height,
        )
    else:
        composed = base_image

    # 3. 한글 카피 오버레이 — 실제 렌더링 높이로 동적 위치 계산
    text_x = lg.text_bbox.x
    text_y = lg.text_bbox.y
    max_w = lg.text_bbox.width

    # 헤드라인
    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.headline,
        x=text_x,
        y=text_y,
        max_width=max_w,
        font_size=52,
        bold=True,
        color=(255, 255, 255, 255),
    )
    headline_h = measure_text_height(
        blueprint.ad_copy.headline, max_w, font_size=52, bold=True
    )

    # 서브카피 — 헤드라인 실제 높이 + 간격만큼 아래에 배치
    sub_y = text_y + headline_h + _TEXT_GAP
    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.subheadline,
        x=text_x,
        y=sub_y,
        max_width=max_w,
        font_size=32,
        bold=False,
        color=(240, 240, 240, 220),
    )
    sub_h = measure_text_height(
        blueprint.ad_copy.subheadline, max_w, font_size=32, bold=False
    )

    # CTA — 서브카피 아래 추가 간격
    cta_y = sub_y + sub_h + _CTA_GAP
    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.cta,
        x=text_x,
        y=cta_y,
        max_width=max_w,
        font_size=28,
        bold=True,
        color=(255, 220, 80, 255),
    )

    # 4. 브랜드 로고 합성
    logo_url = brand_identity.get("logo_url")
    if logo_url:
        logo_img = await load_image(logo_url)
        composed = overlay_logo(
            composed,
            logo=logo_img,
            x=lg.logo_bbox.x,
            y=lg.logo_bbox.y,
            width=lg.logo_bbox.width,
            height=lg.logo_bbox.height,
        )

    return composed, image_to_bytes(composed)


async def _generate_base_image(blueprint: Blueprint, settings) -> Image.Image:
    """FLUX.1 [dev] API로 배경 이미지를 생성합니다."""
    # fal_client reads FAL_KEY directly from os.environ (not from pydantic settings)
    if settings.fal_key:
        os.environ["FAL_KEY"] = settings.fal_key

    result = await fal_client.run_async(
        settings.image_gen_model,
        arguments={
            "prompt": blueprint.image_prompt,
            "image_size": {
                "width": settings.image_width,
                "height": settings.image_height,
            },
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": True,
        },
    )

    image_url = result["images"][0]["url"]
    return await load_image(image_url)
