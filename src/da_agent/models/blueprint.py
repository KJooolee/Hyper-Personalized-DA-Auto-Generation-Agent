from pydantic import BaseModel, Field


class AdCopy(BaseModel):
    headline: str = Field(description="헤드라인 (주 카피)")
    subheadline: str = Field(description="서브카피")
    cta: str = Field(description="행동 유도 문구 (CTA)")


class Blueprint(BaseModel):
    ad_copy: AdCopy = Field(description="생성된 광고 카피 (한글)")
    transformation_prompt: str = Field(
        description="FLUX.1 img2img 스타일 변환용 영문 프롬프트 — 제품/구도는 유지하고 분위기·색감을 사용자 선호로 변환"
    )
