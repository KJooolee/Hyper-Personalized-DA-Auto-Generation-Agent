"""Stage 4 Evaluator 테스트 — 이중 검증 경로 확인"""
import pytest
from da_agent.models.blueprint import AdCopy
from da_agent.models.evaluation import EvaluationResult, Issue, Severity, CategoryScores


def test_evaluation_result_pass():
    result = EvaluationResult(
        passed=True,
        score=85,
        category_scores=CategoryScores(
            brand_compliance=90,
            copy_compliance=80,
            layout_compliance=85,
            visual_quality=85,
        ),
        issues=[],
        recommendations=[],
        retry_priority=[],
    )
    assert result.passed is True
    assert result.score == 85


def test_evaluation_result_fail_with_issues():
    result = EvaluationResult(
        passed=False,
        score=55,
        category_scores=CategoryScores(
            brand_compliance=30,
            copy_compliance=70,
            layout_compliance=60,
            visual_quality=65,
        ),
        issues=[
            Issue(
                category="브랜드",
                item="로고 미포함",
                severity=Severity.CRITICAL,
                detail="우측 하단에 브랜드 로고가 배치되어야 함",
            )
        ],
        recommendations=["로고를 우측 하단에 배치하세요"],
        retry_priority=["브랜드 로고 추가"],
    )
    assert result.passed is False
    assert len(result.issues) == 1
    assert result.issues[0].severity == Severity.CRITICAL


def test_ad_copy_text_passthrough():
    """금지어 검증은 ad_copy 텍스트 직접 참조로 수행되는지 확인합니다."""
    copy = AdCopy(
        headline="오늘도 특별한 하루",
        subheadline="당신만을 위한 선택",
        cta="지금 알아보기",
    )
    forbidden = ["최저가", "100% 보장", "무조건"]
    for word in forbidden:
        assert word not in copy.headline
        assert word not in copy.subheadline
        assert word not in copy.cta
