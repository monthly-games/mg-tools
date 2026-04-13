# MG Tools

> Monthly Games 개발 도구, 파이프라인, 자동화 스크립트 모음

---

## 개요

이 레포지토리는 Monthly Games 프로젝트 전반에서 사용되는 개발 도구, 자동화 스크립트, AI 파이프라인을 포함합니다.

## 구조

```
mg-tools/
├── mg-cli/                 # MG Games 프로젝트 관리 CLI
├── spine-ai-pipeline/      # Spine 2D 캐릭터 자동 생성 파이프라인
├── asset-generator/        # 에셋 자동 생성 도구
├── batch-processor/        # 일괄 처리 스크립트
├── ci-tools/               # CI/CD 관련 도구
├── data-tools/             # 데이터 변환/검증 도구
├── docs/                   # 문서
├── config/                 # 설정 파일
└── scripts/                # 범용 스크립트
```

## 주요 도구

### 0. MG-CLI (NEW)
MG Games 프로젝트 관리 CLI 도구

- Firebase 설정 자동화 (Analytics, Crashlytics, Remote Config)
- 광고 SDK 설정 (AdMob)
- 42개 게임 일괄 처리
- 상태 모니터링 및 리포팅

```bash
# 전체 게임 상태 확인
python -m mg-cli status

# Firebase 초기화
python -m mg-cli firebase init --game 0001

# AdMob 설정
python -m mg-cli ads setup --all
```

### 1. Spine AI Pipeline
AI를 활용한 Spine 2D 캐릭터 자동 생성 파이프라인

- 일러스트 생성 (Stable Diffusion)
- 파츠 자동 분리 (KomikoAI / SAM)
- 리깅 자동 생성 (Spine2D AI)
- 애니메이션 프리셋 적용

### 2. Asset Generator
게임 에셋 자동 생성 도구

- 아이콘 생성
- 썸네일 생성
- 스프라이트 시트 변환

### 6. Prompt Extractor
프롬프트 추출 자동화 도구

- 마크다운 문서 파싱
- 이미지/VFX/오디오 프롬프트 분류 및 추출
- JSON 출력 지원


### 3. Batch Processor
다수 파일/프로젝트 일괄 처리

- **[New] 배경 제거 자동화 (`remove_bg.py`)**: AI를 활용한 이미지 누끼 따기
- 이미지 최적화
- 포맷 변환


### 4. CI Tools
CI/CD 파이프라인 도구

- 빌드 스크립트
- 배포 자동화
- 테스트 실행기

### 5. Data Tools
데이터 처리 도구

- JSON 스키마 검증
- 데이터 마이그레이션
- 밸런스 데이터 변환

---

## 설치

```bash
# Python 환경 설정
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 사용법

각 도구별 상세 사용법은 해당 폴더의 README를 참조하세요.

```bash
# Spine AI Pipeline 예시
python spine-ai-pipeline/scripts/gen_illustration.py --config config.json

# Asset Generator 예시
python asset-generator/scripts/gen_icons.py --input ./sprites --output ./icons
```

---

## 연관 레포지토리

| 레포 | 설명 |
|------|------|
| mg-meta | 프로젝트 메타 정보, 문서 |
| mg-common-game | 공통 게임 라이브러리 |
| mg-common-backend | 공통 백엔드 모듈 |
| mg-common-analytics | 공통 분석 모듈 |

---

## 라이선스

MIT License
