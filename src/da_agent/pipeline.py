"""
메인 파이프라인 오케스트레이터

Stage 1 (병렬 추출) → Stage 2 (설계도 작성) → Stage 3 (이미지 생성)
→ Stage 4 (가이드라인 평가) → PASS: 완료 / FAIL: 피드백 포함 Stage 2 재진입
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from PIL import Image

from da_agent.agents.architect import create_blueprint
from da_agent.agents.evaluator import evaluate_ad
from da_agent.agents.extractor import extract_style_dna
from da_agent.agents.generator import generate_ad_image
from da_agent.config import get_settings
from da_agent.models.evaluation import EvaluationResult
from da_agent.models.style_dna import StyleDNA

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    final_image: Image.Image
    final_image_bytes: bytes
    style_dna: StyleDNA
    eval_result: EvaluationResult
    iterations_used: int
    evaluation_history: list[EvaluationResult] = field(default_factory=list)


async def run_pipeline(
    user_clicked_ad_image: str | list[str],
    product_image: str,
    product_info: dict,
    brand_identity: dict,
    guidelines: dict,
) -> PipelineResult:
    """
    초개인화 DA 자동 생성 파이프라인을 실행합니다.

    Args:
        user_clicked_ad_image: 사용자가 클릭한 광고 이미지 URL
        product_image: 광고할 제품 이미지 URL
        product_info: { name, description, features[], image_url }
        brand_identity: { logo_url, primary_colors[], secondary_colors[] }
        guidelines: { required_elements[], forbidden_elements[],
                      tone_constraints[], media_specs{} }

    Returns:
        PipelineResult (최종 이미지, 평가 결과, 반복 횟수 포함)
    """
    settings = get_settings()
    product_info = {**product_info, "image_url": product_image}

    # ── Stage 1: 병렬 스타일 DNA 추출 ───────────────────────────────────────
    logger.info("Stage 1: extracting style DNA from user-clicked ad...")
    style_dna = await extract_style_dna(user_clicked_ad_image)
    logger.info("Style DNA extracted: %s", style_dna.model_dump())

    # ── Stage 2 → 3 → 4 평가 루프 ───────────────────────────────────────────
    evaluation_history: list[EvaluationResult] = []
    best_image: Image.Image | None = None
    best_bytes: bytes | None = None
    best_eval: EvaluationResult | None = None
    best_score = -1

    for iteration in range(1, settings.max_eval_iterations + 1):
        logger.info("Iteration %d/%d", iteration, settings.max_eval_iterations)

        # Stage 2: 설계도 작성 (재생성 시 이전 피드백 포함)
        logger.info("Stage 2: creating blueprint...")
        blueprint = await create_blueprint(
            style_dna=style_dna,
            product_info=product_info,
            brand_identity=brand_identity,
            guidelines=guidelines,
            feedback=evaluation_history if evaluation_history else None,
        )
        logger.info("Blueprint ad_copy: %s", blueprint.ad_copy.model_dump())

        # Stage 3: 이미지 생성 + 카피/로고 합성
        logger.info("Stage 3: generating ad image...")
        generated_image, image_bytes = await generate_ad_image(blueprint, brand_identity)

        # Stage 4: 가이드라인 적합성 평가 (이중 검증: Vision + 텍스트 직접)
        logger.info("Stage 4: evaluating ad against guidelines...")
        eval_result = await evaluate_ad(
            generated_image=generated_image,
            ad_copy=blueprint.ad_copy,   # ← 카피 텍스트를 직접 전달 (OCR 우회)
            brand_identity=brand_identity,
            guidelines=guidelines,
        )
        evaluation_history.append(eval_result)
        logger.info(
            "Evaluation score: %d/100 — %s",
            eval_result.score,
            "PASS" if eval_result.passed else "FAIL",
        )

        # 최고 점수 이미지 보관
        if eval_result.score > best_score:
            best_score = eval_result.score
            best_image = generated_image
            best_bytes = image_bytes
            best_eval = eval_result

        if eval_result.passed:
            logger.info("Passed on iteration %d", iteration)
            return PipelineResult(
                final_image=generated_image,
                final_image_bytes=image_bytes,
                style_dna=style_dna,
                eval_result=eval_result,
                iterations_used=iteration,
                evaluation_history=evaluation_history,
            )

        logger.warning(
            "Iteration %d failed (score=%d). Issues: %s",
            iteration,
            eval_result.score,
            [i.item for i in eval_result.issues],
        )

    # max_iterations 도달: 최고 점수 이미지 반환 + 경고
    logger.warning(
        "Max iterations (%d) reached without passing. "
        "Returning best result (score=%d).",
        settings.max_eval_iterations,
        best_score,
    )
    return PipelineResult(
        final_image=best_image,
        final_image_bytes=best_bytes,
        style_dna=style_dna,
        eval_result=best_eval,
        iterations_used=settings.max_eval_iterations,
        evaluation_history=evaluation_history,
    )
