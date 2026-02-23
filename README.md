# Hyper-Personalized DA Auto-Generation Agent

사용자가 클릭한 광고 이미지에서 선호 스타일을 추출하고, 새로운 제품에 맞춰 초개인화된 광고 이미지를 자동 생성하는 멀티 에이전트 파이프라인입니다.

---

## 핵심 설계 원칙

- **로컬 컴퓨팅 최소화**: 모든 이미지 생성 및 분석은 외부 API로 위임
- **토큰 비용 최적화**: 단순 분류·추출 작업에는 경량 모델, 핵심 창작·설계 단계에만 고성능 모델 사용
- **3단계 파이프라인**: 추출 → 설계 → 생성의 책임 분리

---

## 시스템 아키텍처

```
[사용자 클릭 광고 이미지]
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  Stage 1. The Extractor  — 스타일 DNA 추출            │
│  모델: GPT-4o mini / Claude Haiku (Vision, 저비용)    │
│                                                       │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────┐  │
│  │ Image Style     │  │ Layout Style │  │  Copy   │  │
│  │ Extractor       │  │ Extractor    │  │  Style  │  │
│  │ 분위기·색감·조명 │  │ 구도·배치    │  │  Extractor│ │
│  └────────┬────────┘  └──────┬───────┘  └────┬────┘  │
│           └──────────────────┼───────────────┘        │
│                              │                        │
│                    [Style DNA JSON]                   │
└──────────────────────────────┼────────────────────────┘
                               │
        ┌──────────────────────┤
        │  [신규 입력]          │
        │  - 제품 이미지/정보   │
        │  - 브랜드 아이덴티티  │
        │  - 가이드라인         │
        ▼
┌───────────────────────────────────────────────────────┐
│  Stage 2. The Architect  — 생성 설계도 작성            │
│  모델: GPT-4o (고성능, 핵심 단계)                     │
│                                                       │
│  Input Mixing                                         │
│  ┌──────────────────────────────────────────────┐    │
│  │ Style DNA + 제품 정보 + 브랜드 + 가이드라인   │    │
│  └──────────────────────┬───────────────────────┘    │
│                         │                             │
│          ┌──────────────┼──────────────┐              │
│          ▼              ▼              ▼              │
│    [광고 카피]    [이미지 생성      [레이아웃          │
│     작성         프롬프트(EN)]      가이드/좌표]       │
└──────────┬──────────────┬──────────────┬──────────────┘
           │              │              │
           ▼              ▼              ▼
┌───────────────────────────────────────────────────────┐
│  Stage 3. The Generator  — 최종 이미지 합성            │
│  메인: FLUX.1 [dev] via API (fal.ai / Replicate)      │
│                                                       │
│  ┌──────────────┐    ┌──────────────┐                 │
│  │ FLUX.1 [dev] │    │  ControlNet  │                 │
│  │ 이미지 생성  │◄───│  레이아웃    │                 │
│  │             │    │  준수        │                 │
│  └──────┬───────┘    └──────────────┘                 │
│         │                                             │
│         ▼                                             │
│  ┌──────────────┐                                     │
│  │ 텍스트 합성  │  (카피 오버레이, 위치 정렬)          │
│  │ 후처리       │                                     │
│  └──────┬───────┘                                     │
└─────────┼─────────────────────────────────────────────┘
          │
          ▼
 [최종 개인화 광고 이미지]
```

---

## Stage별 상세 설명

### Stage 1 — The Extractor (스타일 DNA 추출기)

사용자가 클릭한 광고 이미지를 3개 축으로 분해합니다.

| 추출기 | 추출 내용 | 출력 예시 |
|--------|-----------|-----------|
| **Image Style** | 전반적 분위기, 조명, 색감, 미학 | `{ mood: "미니멀", lighting: "자연광", palette: ["#F5F5F0", "#2C2C2C"] }` |
| **Layout Style** | 텍스트·제품 배치 구도, 시선 흐름 | `{ type: "상단텍스트-하단제품", flow: "Z자형", focal: "중앙" }` |
| **Copy Style** | 톤앤매너, 문구 길이, 강조 방식 | `{ tone: "감성적 서술형", length: "short", emphasis: "감정소구" }` |

**비용 최적화**: 세 추출기를 하나의 멀티파트 프롬프트로 묶어 Vision 모델 호출을 **1회**로 통합합니다.

**사용 모델**: `gpt-4o-mini` 또는 `claude-3-haiku` (Vision 지원, 저비용)

---

### Stage 2 — The Architect (생성 설계도 작성)

추출된 Style DNA와 광고주 요청 데이터를 결합하여 Stage 3의 입력이 될 정밀 설계도를 생성합니다.

#### 입력 (Input Mixing)

```
[Stage 1 출력]           [신규 입력]
 Style DNA JSON    +     제품 이미지 URL / 설명
                         브랜드 로고, 필수 컬러
                         가이드라인 (금지어, 필수 요소)
```

#### 출력 (Blueprint)

| 출력물 | 설명 |
|--------|------|
| **광고 카피** | 사용자 선호 톤앤매너로 새 제품에 맞게 작성된 헤드라인·서브카피 |
| **이미지 생성 프롬프트** | FLUX.1 입력용 상세 영문 프롬프트 (색감, 조명, 분위기, 제품 묘사 포함) |
| **레이아웃 좌표** | 제품 영역, 텍스트 영역의 bounding box 또는 Segmentation Map 힌트 |

**사용 모델**: `gpt-4o` (창의적 카피 작성 + 프롬프트 엔지니어링이 핵심이므로 고성능 모델 유지)

---

### Stage 3 — The Generator (최종 이미지 합성)

설계도를 바탕으로 실제 이미지를 생성합니다. 세 가지 제약을 동시에 만족해야 합니다:
- **제품 동일성 유지** (IP-Adapter 또는 Reference Image)
- **레이아웃 준수** (ControlNet Segmentation)
- **텍스트 렌더링** (카피 오버레이 후처리)

#### 권장 구성

```
FLUX.1 [dev]
  + ControlNet (레이아웃 맵 기반 구도 제어)
  + IP-Adapter (제품 이미지 참조)
  → 생성된 배경/구도 이미지

후처리 (Pillow / 디자인 API)
  → 카피 텍스트 오버레이 (폰트, 위치, 컬러 적용)
  → 브랜드 로고 합성

→ 최종 광고 이미지
```

**실행 환경**: fal.ai 또는 Replicate API (로컬 GPU 불필요)

---

## 기술 스택

| 레이어 | 기술 / 서비스 | 선택 이유 |
|--------|---------------|-----------|
| 오케스트레이션 | Python + LangGraph 또는 직접 파이프라인 | 에이전트 상태 관리 |
| Stage 1 Vision | OpenAI `gpt-4o-mini` / Anthropic `claude-3-haiku` | 저비용 Vision |
| Stage 2 LLM | OpenAI `gpt-4o` | 고품질 창의적 생성 |
| Stage 3 Image Gen | FLUX.1 [dev] via `fal.ai` / `Replicate` | 로컬 GPU 불필요 |
| 텍스트 후처리 | Pillow, `python-pptx`, 또는 Canva API | 카피 오버레이 |
| 스토리지 | S3 / GCS (입출력 이미지) | 이미지 URL 기반 처리 |

---

## 비용 최적화 전략

```
Stage 1  ─── gpt-4o-mini vision  ← 1회 호출로 3가지 추출 통합
                                    (개별 3회 → 1회로 약 40% 절감)

Stage 2  ─── gpt-4o              ← 설계도 품질이 전체 성과를 결정,
                                    유일하게 고비용 모델 사용

Stage 3  ─── FLUX.1 API          ← 이미지 1장당 ~$0.03~0.05 수준
                                    (로컬 GPU 운영 비용 대비 절감)

공통     ─── Prompt Caching       ← 브랜드 가이드라인 등 반복 컨텍스트
                                    Anthropic/OpenAI 캐싱 활용
         ─── 배치 처리            ← 다수 사용자 분석 시 Batch API 적용
```

---

## 데이터 흐름 (I/O 명세)

```
입력:
  user_clicked_ad_image: str (URL 또는 base64)
  product_image: str (URL)
  product_info: dict { name, description, features }
  brand_identity: dict { logo_url, primary_colors[], forbidden_elements[] }
  guidelines: dict { required_elements[], tone_constraints[] }

Stage 1 출력 (Style DNA):
  image_style: dict { mood, lighting, color_palette, aesthetic }
  layout_style: dict { type, text_position, product_position, visual_flow }
  copy_style: dict { tone, length, emphasis_type, keywords[] }

Stage 2 출력 (Blueprint):
  ad_copy: dict { headline, subheadline, cta }
  image_prompt: str (영문, FLUX.1 입력용)
  layout_guide: dict { product_bbox, text_bbox, background_desc }

Stage 3 출력:
  final_ad_image: str (URL)
```

---

## 디렉토리 구조 (예정)

```
Hyper-Personalized-DA-Auto-Generation-Agent/
├── agents/
│   ├── extractor.py        # Stage 1: Style DNA 추출
│   ├── architect.py        # Stage 2: 설계도 작성
│   └── generator.py        # Stage 3: 이미지 생성
├── models/
│   ├── style_dna.py        # Pydantic 데이터 모델
│   └── blueprint.py
├── utils/
│   ├── image_utils.py      # 이미지 전처리/후처리
│   └── prompt_templates.py # 프롬프트 템플릿 관리
├── pipeline.py             # 전체 파이프라인 오케스트레이터
├── config.py               # API 키, 모델 설정
├── requirements.txt
└── README.md
```

---

## 개발 로드맵

- [ ] Stage 1: Vision 기반 스타일 DNA 추출기 구현
- [ ] Stage 2: GPT-4o 기반 설계도 생성 (카피 + 프롬프트 + 레이아웃)
- [ ] Stage 3: FLUX.1 API 연동 및 ControlNet 레이아웃 제어
- [ ] 텍스트 오버레이 후처리 모듈
- [ ] 전체 파이프라인 통합 및 테스트
- [ ] 비용 모니터링 및 Batch API 최적화

---

## 라이선스

MIT License — Copyright (c) 2026 Git_ju
