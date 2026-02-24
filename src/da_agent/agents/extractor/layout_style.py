import json
from pathlib import Path

from da_agent.config import get_settings
from da_agent.models.style_dna import LayoutStyle
from da_agent.utils.http_client import create_openai_client

_TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "utils/prompt_templates/extractor/layout_style.txt"
)


async def extract_layout_style(image_url: str) -> LayoutStyle:
    """Stage 1b: 광고 이미지에서 레이아웃 구도(배치·시선흐름·여백)를 추출합니다."""
    settings = get_settings()
    client = create_openai_client()
    system_prompt = _TEMPLATE_PATH.read_text(encoding="utf-8")

    response = await client.chat.completions.create(
        model=settings.stage1_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                    {
                        "type": "text",
                        "text": "Extract the layout composition from this ad.",
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=512,
    )

    raw = json.loads(response.choices[0].message.content)
    return LayoutStyle(**raw)
