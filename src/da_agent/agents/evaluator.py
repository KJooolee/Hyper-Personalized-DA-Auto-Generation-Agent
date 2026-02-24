import base64
import json
from pathlib import Path

from openai import AsyncOpenAI
from PIL import Image

from da_agent.config import get_settings
from da_agent.models.blueprint import AdCopy
from da_agent.models.evaluation import EvaluationResult
from da_agent.utils.image_utils import image_to_bytes

_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "utils/prompt_templates/evaluator.txt"
)


def _image_to_data_url(image: Image.Image) -> str:
    """PIL Image를 base64 data URL로 변환합니다."""
    image_bytes = image_to_bytes(image, format="JPEG")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


async def evaluate_ad(
    generated_image: Image.Image,
    ad_copy: AdCopy,
    brand_identity: dict,
    guidelines: dict,
) -> EvaluationResult:
    """Stage 4: 생성된 광고 이미지를 가이드라인 기준으로 평가합니다.

    이중 검증 경로:
    - Vision 분석: 브랜드 컬러·로고·레이아웃·비주얼 품질 (이미지)
    - 텍스트 직접 검사: 금지어·필수 문구·법적 요소 (ad_copy 문자열)
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        guidelines_required=", ".join(guidelines.get("required_elements", [])),
        guidelines_forbidden=", ".join(guidelines.get("forbidden_elements", [])),
        guidelines_tone=", ".join(guidelines.get("tone_constraints", [])),
        brand_colors=", ".join(brand_identity.get("primary_colors", [])),
        guidelines_media_specs=str(guidelines.get("media_specs", {})),
        copy_headline=ad_copy.headline,
        copy_subheadline=ad_copy.subheadline,
        copy_cta=ad_copy.cta,
        pass_score=settings.eval_pass_score,
    )

    image_data_url = _image_to_data_url(generated_image)

    response = await client.chat.completions.create(
        model=settings.stage4_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url, "detail": "high"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
    )

    raw = json.loads(response.choices[0].message.content)
    return EvaluationResult(**raw)
