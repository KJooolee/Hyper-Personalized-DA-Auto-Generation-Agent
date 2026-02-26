import json
from pathlib import Path

from PIL import Image

from da_agent.config import get_settings
from da_agent.models.blueprint import AdCopy
from da_agent.models.evaluation import EvaluationResult
from da_agent.utils.http_client import create_anthropic_client
from da_agent.utils.image_utils import pil_to_anthropic_block

_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "utils/prompt_templates/evaluator.txt"
)


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
    client = create_anthropic_client()

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

    response = await client.messages.create(
        model=settings.stage4_model,
        messages=[
            {
                "role": "user",
                "content": [
                    pil_to_anthropic_block(generated_image),
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_tokens=1024,
    )

    raw = json.loads(response.content[0].text)
    return EvaluationResult(**raw)
