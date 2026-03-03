"""Stage 3b — Vision 기반 레이아웃 분석기

생성된 이미지를 Vision LLM이 직접 보고 카피·로고의 최적 배치 좌표를 결정합니다.
LLM이 좌표를 상상하는 대신 실제 이미지를 분석하므로 배치 품질이 크게 향상됩니다.
"""
from __future__ import annotations

import base64
import json
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image

from da_agent.config import get_settings
from da_agent.models.ad_layout import AdLayout
from da_agent.utils.http_client import create_openai_client

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "utils/prompt_templates/layout_analyzer.txt"
)


def _image_to_data_url(image: Image.Image) -> str:
    """PIL Image를 Vision API용 base64 JPEG data URL로 변환합니다."""
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _clamp_layout(layout: AdLayout, canvas_w: int, canvas_h: int) -> AdLayout:
    """Vision이 반환한 좌표를 캔버스 경계 내로 클램핑합니다."""
    def clamp_bbox(bbox, max_w, max_h):
        x = max(0, min(bbox.x, max_w - 1))
        y = max(0, min(bbox.y, max_h - 1))
        w = max(1, min(bbox.width, max_w - x))
        h = max(1, min(bbox.height, max_h - y))
        return bbox.__class__(x=x, y=y, width=w, height=h)

    return AdLayout(
        text_zone=clamp_bbox(layout.text_zone, canvas_w, canvas_h),
        logo_zone=clamp_bbox(layout.logo_zone, canvas_w, canvas_h),
        text_color=layout.text_color if layout.text_color in ("white", "dark") else "white",
    )


async def analyze_ad_layout(image: Image.Image) -> AdLayout:
    """Stage 3b: 생성 이미지를 Vision으로 분석해 카피·로고 배치 존을 결정합니다.

    Args:
        image: FLUX img2img로 스타일 변환이 완료된 PIL Image

    Returns:
        AdLayout — text_zone, logo_zone, text_color
    """
    settings = get_settings()
    client = create_openai_client()
    canvas_w, canvas_h = image.size

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = template.format(width=canvas_w, height=canvas_h)

    response = await client.chat.completions.create(
        model=settings.stage1_model,  # gpt-4o-mini (Vision)
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": _image_to_data_url(image),
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        response_format={"type": "json_object"},
        max_tokens=512,
    )

    raw = json.loads(response.choices[0].message.content)
    raw.pop("reasoning", None)  # 모델 필드에 없는 reasoning 제거
    layout = AdLayout(**raw)
    layout = _clamp_layout(layout, canvas_w, canvas_h)

    logger.info(
        "Layout analysis: text_zone=%s, logo_zone=%s, text_color=%s",
        layout.text_zone,
        layout.logo_zone,
        layout.text_color,
    )
    return layout
