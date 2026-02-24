import asyncio

from da_agent.models.style_dna import CopyStyle, ImageStyle, LayoutStyle, StyleDNA

from .copy_style import extract_copy_style
from .image_style import extract_image_style
from .layout_style import extract_layout_style


async def _extract_single(image_url: str) -> StyleDNA:
    """단일 이미지에서 3개 추출기를 병렬 실행합니다."""
    image_style, layout_style, copy_style = await asyncio.gather(
        extract_image_style(image_url),   # 1a: 독립 Vision 호출
        extract_layout_style(image_url),  # 1b: 독립 Vision 호출
        extract_copy_style(image_url),    # 1c: 독립 Vision 호출
    )
    return StyleDNA(
        image_style=image_style,
        layout_style=layout_style,
        copy_style=copy_style,
    )


def _merge_style_dnas(dnas: list[StyleDNA]) -> StyleDNA:
    """여러 StyleDNA를 병합하여 종합적인 사용자 선호 스타일을 추출합니다.

    - 색상 팔레트 / 미학 키워드 / 카피 키워드: 합산 (중복 제거)
    - 분위기 / 조명 / 톤: " / "로 연결 (Architect가 최종 해석)
    - 레이아웃: 첫 번째 이미지 기준 (가장 강한 클릭 신호)
    """
    if len(dnas) == 1:
        return dnas[0]

    # 색상 팔레트: 중복 제거 후 합산 (최대 8개)
    seen_colors: set[str] = set()
    merged_palette: list[str] = []
    for dna in dnas:
        for color in dna.image_style.color_palette:
            key = color.upper()
            if key not in seen_colors:
                seen_colors.add(key)
                merged_palette.append(color)
    merged_palette = merged_palette[:8]

    # 미학 키워드 합산 (순서 유지 중복 제거)
    merged_aesthetic = list(dict.fromkeys(
        kw for dna in dnas for kw in dna.image_style.aesthetic
    ))

    # 카피 키워드 합산
    merged_keywords = list(dict.fromkeys(
        kw for dna in dnas for kw in dna.copy_style.keywords
    ))

    return StyleDNA(
        image_style=ImageStyle(
            mood=" / ".join(dna.image_style.mood for dna in dnas),
            lighting=" / ".join(dna.image_style.lighting for dna in dnas),
            color_palette=merged_palette,
            aesthetic=merged_aesthetic,
        ),
        layout_style=dnas[0].layout_style,  # 첫 번째 이미지 레이아웃 기준
        copy_style=CopyStyle(
            tone=" / ".join(dna.copy_style.tone for dna in dnas),
            length=dnas[0].copy_style.length,
            emphasis_type=dnas[0].copy_style.emphasis_type,
            keywords=merged_keywords,
        ),
    )


async def extract_style_dna(image_url: str | list[str]) -> StyleDNA:
    """Stage 1: 하나 또는 여러 광고 이미지에서 Style DNA를 추출합니다.

    - 단일 str: 해당 이미지에서 추출
    - list[str]: 각 이미지에서 병렬 추출 후 StyleDNA 병합
    """
    urls = [image_url] if isinstance(image_url, str) else list(image_url)

    # 이미지별로 3개 추출기 병렬 실행 (N images × 3 extractors 전체 동시)
    dnas = await asyncio.gather(*[_extract_single(url) for url in urls])

    return _merge_style_dnas(list(dnas))


__all__ = [
    "extract_style_dna",
    "extract_image_style",
    "extract_layout_style",
    "extract_copy_style",
]
