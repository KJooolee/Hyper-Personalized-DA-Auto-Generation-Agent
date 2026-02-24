"""
사용법:
    uv run python -m da_agent

예시 입력값으로 파이프라인을 실행하는 CLI 진입점.
실제 운영 시에는 아래 example_* 변수를 교체하여 사용.
"""
import asyncio
import logging

from da_agent.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ── 예시 입력값 (실제 사용 시 교체) ──────────────────────────
example_clicked_ad   = "https://example.com/clicked_ad.jpg"
example_product_img  = "https://example.com/product.jpg"
example_product_info = {
    "name": "테스트 제품",
    "description": "일상에 여유를 더하는 라이프스타일 제품",
    "features": ["친환경 소재", "미니멀 디자인", "30일 무료 반품"],
}
example_brand = {
    "logo_url": "",
    "primary_colors": ["#1A1A2E", "#E94560"],
    "secondary_colors": ["#F5F5F0"],
}
example_guidelines = {
    "required_elements": ["브랜드 로고", "가격 정보"],
    "forbidden_elements": ["최저가", "100% 보장"],
    "tone_constraints": ["과장 표현 금지"],
    "media_specs": {"width": 1080, "height": 1080, "format": "JPG"},
}

async def main() -> None:
    result = await run_pipeline(
        user_clicked_ad_image=example_clicked_ad,
        product_image=example_product_img,
        product_info=example_product_info,
        brand_identity=example_brand,
        guidelines=example_guidelines,
    )
    print(f"\n✓ 완료: {result.iterations_used}회 시도, 최종 점수 {result.eval_result.score}/100")
    print(f"  Pass: {result.eval_result.passed}")
    if result.eval_result.issues:
        print("  남은 이슈:")
        for issue in result.eval_result.issues:
            print(f"    [{issue.severity.value}] {issue.item}: {issue.detail}")

if __name__ == "__main__":
    asyncio.run(main())