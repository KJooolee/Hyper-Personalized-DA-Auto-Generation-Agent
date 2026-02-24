from __future__ import annotations

import fal_client
from PIL import Image

from da_agent.config import get_settings
from da_agent.models.blueprint import Blueprint
from da_agent.utils.image_utils import (
    download_image,
    image_to_bytes,
    overlay_logo,
    overlay_text,
)


async def generate_ad_image(
    blueprint: Blueprint,
    brand_identity: dict,
) -> tuple[Image.Image, str]:
    """Stage 3: Blueprint를 바탕으로 최종 광고 이미지를 생성·합성합니다.

    Returns:
        (PIL Image, 임시 저장 경로 또는 data URL)
    """
    settings = get_settings()

    # 1. FLUX.1 [dev] 로 배경/구도 이미지 생성
    base_image = await _generate_base_image(blueprint, settings)

    # 2. 한글 카피 오버레이
    lg = blueprint.layout_guide
    composed = overlay_text(
        base_image,
        text=blueprint.ad_copy.headline,
        x=lg.text_bbox.x,
        y=lg.text_bbox.y,
        max_width=lg.text_bbox.width,
        font_size=52,
        bold=True,
        color=(255, 255, 255, 255),
    )
    # 서브카피 (헤드라인 아래)
    headline_height = 52 + 12
    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.subheadline,
        x=lg.text_bbox.x,
        y=lg.text_bbox.y + headline_height,
        max_width=lg.text_bbox.width,
        font_size=32,
        bold=False,
        color=(240, 240, 240, 220),
    )
    # CTA
    cta_y = lg.text_bbox.y + lg.text_bbox.height - 48
    composed = overlay_text(
        composed,
        text=blueprint.ad_copy.cta,
        x=lg.text_bbox.x,
        y=cta_y,
        max_width=lg.text_bbox.width,
        font_size=28,
        bold=True,
        color=(255, 220, 80, 255),
    )

    # 3. 브랜드 로고 합성
    logo_url = brand_identity.get("logo_url")
    if logo_url:
        logo_img = await download_image(logo_url)
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
    return await download_image(image_url)
