# MG-CLI

> Monthly Games 프로젝트 관리 CLI 도구

Firebase, 광고 SDK, CI/CD, Analytics, 마케팅, 인프라 구성을 자동화하는 커맨드라인 도구입니다.

## 설치

```bash
# mg-tools 루트에서
pip install -r requirements.txt

# CLI 실행
python -m mg-cli --help
```

## 명령어 체계

```
mg-cli
├── status          # 게임 상태 확인
├── firebase        # Firebase 설정
├── ads             # 광고 SDK 설정
├── config          # 설정 관리
├── batch           # 배치 처리
├── cicd            # CI/CD 도구
├── analytics       # Analytics 설정
├── marketing       # 마케팅 캠페인
└── infra           # 인프라 구성
```

## 상태 확인

```bash
# 전체 게임 상태 요약
python -m mg-cli status

# 특정 게임 상세 상태
python -m mg-cli status --game 0001

# 게임 유형별 필터
python -m mg-cli status --type jrpg_level_a -v
```

## Firebase 설정

```bash
# 단일 게임 Firebase 초기화
python -m mg-cli firebase init --game 0001

# 전체 게임 Firebase 초기화
python -m mg-cli firebase init --all

# Firebase 상태 확인
python -m mg-cli firebase status
```

## 광고 SDK 설정

```bash
# 단일 게임 AdMob 설정
python -m mg-cli ads setup --game 0001

# 전체 게임 AdMob 설정
python -m mg-cli ads setup --all

# 테스트 모드 전환
python -m mg-cli ads test-mode --enable
python -m mg-cli ads test-mode --disable
```

## CI/CD 도구

```bash
# Flutter 테스트 실행
python -m mg-cli cicd test --game 0001
python -m mg-cli cicd test --all

# Flutter 분석
python -m mg-cli cicd analyze --game 0001

# 빌드 (APK/iOS)
python -m mg-cli cicd build --game 0001 --platform android --release

# 의존성 업데이트
python -m mg-cli cicd deps --all
```

## Analytics 도구

```bash
# Analytics 설정 생성
python -m mg-cli analytics setup --game 0001 --output ./analytics

# 표준 KPI 목록
python -m mg-cli analytics kpis

# 표준 이벤트 목록
python -m mg-cli analytics events
```

## 마케팅 도구

```bash
# 마케팅 채널 목록
python -m mg-cli marketing channels

# 캠페인 계획 생성
python -m mg-cli marketing plan --game 0001 --template soft_launch

# 글로벌 론칭 캠페인
python -m mg-cli marketing plan --game 0001 --template global_launch \
    -c google_ads -c facebook_ads -c unity_ads

# Attribution/MMP 설정
python -m mg-cli marketing attribution --game 0001
```

### 캠페인 템플릿

| 템플릿 | 일일 예산 | 기간 | 타겟 지역 | 목표 |
|--------|----------|------|-----------|------|
| soft_launch | $100 | 14일 | PH, TH, VN | 제품 검증 |
| global_launch | $5,000 | 30일 | US, GB, JP 등 | 스케일 |
| retention_focused | $1,000 | 7일 | US, JP, KR | 고품질 유저 |
| monetization_test | $500 | 14일 | US, GB, DE | 수익 최적화 |

## 인프라 도구

```bash
# 사용 가능 서비스 목록
python -m mg-cli infra services

# Terraform 설정 생성
python -m mg-cli infra terraform --game 0001 --env prod \
    -s firebase -s bigquery -s cloud_storage

# GitHub Actions 워크플로우 생성
python -m mg-cli infra github-actions --game 0001 --output .github/workflows/build.yml

# Fastlane 설정 생성
python -m mg-cli infra fastlane --game 0001 --output ./fastlane

# 월간 비용 추정
python -m mg-cli infra costs --env prod \
    -s firebase -s bigquery -s cloud_storage -s cloud_run
```

### 환경별 비용 추정

| 서비스 | Dev | Staging | Prod |
|--------|-----|---------|------|
| Firebase | $0 | $25 | $25 |
| BigQuery | $5 | $5 | $50 |
| Cloud Storage | $5 | $5 | $30 |
| Cloud Run | $0 | $50 | $200 |

## 설정 파일

설정 파일: `config/mg_cli_config.yaml`

```yaml
environment: dev

firebase:
  project_pattern: mg-game-{game_id}
  shared_project: mg-games-dev
  use_shared: true

ads:
  sdk: admob
  test_mode: true
  mediation: false

batch:
  parallel: false
  max_workers: 4
  dry_run: false
```

## 게임 유형

| 유형 | 게임 번호 | 설명 |
|------|----------|------|
| original | 0001-0024 | 초기 게임들 |
| jrpg_level_a | 0025-0036 | JRPG Level A 게임들 |
| casual | 0037+ | 캐주얼 게임들 |

## 서브모듈 구조

| 구조 | 경로 | 게임 |
|------|------|------|
| legacy | common/game | MG-0001 ~ MG-0024 |
| new | libs/mg_common_game | MG-0025+ |

## 개발 상태

- [x] Phase 1: CLI 기본 구조
- [x] Phase 2: Firebase 설정 자동화
- [x] Phase 3: 광고 SDK 설정 자동화
- [x] Phase 4: mg-common-game 통합
- [x] Phase 5: CI/CD 도구
- [x] Phase 6: Analytics/마케팅 도구
- [x] Phase 7: Infra 구성 도구
