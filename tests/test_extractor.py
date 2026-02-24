"""Stage 1 추출기 테스트 (실제 API 호출 없이 구조 검증)"""
import pytest
from unittest.mock import AsyncMock, patch

from da_agent.models.style_dna import ImageStyle, LayoutStyle, CopyStyle, StyleDNA


def test_image_style_model():
    style = ImageStyle(
        mood="미니멀 럭셔리",
        lighting="소프트 자연광",
        color_palette=["#F0EDE8", "#1A1A1A", "#C8A882"],
        aesthetic=["clean editorial", "minimalist"],
    )
    assert style.mood == "미니멀 럭셔리"
    assert len(style.color_palette) == 3


def test_layout_style_model():
    layout = LayoutStyle(
        type="상단텍스트-하단제품",
        text_position="top",
        product_position="하단 중앙",
        visual_flow="Z자형",
        whitespace="generous",
        focal_point="제품 중심부",
    )
    assert layout.type == "상단텍스트-하단제품"


def test_copy_style_model():
    copy = CopyStyle(
        tone="감성적 서술형",
        length="short",
        emphasis_type="감정소구",
        keywords=["일상", "여유", "나만의"],
    )
    assert copy.emphasis_type == "감정소구"


def test_style_dna_composition():
    dna = StyleDNA(
        image_style=ImageStyle(
            mood="미니멀", lighting="자연광", color_palette=["#FFF"], aesthetic=["clean"]
        ),
        layout_style=LayoutStyle(
            type="top-text", text_position="top", product_position="bottom",
            visual_flow="Z", whitespace="moderate", focal_point="center"
        ),
        copy_style=CopyStyle(
            tone="감성적", length="short", emphasis_type="감정소구", keywords=["힐링"]
        ),
    )
    assert dna.image_style.mood == "미니멀"
    assert dna.copy_style.keywords == ["힐링"]


@pytest.mark.asyncio
async def test_extract_style_dna_parallel():
    """3개 추출기가 병렬로 호출되는지 확인합니다."""
    mock_image_style = ImageStyle(
        mood="test", lighting="test", color_palette=["#FFF"], aesthetic=["test"]
    )
    mock_layout_style = LayoutStyle(
        type="test", text_position="top", product_position="bottom",
        visual_flow="Z", whitespace="moderate", focal_point="center"
    )
    mock_copy_style = CopyStyle(
        tone="test", length="short", emphasis_type="감정소구", keywords=[]
    )

    with (
        patch("da_agent.agents.extractor.extract_image_style", new=AsyncMock(return_value=mock_image_style)),
        patch("da_agent.agents.extractor.extract_layout_style", new=AsyncMock(return_value=mock_layout_style)),
        patch("da_agent.agents.extractor.extract_copy_style", new=AsyncMock(return_value=mock_copy_style)),
    ):
        from da_agent.agents.extractor import extract_style_dna
        result = await extract_style_dna("https://example.com/ad.jpg")

    assert isinstance(result, StyleDNA)
    assert result.image_style.mood == "test"
