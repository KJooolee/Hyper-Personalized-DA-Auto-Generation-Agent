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
example_clicked_ad   = "./axample/img/ad_1.png","./example/img/ad_2.png","./example/img/ad_3.png"  # 사용자가 클릭한 광고 이미지 URL (병렬 추출 테스트용)
example_product_img  = "./example/img/product.png"  # 광고할 제품 이미지 URL
example_product_info = {
    "name": "카본 알파 플러스 러닝화",
    "description": "러닝 에너지를 폭발시키는 단 하나의 선택",
    "features": ["친환경 소재", "미니멀 디자인", "30일 무료 반품"],
}
example_brand = {
    "logo_url": "",
    "primary_colors": ["#1A1A2E", "#E94560"],
    "secondary_colors": ["#F5F5F0"],
}
example_guidelines = {
    "required_elements": ["제품 이미지", "무드"],
    "forbidden_elements": ["최저가", "100% 보장"],
    "tone_constraints": ["과장 표현 금지"],
    "media_specs": {"width": 1660, "height": 260, "format": "PNG"},
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