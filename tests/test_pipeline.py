"""Pipeline 오케스트레이터 테스트 — 평가 루프 동작 확인"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image

from da_agent.models.style_dna import StyleDNA, ImageStyle, LayoutStyle, CopyStyle
from da_agent.models.blueprint import Blueprint, AdCopy, LayoutGuide, BoundingBox
from da_agent.models.evaluation import EvaluationResult, CategoryScores


def _make_style_dna():
    return StyleDNA(
        image_style=ImageStyle(mood="미니멀", lighting="자연광", color_palette=["#FFF"], aesthetic=["clean"]),
        layout_style=LayoutStyle(type="top-text", text_position="top", product_position="bottom", visual_flow="Z", whitespace="moderate", focal_point="center"),
        copy_style=CopyStyle(tone="감성적", length="short", emphasis_type="감정소구", keywords=["일상"]),
    )


def _make_blueprint():
    bbox = BoundingBox(x=0, y=0, width=540, height=200)
    return Blueprint(
        ad_copy=AdCopy(headline="오늘도 특별하게", subheadline="당신을 위한 선택", cta="지금 보기"),
        image_prompt="minimal product photography, soft natural light",
        layout_guide=LayoutGuide(product_bbox=bbox, text_bbox=bbox, logo_bbox=bbox, background_desc="white"),
    )


def _make_eval_result(passed: bool, score: int):
    return EvaluationResult(
        passed=passed,
        score=score,
        category_scores=CategoryScores(brand_compliance=score, copy_compliance=score, layout_compliance=score, visual_quality=score),
        issues=[],
        recommendations=[],
        retry_priority=[],
    )


@pytest.mark.asyncio
async def test_pipeline_passes_on_first_iteration():
    """첫 번째 평가에서 PASS이면 iteration=1로 종료."""
    mock_image = Image.new("RGBA", (1080, 1080), (255, 255, 255, 255))

    with (
        patch("da_agent.pipeline.extract_style_dna", new=AsyncMock(return_value=_make_style_dna())),
        patch("da_agent.pipeline.create_blueprint", new=AsyncMock(return_value=_make_blueprint())),
        patch("da_agent.pipeline.generate_ad_image", new=AsyncMock(return_value=(mock_image, b"bytes"))),
        patch("da_agent.pipeline.evaluate_ad", new=AsyncMock(return_value=_make_eval_result(passed=True, score=90))),
    ):
        from da_agent.pipeline import run_pipeline
        result = await run_pipeline(
            user_clicked_ad_image="https://example.com/ad.jpg",
            product_image="https://example.com/product.jpg",
            product_info={"name": "Test", "description": "Test", "features": []},
            brand_identity={"logo_url": "", "primary_colors": [], "secondary_colors": []},
            guidelines={"required_elements": [], "forbidden_elements": [], "tone_constraints": [], "media_specs": {}},
        )

    assert result.iterations_used == 1
    assert result.eval_result.passed is True


@pytest.mark.asyncio
async def test_pipeline_retries_on_fail():
    """FAIL 후 재시도하여 두 번째에서 PASS하는 루프를 확인합니다."""
    mock_image = Image.new("RGBA", (1080, 1080), (255, 255, 255, 255))
    eval_side_effects = [
        _make_eval_result(passed=False, score=60),
        _make_eval_result(passed=True, score=88),
    ]

    with (
        patch("da_agent.pipeline.extract_style_dna", new=AsyncMock(return_value=_make_style_dna())),
        patch("da_agent.pipeline.create_blueprint", new=AsyncMock(return_value=_make_blueprint())),
        patch("da_agent.pipeline.generate_ad_image", new=AsyncMock(return_value=(mock_image, b"bytes"))),
        patch("da_agent.pipeline.evaluate_ad", new=AsyncMock(side_effect=eval_side_effects)),
    ):
        from da_agent.pipeline import run_pipeline
        result = await run_pipeline(
            user_clicked_ad_image="https://example.com/ad.jpg",
            product_image="https://example.com/product.jpg",
            product_info={"name": "Test", "description": "Test", "features": []},
            brand_identity={"logo_url": "", "primary_colors": [], "secondary_colors": []},
            guidelines={"required_elements": [], "forbidden_elements": [], "tone_constraints": [], "media_specs": {}},
        )

    assert result.iterations_used == 2
    assert result.eval_result.passed is True
    assert len(result.evaluation_history) == 2
