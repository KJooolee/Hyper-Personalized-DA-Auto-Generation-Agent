from pydantic import BaseModel, Field


class ImageStyle(BaseModel):
    mood: str = Field(description="전반적 분위기 (예: 미니멀 럭셔리, 활기찬 라이프스타일)")
    lighting: str = Field(description="조명 방식 (예: 소프트 자연광, 스튜디오 하드라이트)")
    color_palette: list[str] = Field(description="주요 색상 HEX 코드 목록 (최대 5개)")
    aesthetic: list[str] = Field(description="미학 키워드 목록 (예: clean editorial, warm lifestyle)")


class LayoutStyle(BaseModel):
    type: str = Field(description="레이아웃 유형 (예: 상단텍스트-하단제품, 중앙집중형)")
    text_position: str = Field(description="텍스트 위치 (top/bottom/left/right/overlay)")
    product_position: str = Field(description="제품 위치 설명")
    visual_flow: str = Field(description="시선 흐름 패턴 (예: Z자형, F자형, 중앙 확산)")
    whitespace: str = Field(description="여백 사용 수준 (minimal/moderate/generous)")
    focal_point: str = Field(description="시선이 먼저 향하는 지점")


class CopyStyle(BaseModel):
    tone: str = Field(description="톤앤매너 (예: 감성적 서술형, 직접적 혜택 강조형)")
    length: str = Field(description="문구 길이 (ultra-short/short/medium/long)")
    emphasis_type: str = Field(description="강조 방식 (예: 감정소구, 이성소구, 할인강조)")
    keywords: list[str] = Field(description="카피에서 추출된 핵심 감성/주제 키워드")


class StyleDNA(BaseModel):
    image_style: ImageStyle
    layout_style: LayoutStyle
    copy_style: CopyStyle
