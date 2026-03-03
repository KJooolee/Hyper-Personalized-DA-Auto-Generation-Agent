from pydantic import BaseModel, Field


class BBox(BaseModel):
    x: int = Field(description="좌측 상단 x 좌표 (px)")
    y: int = Field(description="좌측 상단 y 좌표 (px)")
    width: int = Field(description="너비 (px)")
    height: int = Field(description="높이 (px)")


class AdLayout(BaseModel):
    """Vision LLM이 실제 생성 이미지를 보고 결정하는 카피·로고 배치 좌표."""

    text_zone: BBox = Field(
        description="헤드라인·서브카피·CTA를 배치할 영역 (제품과 겹치지 않는 배경 공간)"
    )
    logo_zone: BBox = Field(
        description="브랜드 로고를 배치할 영역 (모서리 선호)"
    )
    text_color: str = Field(
        description="텍스트 색상: 'white'(어두운 배경) 또는 'dark'(밝은 배경)"
    )
