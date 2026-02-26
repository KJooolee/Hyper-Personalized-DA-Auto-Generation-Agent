from __future__ import annotations

import asyncio
import os
import re

import fal_client
from PIL import Image

from da_agent.agents.layout_analyzer import analyze_ad_layout
from da_agent.config import get_settings
from da_agent.models.blueprint import Blueprint
from da_agent.utils.image_utils import (
    draw_text_zone_background,
    image_to_bytes,
    load_image,
    measure_text_height,
    overlay_cta_button,
    overlay_logo,
    overlay_text,
)

_IMG2IMG_STRENGTH = 0.72  # 스타일 변환 강도 (0=원본 유지, 1=완전 변환)

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


async def _get_fal_image_url(path_or_url: str) -> str:
    """로컬 파일 경로면 fal.ai에 업로드하고 URL을 반환합니다."""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return await asyncio.to_thread(fal_client.upload_file, path_or_url)


async def _transform_style(
    existing_da: str,
    transformation_prompt: str,
    settings,
) -> Image.Image:
    """Stage 3a: FLUX.1 img2img로 기존 DA를 사용자 선호 스타일로 변환합니다.

    strength=0.72 → 제품·구도는 유지하면서 분위기·색감·조명을 확실하게 변환합니다.
    """
    fal_url = await _get_fal_image_url(existing_da)

    result = await fal_client.run_async(
        "fal-ai/flux/dev/image-to-image",
        arguments={
            "image_url": fal_url,
            "prompt": transformation_prompt,
            "strength": _IMG2IMG_STRENGTH,
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


async def generate_ad_image(
    blueprint: Blueprint,
    brand_identity: dict,
    existing_product_da: str,
) -> tuple[Image.Image, bytes]:
    """Stage 3: 기존 제품 DA를 스타일 변환하고 카피·로고를 합성합니다.

    레이어 순서:
      1) FLUX.1 img2img — 기존 DA를 사용자 선호 스타일로 변환
      2) Vision LLM — 변환된 이미지를 분석해 최적 텍스트·로고 배치 좌표 결정
      3) Pillow 합성
         a) 텍스트 존 반투명 컬러 밴드
         b) 헤드라인 + 서브카피
         c) CTA 버튼
         d) 브랜드 로고

    Args:
        blueprint: 설계도 (카피, img2img 변환 프롬프트)
        brand_identity: 브랜드 아이덴티티 (로고 URL, 컬러)
        existing_product_da: 카피 제거된 기존 제품 DA 경로/URL

    Returns:
        (PIL Image, PNG bytes)
    """
    settings = get_settings()
    if settings.fal_key:
        os.environ["FAL_KEY"] = settings.fal_key

    # Stage 3a: img2img 스타일 변환
    styled = await _transform_style(
        existing_product_da,
        blueprint.transformation_prompt,
        settings,
    )
    canvas_w, canvas_h = styled.size
    banner = _is_horizontal_banner(canvas_w, canvas_h)

    # Stage 3b: 이미지 밝기 분산 분석으로 텍스트·로고 배치 좌표 결정 (Vision LLM 미사용)
    layout = analyze_ad_layout(styled)
    tz = layout.text_zone
    lz = layout.logo_zone

    # Stage 3c: Pillow 합성
    # 텍스트 색상 결정 (Vision이 배경 밝기를 분석해 결정)
    if layout.text_color == "white":
        text_fg_color = (255, 255, 255, 255)
        sub_fg_color = (210, 210, 210, 220)
    else:
        text_fg_color = (20, 20, 20, 255)
        sub_fg_color = (60, 60, 60, 220)

    # 3c-1. 텍스트 존 반투명 배경 밴드
    zone_color = _brand_zone_color(brand_identity)
    composed = draw_text_zone_background(
        styled,
        x=tz.x,
        y=tz.y,
        width=tz.width,
        height=tz.height,
        color=zone_color,
        alpha=215,
    )

    # 3c-2. 헤드라인 + 서브카피
    text_x = tz.x + _TEXT_ZONE_PADDING_SIDE
    text_y = tz.y + _TEXT_ZONE_PADDING_TOP

    # max_w: text_zone 내부 너비와 캔버스 우측 경계 중 작은 값으로 클램핑
    max_w = max(
        50,
        min(
            tz.width - _TEXT_ZONE_PADDING_SIDE * 2,
            canvas_w - text_x - _TEXT_ZONE_PADDING_SIDE,
        ),
    )

    # 가로형 배너에서는 폰트를 줄여서 좁은 높이에 맞춤
    headline_size = 32 if banner else 52
    sub_size = 20 if banner else 30
    cta_size = 18 if banner else 26
    cta_btn_h = 36 if banner else _CTA_BTN_HEIGHT

    if text_y < canvas_h:
        composed = overlay_text(
            composed,
            text=blueprint.ad_copy.headline,
            x=text_x,
            y=text_y,
            max_width=max_w,
            font_size=headline_size,
            bold=True,
            color=text_fg_color,
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
            color=sub_fg_color,
            shadow=False,
        )
    sub_h = measure_text_height(
        blueprint.ad_copy.subheadline, max_w, font_size=sub_size, bold=False
    )

    # 3c-3. CTA 버튼 — 캔버스 하단을 넘지 않도록 y 클램핑
    cta_btn_w = min(_CTA_BTN_MAX_WIDTH, max_w)
    cta_btn_x = text_x
    cta_btn_y = sub_y + sub_h + _CTA_GAP
    cta_btn_y = min(cta_btn_y, canvas_h - cta_btn_h - 4)

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

    # 3c-4. 브랜드 로고 합성
    logo_url = brand_identity.get("logo_url")
    if logo_url:
        logo_img = await load_image(logo_url)
        composed = overlay_logo(
            composed,
            logo=logo_img,
            x=lz.x,
            y=lz.y,
            width=lz.width,
            height=lz.height,
        )

    return composed, image_to_bytes(composed)
