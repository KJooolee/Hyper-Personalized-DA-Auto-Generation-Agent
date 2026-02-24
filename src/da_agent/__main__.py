"""
사용법:
  uv run python -m da_agent

예시 입력값으로 파이프라인을 실행하는 CLI 진입점.
실제 운영 시에는 아래 example_* 변수를 교체하여 사용.
"""
import asyncio
import logging
import os
import urllib.request
from datetime import datetime

from da_agent.utils.http_client import configure_ssl_globally

# SSL 전역 패치 — 반드시 다른 import보다 먼저 실행 (fal_client 포함 모든 라이브러리에 적용)
configure_ssl_globally()

from da_agent.pipeline import run_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ── 예시 입력값 (실제 사용 시 교체) ──────────────────────────
example_clicked_ad   = ["./example/img/ad_1.png", "./example/img/ad_2.jpg", "./example/img/ad_3.jpg"]  # 사용자가 클릭한 광고 이미지 (병렬 추출)
example_product_img  = "./example/img/product.png"  # 광고할 제품 이미지 URL
example_product_info = {
    "name": "카본 알파 플러스 러닝화",
    "description": "러닝 에너지를 폭발시키는 단 하나의 선택",
    "features": ["최상급 퍼포먼스", "부드러운 쿠셔닝", "통기성이 뛰어난 메쉬 소재"],
}
example_brand = {
    "logo_url": "",
    "primary_colors": ["#1A1A2E", "#E94560"],
    "secondary_colors": ["#F5F5F0"],
}
example_guidelines = {
    "required_elements": ["제품 이미지", "퍼포먼스"],
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

# ── 이미지 저장 로직 수정 ───────────────────────────────
    # output 디렉토리 생성
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 파일명 생성 (타임스탬프 기반)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = os.path.join(output_dir, f"final_da_{timestamp}.png")

    # 1. 바이트(bytes) 데이터가 있는 경우 가장 깔끔하게 저장 가능
    if hasattr(result, 'final_image_bytes') and result.final_image_bytes:
        try:
            with open(output_filename, "wb") as f:
                f.write(result.final_image_bytes)
            print(f"\n💾 최종 이미지가 저장되었습니다: {output_filename}")
        except Exception as e:
            print(f"\n❌ 이미지 바이트 저장 중 오류 발생: {e}")
            
    # 2. final_image가 URL 문자열이거나 Pillow(PIL) 객체인 경우
    elif hasattr(result, 'final_image') and result.final_image:
        image_data = result.final_image
        try:
            if isinstance(image_data, str) and image_data.startswith("http"):
                # URL인 경우 다운로드
                urllib.request.urlretrieve(image_data, output_filename)
                print(f"\n💾 최종 이미지가 저장되었습니다: {output_filename}")
            
            elif hasattr(image_data, 'save'):
                # Pillow Image 객체인 경우
                image_data.save(output_filename)
                print(f"\n💾 최종 이미지가 저장되었습니다: {output_filename}")
            
            else:
                print(f"\n⚠️ 이미지를 저장할 수 없는 형식입니다. (타입: {type(image_data)})")
        except Exception as e:
            print(f"\n❌ 이미지 저장 중 오류 발생: {e}")
            
    else:
        print("\n⚠️ 파이프라인 결과에 저장할 이미지가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())