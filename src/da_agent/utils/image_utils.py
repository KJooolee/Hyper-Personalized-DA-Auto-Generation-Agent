from __future__ import annotations

import base64
import io
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove as rembg_remove

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


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """한글 텍스트를 max_width에 맞게 자동 줄바꿈합니다."""
    lines: list[str] = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    if current_line:
        lines.append(current_line)
    return lines


def measure_text_height(
    text: str,
    max_width: int,
    font_size: int,
    bold: bool = False,
    line_spacing: int = 8,
) -> int:
    """텍스트가 렌더링될 총 높이(px)를 계산합니다 (실제 렌더링 없음)."""
    font = _load_korean_font(font_size, bold=bold)
    lines = _wrap_text(text, font, max_width)
    char_h = font.getbbox("가")
    line_height = (char_h[3] - char_h[1]) + line_spacing
    return len(lines) * line_height


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
    shadow: bool = True,
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 180),
    shadow_offset: int = 2,
) -> Image.Image:
    """이미지에 한글 텍스트를 오버레이합니다.

    - 자동 줄바꿈 (max_width 기준)
    - 선택적 드롭 섀도우로 가독성 향상
    """
    img = image.copy()
    draw = ImageDraw.Draw(img)
    font = _load_korean_font(font_size, bold=bold)

    lines = _wrap_text(text, font, max_width)

    char_h = font.getbbox("가")
    line_height = (char_h[3] - char_h[1]) + line_spacing

    for i, line in enumerate(lines):
        line_y = y + i * line_height
        if shadow:
            draw.text(
                (x + shadow_offset, line_y + shadow_offset),
                line,
                font=font,
                fill=shadow_color,
            )
        draw.text((x, line_y), line, font=font, fill=color)

    return img


def draw_text_zone_background(
    image: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
    color: tuple[int, int, int] = (20, 20, 20),
    alpha: int = 210,
) -> Image.Image:
    """텍스트 영역에 반투명 컬러 배경 밴드를 그립니다.

    실제 DA처럼 배경 이미지 위에 불투명한 컬러 존을 만들어
    텍스트 가독성을 보장합니다.
    """
    img = image.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([(x, y), (x + width, y + height)], fill=(*color, alpha))
    return Image.alpha_composite(img, overlay)


def overlay_cta_button(
    image: Image.Image,
    text: str,
    x: int,
    y: int,
    width: int,
    height: int,
    bg_color: tuple[int, int, int, int] = (255, 80, 0, 255),
    text_color: tuple[int, int, int, int] = (255, 255, 255, 255),
    radius: int = 28,
    font_size: int = 26,
) -> Image.Image:
    """실제 버튼 모양의 CTA를 그립니다.

    둥근 사각형 배경 위에 텍스트를 중앙 정렬하여
    실제 DA의 클릭 유도 버튼처럼 보이게 합니다.
    """
    img = image.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    draw.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=radius,
        fill=bg_color,
    )

    font = _load_korean_font(font_size, bold=True)
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = x + (width - text_w) // 2
    text_y = y + (height - text_h) // 2

    draw.text((text_x, text_y), text, font=font, fill=text_color)

    return Image.alpha_composite(img, overlay)


# rembg 세션은 프로세스 당 한 번만 생성 (모델 재로드 방지)
_rembg_session = new_session("u2net")


def remove_background(image: Image.Image) -> Image.Image:
    """제품 이미지의 배경을 자동으로 제거하여 투명 PNG로 반환합니다.

    u2net 모델을 사용하며, 첫 실행 시 모델을 다운로드합니다 (~170MB).
    이후 실행은 캐시에서 즉시 로드됩니다.
    """
    return rembg_remove(image, session=_rembg_session)


def overlay_product(
    image: Image.Image,
    product: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
) -> Image.Image:
    """실제 제품 이미지를 지정 영역(product_bbox)에 합성합니다.

    - 비율 유지 리사이즈 (contain, 확대·축소 모두 지원)
    - bbox를 캔버스 경계 내로 클램핑 (제품 잘림 방지)
    - 영역 중앙 정렬
    - PNG 투명 배경 지원
    """
    img = image.copy().convert("RGBA")
    product_rgba = product.convert("RGBA")

    # bbox를 캔버스 경계 내로 클램핑
    x = max(0, x)
    y = max(0, y)
    width = min(width, img.width - x)
    height = min(height, img.height - y)
    if width <= 0 or height <= 0:
        return img

    # 비율 유지 스케일 계산 (thumbnail과 달리 확대도 지원)
    pw, ph = product_rgba.size
    scale = min(width / pw, height / ph)
    new_w = max(1, round(pw * scale))
    new_h = max(1, round(ph * scale))
    product_rgba = product_rgba.resize((new_w, new_h), Image.LANCZOS)

    paste_x = x + (width - new_w) // 2
    paste_y = y + (height - new_h) // 2

    img.paste(product_rgba, (paste_x, paste_y), mask=product_rgba.split()[3])
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
