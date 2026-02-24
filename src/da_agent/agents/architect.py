import json
from pathlib import Path

from da_agent.config import get_settings
from da_agent.models.blueprint import Blueprint
from da_agent.models.evaluation import EvaluationResult
from da_agent.models.style_dna import StyleDNA
from da_agent.utils.http_client import create_openai_client

_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "utils/prompt_templates/architect.txt"
)


def _build_feedback_section(feedback: list[EvaluationResult]) -> str:
    if not feedback:
        return ""

    last = feedback[-1]
    issues_text = "\n".join(
        f"- [{issue.severity.value.upper()}] {issue.category} / {issue.item}: {issue.detail}"
        for issue in last.issues
    )
    recommendations_text = "\n".join(
        f"- {rec}" for rec in last.recommendations
    )
    priority_text = ", ".join(last.retry_priority)

    return f"""## Previous Evaluation Feedback (Iteration {len(feedback)})
Score: {last.score}/100 — FAILED

Issues to fix:
{issues_text}

Required improvements:
{recommendations_text}

Top priority fixes: {priority_text}

IMPORTANT: Address ALL issues above in this regeneration.
"""


async def create_blueprint(
    style_dna: StyleDNA,
    product_info: dict,
    brand_identity: dict,
    guidelines: dict,
    feedback: list[EvaluationResult] | None = None,
) -> Blueprint:
    """Stage 2: Style DNA + 광고주 데이터 → 생성 설계도(Blueprint) 작성."""
    settings = get_settings()
    client = create_openai_client()

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    feedback_section = _build_feedback_section(feedback or [])

    prompt = template.format(
        # Image style
        image_mood=style_dna.image_style.mood,
        image_lighting=style_dna.image_style.lighting,
        image_palette=", ".join(style_dna.image_style.color_palette),
        image_aesthetic=", ".join(style_dna.image_style.aesthetic),
        # Layout style
        layout_type=style_dna.layout_style.type,
        layout_text_position=style_dna.layout_style.text_position,
        layout_product_position=style_dna.layout_style.product_position,
        layout_visual_flow=style_dna.layout_style.visual_flow,
        layout_whitespace=style_dna.layout_style.whitespace,
        # Copy style
        copy_tone=style_dna.copy_style.tone,
        copy_length=style_dna.copy_style.length,
        copy_emphasis=style_dna.copy_style.emphasis_type,
        copy_keywords=", ".join(style_dna.copy_style.keywords),
        # Product
        product_name=product_info.get("name", ""),
        product_description=product_info.get("description", ""),
        product_features=", ".join(product_info.get("features", [])),
        product_image_url=product_info.get("image_url", ""),
        # Brand
        brand_primary_colors=", ".join(brand_identity.get("primary_colors", [])),
        brand_secondary_colors=", ".join(brand_identity.get("secondary_colors", [])),
        brand_logo_url=brand_identity.get("logo_url", ""),
        # Guidelines
        guidelines_required=", ".join(guidelines.get("required_elements", [])),
        guidelines_forbidden=", ".join(guidelines.get("forbidden_elements", [])),
        guidelines_tone=", ".join(guidelines.get("tone_constraints", [])),
        guidelines_media_specs=str(guidelines.get("media_specs", {})),
        # Image canvas size
        image_width=settings.image_width,
        image_height=settings.image_height,
        # Feedback loop
        feedback_section=feedback_section,
    )

    response = await client.chat.completions.create(
        model=settings.stage2_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=2048,
    )

    raw = json.loads(response.choices[0].message.content)
    return Blueprint(**raw)
