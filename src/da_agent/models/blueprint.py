from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int = Field(description="좌측 상단 x 좌표 (px)")
    y: int = Field(description="좌측 상단 y 좌표 (px)")
    width: int = Field(description="너비 (px)")
    height: int = Field(description="높이 (px)")


class AdCopy(BaseModel):
    headline: str = Field(description="헤드라인 (주 카피)")
    subheadline: str = Field(description="서브카피")
    cta: str = Field(description="행동 유도 문구 (CTA)")


class LayoutGuide(BaseModel):
    product_bbox: BoundingBox = Field(description="제품 배치 영역")
    text_bbox: BoundingBox = Field(description="텍스트 배치 영역")
    logo_bbox: BoundingBox = Field(description="로고 배치 영역")
    background_desc: str = Field(description="배경 구성 방향 설명")


class Blueprint(BaseModel):
    ad_copy: AdCopy = Field(description="생성된 광고 카피 (한글)")
    image_prompt: str = Field(description="FLUX.1 이미지 생성용 영문 프롬프트")
    layout_guide: LayoutGuide = Field(description="레이아웃 좌표 가이드")
