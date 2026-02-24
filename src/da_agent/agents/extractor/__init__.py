import asyncio

from da_agent.models.style_dna import StyleDNA

from .copy_style import extract_copy_style
from .image_style import extract_image_style
from .layout_style import extract_layout_style


async def extract_style_dna(image_url: str) -> StyleDNA:
    """Stage 1: 3개 추출기를 병렬 실행하여 Style DNA를 추출합니다."""
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


__all__ = [
    "extract_style_dna",
    "extract_image_style",
    "extract_layout_style",
    "extract_copy_style",
]
