from __future__ import annotations

import os
import re

import fal_client
from PIL import Image

from da_agent.config import get_settings
from da_agent.models.blueprint import Blueprint
from da_agent.utils.image_utils import (
    draw_text_zone_background,
    image_to_bytes,
    load_image,
    measure_text_height,
    overlay_cta_button,
    overlay_logo,
    overlay_product,
    overlay_text,
    remove_background,
)

_TEXT_GAP = 12   # 텍스트 요소 간 세로 간격 (px)
_CTA_GAP = 20    # 서브카피와 CTA 버튼 사이 추가 간격 (px)
_TEXT_ZONE_PADDING_TOP = 28   # 텍스트 존 배경 상단 내부 패딩 (px)
_TEXT_ZONE_PADDING_SIDE = 40  # 텍스트 존 좌우 내부 패딩 (px)

_CTA_BTN_HEIGHT = 58   # CTA 버튼 높이 (px)
_CTA_BTN_MAX_WIDTH = 320  # CTA 버튼 최대 너비 (px)


def _hex_to_rgb(color_str: str) -> tuple[int, int, int]:
    """색상 문자열(#rrggbb 또는 named color)을 RGB 튜플로 변환합니다."""
    color_str = color_str.strip()
    match = re.search(r"#([0-9a-fA-F]{6})", color_str)
    if match:
        h = match.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # 기본: 진한 다크 톤
    return (20, 20, 20)


def _brand_zone_color(brand_identity: dict) -> tuple[int, int, int]:
    """브랜드 primary 컬러에서 텍스트 존 배경색을 추출합니다."""
    colors = brand_identity.get("primary_colors", [])
    if colors:
        return _hex_to_rgb(colors[0])
    return (20, 20, 20)


def _brand_cta_color(brand_identity: dict) -> tuple[int, int, int, int]:
    """브랜드 컬러에서 CTA 버튼 배경색을 추출합니다.

    secondary_colors 우선, 없으면 primary 컬러를 밝게 조정합니다.
    """
    secondary = brand_identity.get("secondary_colors", [])
    primary = brand_identity.get("primary_colors", [])

    if secondary:
        r, g, b = _hex_to_rgb(secondary[0])
    elif len(primary) > 1:
        r, g, b = _hex_to_rgb(primary[1])
    elif primary:
        # primary 단색이면 +60 밝게 보정 → 버튼이 배경과 구분되게
        r, g, b = _hex_to_rgb(primary[0])
        r, g, b = min(r + 60, 255), min(g + 60, 255), min(b + 60, 255)
    else:
        return (255, 80, 0, 255)  # 기본 오렌지

    return (r, g, b, 255)


async def generate_ad_image(
    blueprint: Blueprint,
    brand_identity: dict,
    product_image_url: str | None = None,
) -> tuple[Image.Image, bytes]:
    """Stage 3: Blueprint를 바탕으로 최종 광고 이미지를 생성·합성합니다.

    실제 DA처럼 보이도록 다음 레이어 순서로 합성합니다:
      1) FLUX.1 배경 이미지 생성
      2) 제품 이미지 합성 (배경 제거 후)
      3) 텍스트 존 컬러 밴드 (전체 너비, 브랜드 컬러)
      4) 헤드라인 + 서브카피 텍스트
      5) CTA 버튼 (둥근 사각형)
      6) 브랜드 로고 합성

    Args:
        blueprint: 설계도 (카피, 이미지 프롬프트, 레이아웃 가이드)
        brand_identity: 브랜드 아이덴티티 (로고 URL, 컬러)
        product_image_url: 실제 제품 이미지 경로/URL — 제공 시 product_bbox에 직접 합성

    Returns:
        (PIL Image, PNG bytes)
    """
    settings = get_settings()

    # 1. FLUX.1 [dev] 로 배경 이미지 생성
    base_image = await _generate_base_image(blueprint, settings)
    canvas_w, canvas_h = base_image.size
    lg = blueprint.layout_guide

    # 2. 실제 제품 이미지 합성
    if product_image_url:
        product_img = await load_image(product_image_url)
        product_img = remove_background(product_img)  # 배경 자동 제거 → 투명 PNG
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

    # 3. 텍스트 존 컬러 밴드 — 전체 너비로 브랜드 컬러 배경 생성
    #    실제 DA처럼 텍스트 영역을 불투명한 컬러 존으로 명확히 구분합니다.
    zone_y = lg.text_bbox.y
    zone_h = canvas_h - zone_y  # text_bbox 상단부터 캔버스 하단까지
    zone_color = _brand_zone_color(brand_identity)
    composed = draw_text_zone_background(
        composed,
        x=0,
        y=zone_y,
        width=canvas_w,
        height=zone_h,
        color=zone_color,
        alpha=215,
    )

    # 4. 헤드라인 + 서브카피 오버레이
    text_x = lg.text_bbox.x + _TEXT_ZONE_PADDING_SIDE
    text_y = zone_y + _TEXT_ZONE_PADDING_TOP
    max_w = lg.text_bbox.width - _TEXT_ZONE_PADDING_SIDE

    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.headline,
        x=text_x,
        y=text_y,
        max_width=max_w,
        font_size=52,
        bold=True,
        color=(255, 255, 255, 255),
        shadow=False,  # 컬러 배경이 생겼으므로 섀도우 불필요
    )
    headline_h = measure_text_height(
        blueprint.ad_copy.headline, max_w, font_size=52, bold=True
    )

    sub_y = text_y + headline_h + _TEXT_GAP
    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.subheadline,
        x=text_x,
        y=sub_y,
        max_width=max_w,
        font_size=30,
        bold=False,
        color=(210, 210, 210, 220),
        shadow=False,
    )
    sub_h = measure_text_height(
        blueprint.ad_copy.subheadline, max_w, font_size=30, bold=False
    )

    # 5. CTA 버튼 — 실제 버튼 모양으로 클릭 유도감을 높임
    cta_btn_w = min(_CTA_BTN_MAX_WIDTH, max_w)
    cta_btn_x = text_x  # 좌측 정렬 (헤드라인과 동일 기준선)
    cta_btn_y = sub_y + sub_h + _CTA_GAP
    cta_color = _brand_cta_color(brand_identity)
    composed = overlay_cta_button(
        composed,
        text=blueprint.ad_copy.cta,
        x=cta_btn_x,
        y=cta_btn_y,
        width=cta_btn_w,
        height=_CTA_BTN_HEIGHT,
        bg_color=cta_color,
        text_color=(255, 255, 255, 255),
        font_size=26,
    )

    # 6. 브랜드 로고 합성
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
