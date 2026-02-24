from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class CategoryScores(BaseModel):
    brand_compliance: int = Field(ge=0, le=100)
    copy_compliance: int = Field(ge=0, le=100)
    layout_compliance: int = Field(ge=0, le=100)
    visual_quality: int = Field(ge=0, le=100)


class Issue(BaseModel):
    category: str = Field(description="브랜드|카피|레이아웃|비주얼|법적요소")
    item: str = Field(description="구체적 미준수 항목")
    severity: Severity
    detail: str = Field(description="상세 설명 및 수정 방향")


class EvaluationResult(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100, description="종합 점수 (0~100)")
    category_scores: CategoryScores
    issues: list[Issue]
    recommendations: list[str] = Field(description="구체적 수정 방향 목록")
    retry_priority: list[str] = Field(description="재생성 시 우선 반영 항목")
