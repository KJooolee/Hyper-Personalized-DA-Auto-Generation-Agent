from __future__ import annotations

import base64
import io
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

# 한글 폰트 경로 — 프로젝트 루트 기준 assets/fonts/
_FONT_DIR = Path(__file__).parent.parent.parent.parent / "assets/fonts"
_FONT_REGULAR = _FONT_DIR / "NanumGothic.ttf"
_FONT_BOLD = _FONT_DIR / "NanumGothicBold.ttf"


def _load_korean_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """한글 지원 폰트를 로드합니다. 폰트 파일이 없으면 Pillow 기본 폰트로 fallback."""
    font_path = _FONT_BOLD if bold else _FONT_REGULAR
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size=size)
    # Fallback: 한글이 깨질 수 있음 — assets/fonts/ 에 폰트 파일을 추가하세요
    return ImageFont.load_default(size=size)



def prepare_image_for_api(path_or_url: str) -> str:
    """파일 경로 또는 URL을 OpenAI Vision API가 수락하는 형식으로 변환합니다.

    - HTTPS/HTTP URL → 그대로 반환
    - 로컬 파일 경로 → base64 data URL로 변환 (jpg/png/gif/webp 지원)
    """
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url

    path = Path(path_or_url)
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime = mime_map.get(path.suffix.lower(), "image/jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

async def download_image(url: str) -> Image.Image:
    """URL에서 이미지를 다운로드하여 PIL Image로 반환합니다."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGBA")


async def load_image(path_or_url: str) -> Image.Image:
    """로컬 파일 경로 또는 URL에서 PIL Image를 로드합니다.

    - HTTPS/HTTP URL → httpx로 다운로드
    - 로컬 파일 경로 → PIL로 직접 열기
    """
    if path_or_url.startswith(("http://", "https://")):
        return await download_image(path_or_url)
    return Image.open(path_or_url).convert("RGBA")


def overlay_text(
    image: Image.Image,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font_size: int = 48,
    bold: bool = False,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    line_spacing: int = 8,
) -> Image.Image:
    """이미지에 한글 텍스트를 오버레이합니다. 자동 줄바꿈을 지원합니다."""
    img = image.copy()
    draw = ImageDraw.Draw(img)
    font = _load_korean_font(font_size, bold=bold)

    # 자동 줄바꿈: max_width를 초과하면 줄바꿈
    words = list(text)  # 한글은 글자 단위로 처리
    lines: list[str] = []
    current_line = ""

    for char in words:
        test_line = current_line + char
        bbox = font.getbbox(test_line)
        line_width = bbox[2] - bbox[0]
        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    if current_line:
        lines.append(current_line)

    # 각 줄 렌더링
    line_height = font.getbbox("가")[3] + line_spacing
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_height), line, font=font, fill=color)

    return img


def overlay_logo(
    image: Image.Image,
    logo: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
) -> Image.Image:
    """이미지에 로고를 합성합니다. RGBA 투명도를 지원합니다."""
    img = image.copy()
    logo_resized = logo.resize((width, height), Image.LANCZOS).convert("RGBA")
    img.paste(logo_resized, (x, y), mask=logo_resized.split()[3])
    return img


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """PIL Image를 bytes로 변환합니다."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format=format)
    return buffer.getvalue()
