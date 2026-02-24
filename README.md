# Hyper-Personalized DA Auto-Generation Agent

사용자가 클릭한 광고 이미지에서 선호 스타일을 추출하고, 새로운 제품에 맞춰 초개인화된 광고 이미지를 자동 생성하는 멀티 에이전트 파이프라인입니다.
가이드라인 검증 후 미달 시 자동 재생성하는 **평가-루프(Evaluation Loop)** 를 포함합니다.

---

## 핵심 설계 원칙

- **로컬 컴퓨팅 최소화**: 모든 추론·이미지 생성은 외부 API로 위임
- **토큰 비용 최적화**: 분류·추출·평가 작업에는 경량 모델, 핵심 창작·설계 단계에만 고성능 모델 사용
- **Stage 1 병렬 실행**: 3개 추출기를 독립 비동기 호출로 동시 실행하여 지연 최소화
- **4단계 파이프라인 + 평가 루프**: 추출 → 설계 → 생성 → 평가, 미달 시 피드백 포함 재설계
- **uv 기반 의존성 관리**: `pyproject.toml` + `uv.lock`으로 재현 가능한 환경 보장

---

## Stage별 상세 설명

### Stage 1 — The Extractor (병렬 스타일 DNA 추출)

사용자 클릭 광고 이미지를 3개 축으로 **독립적으로 동시** 분석합니다.
각 추출기는 별도의 Vision API 호출로 실행되며, `asyncio.gather()`로 병렬 처리됩니다.

| 추출기 | 분석 항목 | 출력 예시 |
|--------|-----------|-----------|
| **[1a] Image Style** | 전반적 분위기, 조명 방식, 색상 팔레트, 미학 키워드 | `{ mood: "미니멀 럭셔리", lighting: "소프트 자연광", palette: ["#F0EDE8", "#1A1A1A"], aesthetic: "clean editorial" }` |
| **[1b] Layout Style** | 텍스트·제품 배치 구도, 시선 흐름 패턴, 여백 처리 | `{ type: "상단텍스트-하단제품", flow: "Z자형", whitespace: "넓음", focal: "하단 중앙" }` |
| **[1c] Copy Style** | 톤앤매너, 문구 길이, 강조 방식, 핵심 키워드 | `{ tone: "감성적 서술형", length: "short", emphasis: "감정소구", keywords: ["일상", "여유"] }` |

**병렬 실행 방식**:
```python
image_style, layout_style, copy_style = await asyncio.gather(
    extract_image_style(image_url),   # 1a: 독립 Vision 호출
    extract_layout_style(image_url),  # 1b: 독립 Vision 호출
    extract_copy_style(image_url),    # 1c: 독립 Vision 호출
)
```

**사용 모델**: `gpt-4o-mini` 또는 `claude-3-haiku-20240307` (저비용 Vision)

---

### Stage 2 — The Architect (생성 설계도 작성)

추출된 Style DNA와 광고주 요청 데이터를 결합해 Stage 3의 입력이 될 정밀 설계도를 생성합니다.
**재생성 루프 시**: 직전 Stage 4의 피드백 리포트가 컨텍스트에 추가되어 이전 실패 원인을 반영합니다.

#### 입력

```
[Stage 1 출력]             [광고주 신규 입력]           [Stage 4 피드백 — 루프 시]
 Style DNA JSON      +      제품 이미지 URL / 설명  +    미준수 항목 목록
 image_style                브랜드 로고, 필수 컬러        구체적 수정 방향
 layout_style               가이드라인 (금지/필수)
 copy_style
```

#### 출력 (Blueprint)

| 출력물 | 설명 |
|--------|------|
| **광고 카피** | 헤드라인, 서브카피, CTA — 사용자 선호 톤앤매너로 새 제품에 맞게 작성 |
| **이미지 생성 프롬프트** | FLUX.1 입력용 상세 영문 프롬프트 (브랜드 컬러, 조명, 분위기, 제품 묘사 포함) |
| **레이아웃 가이드** | 제품·텍스트·로고 영역의 bounding box 좌표 + 배경 구성 방향 |

**한국 감성 → 영문 프롬프트 변환**: 한국 광고 특유의 감성 키워드는 FLUX.1이 이해할 수 있는 시각 묘사 영문으로 변환합니다. (예: "새벽 감성" → `"soft pre-dawn atmosphere, misty morning light, blue-hour glow"`)
이 변환 규칙은 `prompt_templates/architect.txt`에 내재화합니다.

**사용 모델**: `gpt-4o` (창의적 카피 + 프롬프트 엔지니어링이 전체 품질 결정)

---

### Stage 3 — The Generator (최종 이미지 합성)

설계도를 바탕으로 세 가지 제약을 동시 만족하는 광고 이미지를 생성합니다.

- **제품 동일성 유지**: IP-Adapter로 제품 이미지 참조
- **레이아웃 준수**: ControlNet + Segmentation Map으로 구도 제어
- **텍스트 렌더링**: 생성 후 Pillow로 카피 오버레이 (이미지 생성 모델의 텍스트 한계 우회)

```
Blueprint
  │
  ├─► FLUX.1 [dev] + ControlNet + IP-Adapter  →  배경/구도 이미지
  │       (via fal.ai / Replicate API)
  │
  └─► Pillow 후처리
          │ 카피 텍스트 오버레이 (폰트, 컬러, 위치 좌표 적용)
          │ 브랜드 로고 합성
          ▼
      합성 이미지 (Stage 4로 전달)
```

**한글 폰트 처리**: Pillow 기본 폰트는 한글을 지원하지 않습니다. `image_utils.py`에서 NanumGothic / NotoSansKR 폰트를 명시적으로 로드하여 한글 카피를 렌더링합니다. 프로젝트에 폰트 파일(`assets/fonts/`)을 포함하며, 가중치(Regular/Bold)별로 로드 가능합니다.

**실행 환경**: fal.ai 또는 Replicate API — 로컬 GPU 불필요

---

### Stage 4 — The Evaluator (가이드라인 적합성 평가 + 루프 제어)

생성된 이미지를 Vision 모델로 분석하여 브랜드/매체 가이드라인 준수 여부를 자동 검증합니다.

#### 검증 항목

| 카테고리 | 검증 방식 | 검증 내용 |
|----------|-----------|-----------|
| 브랜드 | Vision 분석 | 지정 컬러 사용, 로고 위치·크기, 금지 폰트 미사용 |
| 카피 | **텍스트 직접 검사** | 톤앤매너 적합성, 금지어 미포함, 필수 문구 포함 |
| 레이아웃 | Vision 분석 | 여백 규정, 텍스트 가독성, 제품 노출 비율 |
| 매체 규격 | 메타데이터 | 이미지 사이즈, 해상도, 파일 포맷 |
| 법적 요소 | **텍스트 직접 검사** | 필수 고지 문구 포함 여부 |

> **금지어/법적 검증 방식**: 이미지 내 OCR 재시도 대신, Stage 2에서 생성된 카피 텍스트(`ad_copy`)를 문자열 그대로 Evaluator에 전달합니다. 이미지 내 소형·장식 폰트 한글의 OCR 오인식 리스크를 제거하고 검증 신뢰도를 높입니다.

#### 평가 결과 출력

```json
{
  "passed": false,
  "score": 62,
  "issues": [
    {
      "category": "브랜드",
      "item": "로고 미포함",
      "severity": "critical",
      "detail": "우측 하단에 브랜드 로고가 배치되어야 함"
    },
    {
      "category": "카피",
      "item": "금지어 사용",
      "severity": "major",
      "detail": "'최저가' 표현은 매체 가이드라인 위반"
    }
  ],
  "recommendations": [
    "로고를 우측 하단 여백 영역(좌표 x:820-960, y:540-580)에 배치",
    "'최저가' → '합리적인 가격' 또는 구체적 할인율로 교체"
  ],
  "retry_priority": ["브랜드 로고 추가", "금지어 제거"]
}
```

#### 평가 루프 흐름

```
iteration = 1
max_iterations = 3  (환경변수로 설정 가능)

while iteration <= max_iterations:
    blueprint = architect(style_dna, product_info, brand, guidelines, feedback)
    image     = generator(blueprint)
    result    = evaluator(image, blueprint.ad_copy, guidelines)  # 카피 텍스트 직접 전달

    if result.passed:
        return image  ← 최종 광고 이미지 반환
    else:
        feedback = result.issues + result.recommendations
        iteration += 1

return image  ← max 도달 시 최고 점수 이미지 반환 + 경고 로그
```

**사용 모델**: `gpt-4o-mini` Vision (평가는 고창의성 불필요, 저비용 모델로 충분)

---

## 기술 스택

| 레이어 | 기술 / 서비스 | 선택 이유 |
|--------|---------------|-----------|
| 패키지 관리 | `uv` + `pyproject.toml` | 빠른 의존성 해결, 재현 가능한 환경 |
| 비동기 오케스트레이션 | `asyncio` + `httpx` | Stage 1 병렬 실행, 논블로킹 API 호출 |
| Stage 1 Vision | `gpt-4o-mini` / `claude-3-haiku` | 저비용 Vision (3개 독립 호출) |
| Stage 2 LLM | `gpt-4o` | 고품질 카피·프롬프트 생성 |
| Stage 3 Image Gen | FLUX.1 [dev] via `fal.ai` / `Replicate` | 로컬 GPU 불필요 |
| Stage 3 후처리 | `Pillow` + 한글 폰트(NanumGothic/NotoSansKR) | 한글 텍스트 오버레이, 로고 합성 |
| Stage 4 Evaluator | `gpt-4o-mini` Vision | 저비용 이미지 분석·채점 |
| 데이터 검증 | `pydantic` v2 | Stage 간 데이터 모델 타입 보장 |
| 설정 관리 | `pydantic-settings` + `.env` | API 키 환경변수 분리 |

---

## 비용 최적화 전략

```
Stage 1  ─── gpt-4o-mini vision  ← 3개 모듈 각각 독립 호출 (병렬)
                                    저비용 모델이므로 개별 호출이어도 비용 부담 낮음
                                    병렬 처리로 지연 시간은 1회 호출 수준으로 유지

Stage 2  ─── gpt-4o              ← 설계도 품질 = 전체 광고 성과를 결정
                                    유일하게 고비용 모델 사용 (루프 시 재호출 필요)

Stage 3  ─── FLUX.1 API          ← 이미지 1장당 약 $0.03~0.05
                                    로컬 GPU 서버 운영 비용 대비 절감

Stage 4  ─── gpt-4o-mini vision  ← 평가는 패턴 인식 수준, 고성능 모델 불필요
                                    카피 텍스트는 직접 전달 → OCR 비용/오류 제거

공통     ─── Prompt Caching       ← 브랜드 가이드라인 등 반복 시스템 프롬프트
                                    OpenAI / Anthropic Prompt Cache 활용

         ─── 루프 상한            ← max_iterations 설정으로 무한 재생성 방지
                                    기본값 3회 (비용 = Stage 비용 × 최대 3배)
```

---

## 환경변수 (.env)

프로젝트 루트의 `.env` 파일에 API 키를 설정합니다. `.env`는 `.gitignore`에 포함되어 있으며, `.env.example`을 복사하여 사용합니다.

```bash
cp .env.example .env
# .env 파일을 열어 각 API 키를 입력
```

`.env.example`:
```dotenv
# ── LLM API ──────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# ── Image Generation API ─────────────────────────────────────
FAL_KEY=...                        # fal.ai (FLUX.1 사용 시)
REPLICATE_API_TOKEN=r8_...         # Replicate (대안)

# ── Model Configuration ───────────────────────────────────────
STAGE1_MODEL=gpt-4o-mini           # Stage 1 Vision 모델
STAGE2_MODEL=gpt-4o                # Stage 2 Architect 모델
STAGE4_MODEL=gpt-4o-mini           # Stage 4 Evaluator 모델
IMAGE_GEN_MODEL=fal-ai/flux/dev    # Stage 3 이미지 생성 모델

# ── Pipeline Configuration ────────────────────────────────────
MAX_EVAL_ITERATIONS=3              # 평가 루프 최대 반복 횟수
EVAL_PASS_SCORE=80                 # 가이드라인 통과 기준 점수 (0~100)

# ── Image Configuration ───────────────────────────────────────
IMAGE_WIDTH=1080                   # 생성 이미지 너비 (px)
IMAGE_HEIGHT=1080                  # 생성 이미지 높이 (px)
```

---

## 데이터 흐름 (I/O 명세)

```
파이프라인 입력:
  user_clicked_ad_image : str     # 사용자 클릭 광고 이미지 URL
  product_image         : str     # 광고할 제품 이미지 URL
  product_info          : dict    # { name, description, features[] }
  brand_identity        : dict    # { logo_url, primary_colors[], secondary_colors[] }
  guidelines            : dict    # { required_elements[], forbidden_elements[],
                                  #   tone_constraints[], media_specs{} }

Stage 1 출력 — Style DNA:
  image_style  : ImageStyle   # { mood, lighting, color_palette[], aesthetic[] }
  layout_style : LayoutStyle  # { type, text_position, product_position, visual_flow, whitespace }
  copy_style   : CopyStyle    # { tone, length, emphasis_type, keywords[] }

Stage 2 출력 — Blueprint:
  ad_copy      : AdCopy       # { headline, subheadline, cta }  ← 평가 시 직접 전달
  image_prompt : str          # FLUX.1 영문 프롬프트
  layout_guide : LayoutGuide  # { product_bbox, text_bbox, logo_bbox, background_desc }

Stage 3 출력:
  generated_image : str       # 합성 완료 이미지 URL

Stage 4 입력 — 이중 경로:
  generated_image : str       # Vision 분석 대상 (시각 요소 검증)
  ad_copy         : AdCopy    # 텍스트 직접 검사 (금지어·법적 요소 검증)
  guidelines      : dict      # 검증 기준

Stage 4 출력 — EvaluationResult:
  passed          : bool
  score           : int       # 0~100
  issues[]        : Issue     # { category, item, severity, detail }
  recommendations[]: str      # 구체적 수정 방향
  retry_priority[]: str       # 재생성 시 우선 반영 항목

최종 파이프라인 출력:
  final_image     : str       # 최종 광고 이미지 URL
  eval_result     : EvaluationResult
  iterations_used : int       # 실제 사용한 루프 횟수
```

---

## 디렉토리 구조 (uv 프로젝트)

```
Hyper-Personalized-DA-Auto-Generation-Agent/
├── pyproject.toml               # uv 프로젝트 설정, 의존성 정의
├── uv.lock                      # 고정된 의존성 버전 (커밋 대상)
├── .python-version              # Python 버전 고정 (3.12)
├── .env                         # API 키 (gitignore 대상)
├── .env.example                 # API 키 템플릿 (커밋 대상)
├── README.md
├── LICENSE
│
├── assets/
│   └── fonts/                   # 한글 폰트 파일
│       ├── NanumGothic.ttf
│       └── NanumGothicBold.ttf
│
├── src/
│   └── da_agent/
│       ├── __init__.py
│       ├── pipeline.py          # 전체 파이프라인 오케스트레이터 (루프 포함)
│       ├── config.py            # 환경변수 로딩, 모델/파라미터 설정
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── extractor/
│       │   │   ├── __init__.py
│       │   │   ├── image_style.py    # Stage 1a: 이미지 스타일 추출
│       │   │   ├── layout_style.py   # Stage 1b: 레이아웃 스타일 추출
│       │   │   └── copy_style.py     # Stage 1c: 카피 스타일 추출
│       │   ├── architect.py          # Stage 2: 설계도 생성
│       │   ├── generator.py          # Stage 3: 이미지 합성
│       │   └── evaluator.py          # Stage 4: 가이드라인 평가
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── style_dna.py          # ImageStyle, LayoutStyle, CopyStyle, StyleDNA
│       │   ├── blueprint.py          # AdCopy, LayoutGuide, Blueprint
│       │   └── evaluation.py         # Issue, EvaluationResult
│       │
│       └── utils/
│           ├── __init__.py
│           ├── image_utils.py        # 이미지 전처리, 한글 Pillow 후처리
│           └── prompt_templates/
│               ├── extractor/
│               │   ├── image_style.txt
│               │   ├── layout_style.txt
│               │   └── copy_style.txt
│               ├── architect.txt     # 한국 감성 → 영문 변환 규칙 포함
│               └── evaluator.txt
│
└── tests/
    ├── __init__.py
    ├── test_extractor.py
    ├── test_architect.py
    ├── test_generator.py
    └── test_evaluator.py
```

---

## Roadmap

- [ ] Stage 1: 병렬 Vision 추출기 3종 구현 (image / layout / copy)
- [ ] Stage 2: GPT-4o 기반 설계도 생성 (카피 + 이미지 프롬프트 + 레이아웃 좌표)
- [ ] Stage 3: FLUX.1 API 연동, ControlNet 레이아웃 제어, Pillow 한글 후처리
- [ ] Stage 4: 가이드라인 평가 모델 + 이중 검증 경로 (Vision + 텍스트 직접)
- [ ] 평가 루프 오케스트레이터 (max_iterations, pass_score 기반 종료 조건)
- [ ] Pydantic 데이터 모델 정의 (Stage 간 타입 보장)
- [ ] 비용 모니터링 및 토큰 사용량 로깅
- [ ] 통합 테스트

---

## 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/KJooolee/Hyper-Personalized-DA-Auto-Generation-Agent.git
cd Hyper-Personalized-DA-Auto-Generation-Agent

# 2. uv로 가상환경 및 의존성 설치
uv sync

# 3. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력

# 4. 파이프라인 실행
uv run python -m da_agent.pipeline
```

---

## License

MIT License — Copyright (c) 2026 Git_ju
