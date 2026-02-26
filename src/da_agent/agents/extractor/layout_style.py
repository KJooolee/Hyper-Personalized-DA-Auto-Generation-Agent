import json
from pathlib import Path

from da_agent.config import get_settings
from da_agent.models.style_dna import LayoutStyle
from da_agent.utils.http_client import create_anthropic_client
from da_agent.utils.image_utils import prepare_image_for_anthropic

_TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "utils/prompt_templates/extractor/layout_style.txt"
)


async def extract_layout_style(image_url: str) -> LayoutStyle:
    """Stage 1b: 광고 이미지에서 레이아웃 구도(배치·시선흐름·여백)를 추출합니다."""
    settings = get_settings()
    client = create_anthropic_client()
    system_prompt = _TEMPLATE_PATH.read_text(encoding="utf-8")
    image_block = prepare_image_for_anthropic(image_url)

    response = await client.messages.create(
        model=settings.stage1_model,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    image_block,
                    {"type": "text", "text": "Extract the layout composition from this ad."},
                ],
            }
        ],
        max_tokens=512,
    )

    raw = json.loads(response.content[0].text)
    return LayoutStyle(**raw)
