"""Stage 3b — Pillow 기반 레이아웃 분석기

이미지의 밝기 분산을 직접 측정해 텍스트·로고 최적 배치 존을 결정합니다.
Vision LLM을 사용하지 않으므로 API 비용 없이 100% 안정적인 좌표를 반환합니다.
"""
from __future__ import annotations

import logging

from PIL import Image, ImageStat

from da_agent.models.ad_layout import AdLayout, BBox

logger = logging.getLogger(__name__)

# 텍스트 배치 후보 존 — 이미지 비율로 정의 (x, y, w, h) as fractions
_CANDIDATE_ZONES: dict[str, tuple[float, float, float, float]] = {
    "bottom": (0.0, 0.60, 1.0, 0.40),   # 하단 40%
    "top":    (0.0, 0.0,  1.0, 0.35),   # 상단 35%
    "left":   (0.0, 0.0,  0.40, 1.0),   # 좌측 40%
}

# 로고 존 크기 (이미지 대비 비율)
_LOGO_W_RATIO = 0.15
_LOGO_H_RATIO = 0.07
_LOGO_MARGIN = 20   # px


def _zone_stddev(gray: Image.Image, x: int, y: int, w: int, h: int) -> float:
    """지정된 픽셀 영역의 밝기 표준편차를 반환합니다. 낮을수록 단조로운 배경."""
    crop = gray.crop((x, y, x + w, y + h))
    return ImageStat.Stat(crop).stddev[0]


def _pick_text_zone(gray: Image.Image, canvas_w: int, canvas_h: int) -> str:
    """각 후보 존의 밝기 분산을 비교해 가장 단조로운 존 이름을 반환합니다."""
    best: str | None = None
    best_std = float("inf")
    for name, (xr, yr, wr, hr) in _CANDIDATE_ZONES.items():
        x, y = int(xr * canvas_w), int(yr * canvas_h)
        w, h = int(wr * canvas_w), int(hr * canvas_h)
        std = _zone_stddev(gray, x, y, w, h)
        logger.debug("Zone '%s' stddev=%.1f", name, std)
        if std < best_std:
            best_std = std
            best = name
    return best  # type: ignore[return-value]


def _build_logo_zone(
    zone_name: str, canvas_w: int, canvas_h: int
) -> BBox:
    """텍스트 존과 겹치지 않는 코너에 로고 존을 배치합니다."""
    lw = max(80, int(canvas_w * _LOGO_W_RATIO))
    lh = max(40, int(canvas_h * _LOGO_H_RATIO))

    # 텍스트가 하단 → 로고는 우상단 / 텍스트가 상단 → 로고는 우하단 / 좌측 → 우상단
    if zone_name == "top":
        lx = canvas_w - lw - _LOGO_MARGIN
        ly = canvas_h - lh - _LOGO_MARGIN
    else:  # bottom or left → 우상단
        lx = canvas_w - lw - _LOGO_MARGIN
        ly = _LOGO_MARGIN

    return BBox(x=lx, y=ly, width=lw, height=lh)


def analyze_ad_layout(image: Image.Image) -> AdLayout:
    """Stage 3b: 이미지 밝기 분산 분석으로 카피·로고 배치 존을 결정합니다.

    Args:
        image: FLUX img2img로 스타일 변환이 완료된 PIL Image

    Returns:
        AdLayout — text_zone, logo_zone, text_color
    """
    canvas_w, canvas_h = image.size
    gray = image.convert("L")

    # 가장 단조로운 배경 구역 선택
    zone_name = _pick_text_zone(gray, canvas_w, canvas_h)
    xr, yr, wr, hr = _CANDIDATE_ZONES[zone_name]
    tz_x = int(xr * canvas_w)
    tz_y = int(yr * canvas_h)
    tz_w = int(wr * canvas_w)
    tz_h = int(hr * canvas_h)

    # 텍스트 색상: 선택 존의 평균 밝기로 결정
    crop = gray.crop((tz_x, tz_y, tz_x + tz_w, tz_y + tz_h))
    mean_brightness = ImageStat.Stat(crop).mean[0]
    text_color = "dark" if mean_brightness > 140 else "white"

    text_zone = BBox(x=tz_x, y=tz_y, width=tz_w, height=tz_h)
    logo_zone = _build_logo_zone(zone_name, canvas_w, canvas_h)

    logger.info(
        "Layout (Pillow): zone=%s stddev-based, text_zone=%s, logo_zone=%s, "
        "text_color=%s (brightness=%.0f)",
        zone_name,
        text_zone,
        logo_zone,
        text_color,
        mean_brightness,
    )
    return AdLayout(text_zone=text_zone, logo_zone=logo_zone, text_color=text_color)
