import json
from pathlib import Path

from openai import AsyncOpenAI

from da_agent.config import get_settings
from da_agent.models.style_dna import CopyStyle

_TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "utils/prompt_templates/extractor/copy_style.txt"
)


async def extract_copy_style(image_url: str) -> CopyStyle:
    """Stage 1c: 광고 이미지에서 카피 스타일(톤앤매너·길이·강조방식)을 추출합니다."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
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
                        "text": "Extract the copy style from this ad.",
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=512,
    )

    raw = json.loads(response.choices[0].message.content)
    return CopyStyle(**raw)
