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
_CTA_GAP = 16    # 서브카피와 CTA 버튼 사이 추가 간격 (px)
_TEXT_ZONE_PADDING_TOP = 24    # 텍스트 존 배경 상단 내부 패딩 (px)
_TEXT_ZONE_PADDING_SIDE = 32   # 텍스트 존 좌우 내부 패딩 (px)

_CTA_BTN_HEIGHT = 52    # CTA 버튼 높이 (px)
_CTA_BTN_MAX_WIDTH = 300  # CTA 버튼 최대 너비 (px)

# 가로형 배너 판정 기준: 너비가 높이의 2.5배 이상이면 배너
_BANNER_ASPECT_THRESHOLD = 2.5


def _is_horizontal_banner(canvas_w: int, canvas_h: int) -> bool:
    return canvas_w > canvas_h * _BANNER_ASPECT_THRESHOLD


def _hex_to_rgb(color_str: str) -> tuple[int, int, int]:
    """색상 문자열(#rrggbb)을 RGB 튜플로 변환합니다."""
    color_str = color_str.strip()
    match = re.search(r"#([0-9a-fA-F]{6})", color_str)
    if match:
        h = match.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
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
        r, g, b = _hex_to_rgb(primary[0])
        r, g, b = min(r + 60, 255), min(g + 60, 255), min(b + 60, 255)
    else:
        return (255, 80, 0, 255)

    return (r, g, b, 255)


async def generate_ad_image(
    blueprint: Blueprint,
    brand_identity: dict,
    product_image_url: str | None = None,
) -> tuple[Image.Image, bytes]:
    """Stage 3: Blueprint를 바탕으로 최종 광고 이미지를 생성·합성합니다.

    레이어 순서:
      1) FLUX.1 배경 이미지 생성 (txt2img)
      2) 제품 이미지 합성 (배경 제거 후, 확대·축소 + 캔버스 클램핑)
      3) 텍스트 존 컬러 밴드
         - 가로형 배너: text_bbox.x부터 우측 끝까지 세로 밴드
         - 정사각형/세로형: text_bbox.y부터 하단 끝까지 가로 밴드
      4) 헤드라인 + 서브카피 텍스트 (캔버스 오버플로 방지)
      5) CTA 버튼 (캔버스 오버플로 방지)
      6) 브랜드 로고 합성

    Args:
        blueprint: 설계도 (카피, 이미지 프롬프트, 레이아웃 가이드)
        brand_identity: 브랜드 아이덴티티 (로고 URL, 컬러)
        product_image_url: 실제 제품 이미지 경로/URL

    Returns:
        (PIL Image, PNG bytes)
    """
    settings = get_settings()

    # 1. 배경 이미지 생성 (txt2img)
    base_image = await _generate_base_image(blueprint, settings)
    canvas_w, canvas_h = base_image.size
    lg = blueprint.layout_guide
    banner = _is_horizontal_banner(canvas_w, canvas_h)

    # 2. 실제 제품 이미지 합성
    if product_image_url:
        product_img = await load_image(product_image_url)
        product_img = remove_background(product_img)
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

    # 3. 텍스트 존 컬러 밴드 — 비율에 따라 가로/세로 밴드 선택
    zone_color = _brand_zone_color(brand_identity)
    if banner:
        # 가로형 배너: text_bbox.x부터 오른쪽 끝까지 전체 높이 세로 밴드
        zone_x = lg.text_bbox.x
        zone_y = 0
        zone_w = canvas_w - lg.text_bbox.x
        zone_h = canvas_h
    else:
        # 정사각형/세로형: text_bbox.y부터 아래쪽 끝까지 전체 너비 가로 밴드
        zone_x = 0
        zone_y = lg.text_bbox.y
        zone_w = canvas_w
        zone_h = canvas_h - lg.text_bbox.y

    composed = draw_text_zone_background(
        composed,
        x=zone_x,
        y=zone_y,
        width=zone_w,
        height=zone_h,
        color=zone_color,
        alpha=215,
    )

    # 4. 헤드라인 + 서브카피 오버레이
    text_x = lg.text_bbox.x + _TEXT_ZONE_PADDING_SIDE
    text_y = lg.text_bbox.y + _TEXT_ZONE_PADDING_TOP

    # max_w는 ① text_bbox 내부 너비, ② 캔버스 오른쪽 경계까지 남은 거리 중 작은 값으로 클램핑
    # → architect가 text_bbox.x + text_bbox.width > canvas_w를 잘못 생성해도 텍스트 우측 잘림 방지
    max_w = max(
        50,
        min(
            lg.text_bbox.width - _TEXT_ZONE_PADDING_SIDE * 2,
            canvas_w - text_x - _TEXT_ZONE_PADDING_SIDE,
        ),
    )

    # 가로형 배너에서는 폰트를 줄여서 좁은 높이에 맞춤
    headline_size = 32 if banner else 52
    sub_size = 20 if banner else 30
    cta_size = 18 if banner else 26
    cta_btn_h = 36 if banner else _CTA_BTN_HEIGHT

    # 캔버스 높이를 넘지 않는 경우만 렌더링
    if text_y < canvas_h:
        composed = overlay_text(
            composed,
            text=blueprint.ad_copy.headline,
            x=text_x,
            y=text_y,
            max_width=max_w,
            font_size=headline_size,
            bold=True,
            color=(255, 255, 255, 255),
            shadow=False,
        )
    headline_h = measure_text_height(
        blueprint.ad_copy.headline, max_w, font_size=headline_size, bold=True
    )

    sub_y = text_y + headline_h + _TEXT_GAP
    if sub_y < canvas_h:
        composed = overlay_text(
            composed,
            text=blueprint.ad_copy.subheadline,
            x=text_x,
            y=sub_y,
            max_width=max_w,
            font_size=sub_size,
            bold=False,
            color=(210, 210, 210, 220),
            shadow=False,
        )
    sub_h = measure_text_height(
        blueprint.ad_copy.subheadline, max_w, font_size=sub_size, bold=False
    )

    # 5. CTA 버튼 — 캔버스 하단을 넘지 않도록 y 클램핑
    cta_btn_w = min(_CTA_BTN_MAX_WIDTH, max_w)
    cta_btn_x = text_x
    cta_btn_y = sub_y + sub_h + _CTA_GAP
    cta_btn_y = min(cta_btn_y, canvas_h - cta_btn_h - 4)  # 캔버스 밖으로 밀려나지 않도록

    if cta_btn_y >= 0 and cta_btn_y + cta_btn_h <= canvas_h:
        cta_color = _brand_cta_color(brand_identity)
        composed = overlay_cta_button(
            composed,
            text=blueprint.ad_copy.cta,
            x=cta_btn_x,
            y=cta_btn_y,
            width=cta_btn_w,
            height=cta_btn_h,
            bg_color=cta_color,
            text_color=(255, 255, 255, 255),
            font_size=cta_size,
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
    """FLUX.1 [dev] API로 배경 이미지를 생성합니다 (txt2img).

    image_prompt는 architect가 제품 카테고리와 브랜드 무드에 맞게 생성합니다.
    배경에 제품·텍스트·UI 요소가 포함되지 않도록 architect.txt에서 엄격히 제한합니다.
    """
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
