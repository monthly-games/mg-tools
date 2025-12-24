# MG Games 서비스 운영 가이드

> 전문 게임 서비스 운영사를 위한 Firebase, Ads, Analytics, Marketing 구성 가이드

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [Firebase 구성](#2-firebase-구성)
3. [광고 SDK 구성](#3-광고-sdk-구성)
4. [Analytics 구성](#4-analytics-구성)
5. [마케팅 인프라](#5-마케팅-인프라)
6. [운영 대시보드](#6-운영-대시보드)
7. [비용 최적화](#7-비용-최적화)
8. [체크리스트](#8-체크리스트)

---

## 1. 아키텍처 개요

### 1.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                        MG Games Platform                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Game 1    │  │   Game 2    │  │   Game N    │   42 Games   │
│  │  (Flutter)  │  │  (Flutter)  │  │  (Flutter)  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    mg-common-game                          │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │  │
│  │  │Analytics│  │   Ads   │  │Firebase │  │  IAP    │       │  │
│  │  │ Manager │  │ Manager │  │ Manager │  │ Manager │       │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │  │
│  └───────┼────────────┼────────────┼────────────┼────────────┘  │
└──────────┼────────────┼────────────┼────────────┼────────────────┘
           │            │            │            │
           ▼            ▼            ▼            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     External Services                             │
├──────────────┬───────────────┬───────────────┬──────────────────┤
│   Firebase   │    AdMob      │   MMP/        │   Payment        │
│   - Analytics│    - AdMob    │   Attribution │   - Google Play  │
│   - Crashlytics│  - Unity Ads│   - Adjust    │   - App Store    │
│   - Remote   │    - ironSource│  - AppsFlyer │                  │
│     Config   │    - AppLovin │   - Singular  │                  │
│   - FCM      │               │               │                  │
└──────────────┴───────────────┴───────────────┴──────────────────┘
           │            │            │            │
           ▼            ▼            ▼            ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Data Warehouse                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      BigQuery                                │ │
│  │   - Firebase Analytics Export                                │ │
│  │   - Ad Revenue Data (SKAN, AdMob Reports)                   │ │
│  │   - Attribution Data                                         │ │
│  │   - IAP Revenue Data                                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      BI & Reporting                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │ Looker   │  │ Tableau  │  │ Metabase │  │ Custom   │         │
│  │ Studio   │  │          │  │          │  │ Dashboard│         │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 환경 구성

| 환경 | 용도 | Firebase 프로젝트 | 특징 |
|------|------|-------------------|------|
| **Development** | 개발/테스트 | `mg-games-dev` (공유) | 테스트 광고, 샌드박스 결제 |
| **Staging** | QA/검증 | `mg-games-stg` (공유) | 실제 광고 (제한), 프로덕션 검증 |
| **Production** | 라이브 서비스 | `mg-game-{id}` (개별) | 실제 광고, 실제 결제 |

### 1.3 프로젝트 전략

**권장: 하이브리드 접근**

```yaml
# 개발/스테이징: 공유 프로젝트 (비용 절감)
dev_project: mg-games-dev
staging_project: mg-games-stg

# 프로덕션: 개별 프로젝트 (격리, 확장성)
prod_projects:
  - mg-game-0001
  - mg-game-0002
  # ... 42개
```

**이유:**
- 개발/스테이징은 트래픽이 적어 공유해도 무방
- 프로덕션은 게임별 격리로 장애 영향 최소화
- 게임별 독립적인 Remote Config, A/B 테스트 가능

---

## 2. Firebase 구성

### 2.1 필수 서비스

| 서비스 | 용도 | 설정 우선순위 |
|--------|------|---------------|
| **Firebase Analytics** | 사용자 행동 분석 | P0 (필수) |
| **Crashlytics** | 크래시 리포팅 | P0 (필수) |
| **Remote Config** | 원격 설정/A/B 테스트 | P0 (필수) |
| **Cloud Messaging** | 푸시 알림 | P1 (권장) |
| **App Check** | 앱 무결성 검증 | P1 (권장) |
| **Performance** | 성능 모니터링 | P2 (선택) |

### 2.2 프로젝트 생성 전략

```bash
# mg-cli를 사용한 자동화
mg-cli firebase create --game 0001              # 단일 프로젝트
mg-cli firebase create --all --batch-size 5     # 전체 (5개씩)

# Firebase CLI 직접 사용
firebase projects:create mg-game-0001 --display-name "MG Game 0001"
firebase apps:create ANDROID --package-name com.monthlygames.game0001 --project mg-game-0001
firebase apps:create IOS --bundle-id com.monthlygames.game0001 --project mg-game-0001
```

### 2.3 Analytics 이벤트 설계

#### 표준 이벤트 (필수)

```dart
// 세션 관련
analytics.logEvent('session_start', {'session_id': sessionId});
analytics.logEvent('session_end', {'duration_seconds': duration});

// 튜토리얼
analytics.logEvent('tutorial_begin');
analytics.logEvent('tutorial_complete', {'duration_seconds': duration});

// 레벨/스테이지
analytics.logEvent('level_start', {'level_id': levelId, 'level_name': name});
analytics.logEvent('level_end', {'level_id': levelId, 'success': success, 'score': score});

// 수익화
analytics.logEvent('ad_impression', {
  'ad_type': 'rewarded',  // interstitial, banner, rewarded
  'ad_unit': 'level_complete_reward',
  'placement': 'level_end',
  'revenue': estimatedRevenue,  // eCPM 기반 추정
});

analytics.logEvent('purchase', {
  'transaction_id': txId,
  'product_id': productId,
  'price': price,
  'currency': 'USD',
});
```

#### 사용자 속성

```dart
// 설정해야 할 사용자 속성
analytics.setUserProperty('first_open_date', firstOpenDate);
analytics.setUserProperty('player_level', playerLevel.toString());
analytics.setUserProperty('total_spend', totalSpend.toString());
analytics.setUserProperty('vip_tier', vipTier);
analytics.setUserProperty('attribution_source', source);  // organic, google_ads, etc.
```

### 2.4 Remote Config 구조

```json
{
  "feature_flags": {
    "new_tutorial_enabled": true,
    "seasonal_event_active": true,
    "ad_frequency_cap": 3
  },
  "game_balance": {
    "gold_multiplier": 1.0,
    "energy_regen_minutes": 5,
    "daily_reward_gems": 50
  },
  "monetization": {
    "interstitial_interval_seconds": 180,
    "rewarded_cooldown_seconds": 30,
    "iap_sale_discount_percent": 20
  },
  "experiments": {
    "onboarding_variant": "control",  // control, variant_a, variant_b
    "price_test_group": "default"
  }
}
```

### 2.5 A/B 테스트 설정

```bash
# Remote Config에서 A/B 테스트 생성
# Firebase Console > Remote Config > Add Parameter > Create Experiment

실험 예시:
- 실험명: tutorial_skip_test
- 변수: tutorial_can_skip (boolean)
- 변형:
  - Control (50%): false
  - Treatment (50%): true
- 목표 메트릭: tutorial_complete, d1_retention
- 최소 샘플: 10,000 users
```

---

## 3. 광고 SDK 구성

### 3.1 Mediation 구조

```
┌─────────────────────────────────────────────────────────┐
│                    AdMob (Primary)                       │
│                    + Mediation                           │
├─────────────────────────────────────────────────────────┤
│  Waterfall Priority:                                     │
│  1. AdMob (직접 수요)                                    │
│  2. Meta Audience Network                                │
│  3. Unity Ads                                            │
│  4. AppLovin MAX                                         │
│  5. ironSource                                           │
│  6. Vungle                                               │
└─────────────────────────────────────────────────────────┘
```

### 3.2 광고 유형별 전략

| 광고 유형 | 배치 | 빈도 제한 | eCPM 기대치 |
|-----------|------|-----------|-------------|
| **Banner** | 하단 고정 | 상시 노출 | $0.5-2 |
| **Interstitial** | 스테이지 클리어 후 | 3분 간격, 하루 10회 | $5-15 |
| **Rewarded** | 보상 획득, 부활 | 쿨다운 30초, 무제한 | $10-30 |
| **Rewarded Interstitial** | 자연스러운 전환점 | 5분 간격, 하루 5회 | $8-20 |

### 3.3 Ad Unit ID 체계

```yaml
# 테스트 환경 (개발용 - Google 공식 테스트 ID)
test_ads:
  android_banner: ca-app-pub-3940256099942544/6300978111
  android_interstitial: ca-app-pub-3940256099942544/1033173712
  android_rewarded: ca-app-pub-3940256099942544/5224354917
  ios_banner: ca-app-pub-3940256099942544/2934735716
  ios_interstitial: ca-app-pub-3940256099942544/4411468910
  ios_rewarded: ca-app-pub-3940256099942544/1712485313

# 프로덕션 환경 (실제 광고 - 게임별)
production_ads:
  # 패턴: ca-app-pub-{publisher_id}/{unit_id}
  # unit_id 규칙: {game_id}{type_code}
  # type_code: 1=banner, 2=interstitial, 3=rewarded

  game_0001:
    android_banner: ca-app-pub-XXXXXXXX/00011
    android_interstitial: ca-app-pub-XXXXXXXX/00012
    android_rewarded: ca-app-pub-XXXXXXXX/00013
```

### 3.4 iOS 14+ SKAN 설정

```xml
<!-- Info.plist에 추가할 SKAdNetwork IDs -->
<key>SKAdNetworkItems</key>
<array>
  <!-- Google -->
  <dict><key>SKAdNetworkIdentifier</key><string>cstr6suwn9.skadnetwork</string></dict>
  <!-- Meta -->
  <dict><key>SKAdNetworkIdentifier</key><string>v9wttpbfk9.skadnetwork</string></dict>
  <!-- Unity -->
  <dict><key>SKAdNetworkIdentifier</key><string>4dzt52r2t5.skadnetwork</string></dict>
  <!-- AppLovin -->
  <dict><key>SKAdNetworkIdentifier</key><string>ludvb6z3bs.skadnetwork</string></dict>
  <!-- ironSource -->
  <dict><key>SKAdNetworkIdentifier</key><string>su67r6k2v3.skadnetwork</string></dict>
  <!-- ... 50+ 네트워크 -->
</array>
```

### 3.5 광고 수익 추적

```dart
// AdMob 수익 이벤트 Firebase로 전송
void onAdRevenuePaid(AdValue adValue) {
  FirebaseAnalytics.instance.logEvent(
    name: 'ad_impression',
    parameters: {
      'ad_platform': 'admob',
      'ad_source': 'admob',  // 또는 mediation 파트너
      'ad_format': 'rewarded',
      'ad_unit_name': 'level_complete_reward',
      'value': adValue.valueMicros / 1000000,
      'currency': adValue.currencyCode,
    },
  );
}
```

---

## 4. Analytics 구성

### 4.1 핵심 KPI 정의

#### Tier 1: 최우선 지표

| KPI | 정의 | 목표치 | 측정 주기 |
|-----|------|--------|-----------|
| **DAU** | 일간 활성 사용자 | 게임별 상이 | 일간 |
| **D1 Retention** | 1일차 잔존율 | >40% | 일간 |
| **D7 Retention** | 7일차 잔존율 | >15% | 주간 |
| **ARPDAU** | DAU당 일 수익 | >$0.10 | 일간 |

#### Tier 2: 수익화 지표

| KPI | 정의 | 목표치 | 측정 주기 |
|-----|------|--------|-----------|
| **ARPU** | 유저당 평균 수익 | >$0.50 (D30) | 월간 |
| **ARPPU** | 결제 유저당 평균 수익 | >$10 | 월간 |
| **Ad eCPM** | 광고 1000회 노출당 수익 | >$10 | 주간 |
| **IAP Conversion** | IAP 결제 전환율 | >2% | 월간 |

#### Tier 3: 마케팅 지표

| KPI | 정의 | 목표치 | 측정 주기 |
|-----|------|--------|-----------|
| **CPI** | 설치당 비용 | <$2.00 (Tier 1 국가) | 캠페인별 |
| **ROAS D7** | 7일차 광고 지출 대비 수익률 | >30% | 주간 |
| **LTV D30** | 30일 생애 가치 | >CPI x 1.5 | 월간 |

### 4.2 BigQuery 데이터 구조

```sql
-- Firebase Analytics 자동 내보내기 테이블
-- 경로: analytics_{game_id}.events_YYYYMMDD

-- 일간 DAU 계산
SELECT
  event_date,
  COUNT(DISTINCT user_pseudo_id) as dau
FROM `mg-game-0001.analytics_123456789.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20241201' AND '20241231'
GROUP BY event_date;

-- D1 Retention 계산
WITH cohorts AS (
  SELECT
    user_pseudo_id,
    MIN(event_date) as install_date
  FROM `mg-game-0001.analytics_*.events_*`
  WHERE event_name = 'first_open'
  GROUP BY user_pseudo_id
)
SELECT
  c.install_date,
  COUNT(DISTINCT c.user_pseudo_id) as cohort_size,
  COUNT(DISTINCT CASE
    WHEN e.event_date = DATE_ADD(c.install_date, INTERVAL 1 DAY)
    THEN e.user_pseudo_id
  END) as d1_retained,
  ROUND(COUNT(DISTINCT CASE
    WHEN e.event_date = DATE_ADD(c.install_date, INTERVAL 1 DAY)
    THEN e.user_pseudo_id
  END) / COUNT(DISTINCT c.user_pseudo_id) * 100, 2) as d1_retention_rate
FROM cohorts c
LEFT JOIN `mg-game-0001.analytics_*.events_*` e
  ON c.user_pseudo_id = e.user_pseudo_id
GROUP BY c.install_date;
```

### 4.3 실시간 모니터링

```yaml
# 알림 설정 (Cloud Monitoring)
alerts:
  - name: crash_rate_spike
    condition: crash_rate > 1%
    window: 1 hour
    notification: slack, email

  - name: revenue_drop
    condition: hourly_revenue < avg_hourly_revenue * 0.5
    window: 2 hours
    notification: slack, pagerduty

  - name: dau_anomaly
    condition: current_dau < yesterday_dau * 0.8
    window: 1 day
    notification: slack
```

---

## 5. 마케팅 인프라

### 5.1 MMP (Mobile Measurement Partner) 설정

#### 권장 MMP

| MMP | 장점 | 가격대 | 추천 시나리오 |
|-----|------|--------|---------------|
| **Adjust** | 정확도, 글로벌 커버리지 | $$$$ | 대규모 UA, 글로벌 론칭 |
| **AppsFlyer** | 다양한 연동, 상세 리포트 | $$$$ | 다채널 캠페인 |
| **Singular** | 비용 효율, 크리에이티브 분석 | $$$ | 중규모 UA |
| **Branch** | 딥링킹 강점, 무료 티어 | $$ | 초기 스타트업 |

#### 기본 설정

```dart
// Adjust SDK 초기화 예시
void initAdjust() {
  final config = AdjustConfig(
    appToken: 'YOUR_APP_TOKEN',
    environment: AdjustEnvironment.production,
  );

  config.setLogLevel(AdjustLogLevel.info);
  config.setAttributionChangedHandler(_onAttributionChanged);
  config.setEventSuccessHandler(_onEventSuccess);

  Adjust.start(config);
}

// 이벤트 전송
void trackPurchase(double revenue, String currency, String transactionId) {
  final event = AdjustEvent('purchase_event_token');
  event.setRevenue(revenue, currency);
  event.setTransactionId(transactionId);
  Adjust.trackEvent(event);
}
```

### 5.2 광고 채널 전략

#### 채널별 특성

| 채널 | 강점 | CPI 범위 | 볼륨 | 품질 |
|------|------|----------|------|------|
| **Google UAC** | 자동 최적화, 규모 | $1-5 | 높음 | 중-높음 |
| **Meta (Facebook)** | 타게팅 정밀도 | $2-8 | 높음 | 중-높음 |
| **Unity Ads** | 게임 유저 타게팅 | $0.5-3 | 중간 | 높음 |
| **AppLovin** | 게임 중심, ROAS 최적화 | $1-4 | 중간 | 높음 |
| **TikTok** | 젊은 층, 바이럴 | $1-5 | 높음 | 중간 |
| **Apple Search Ads** | 의도 기반, 높은 전환 | $2-10 | 낮음 | 매우 높음 |

#### 예산 배분 (글로벌 론칭 기준)

```yaml
# 일일 예산 $5,000 기준
budget_allocation:
  google_uac: 35%         # $1,750/day
  meta_ads: 30%           # $1,500/day
  unity_ads: 15%          # $750/day
  apple_search_ads: 10%   # $500/day
  tiktok: 5%              # $250/day
  other: 5%               # $250/day
```

### 5.3 캠페인 템플릿

#### Soft Launch (제품 검증)

```yaml
soft_launch:
  duration: 14 days
  budget_daily: $100-500
  geo_targets:
    - PH (Philippines)    # Tier 3, 영어권
    - TH (Thailand)       # Tier 3, 동남아
    - VN (Vietnam)        # Tier 3, 볼륨
  goals:
    - D1 Retention > 35%
    - Session Length > 10min
    - Crash Rate < 0.5%
  kpis_to_validate:
    - tutorial_completion_rate
    - ad_engagement_rate
    - session_count_d7
```

#### Global Launch (스케일)

```yaml
global_launch:
  phase_1:  # Week 1-2: 테스트 & 학습
    budget_daily: $1,000
    geo_targets: [US, GB, CA, AU]
    bidding: target_cpi

  phase_2:  # Week 3-4: 확장
    budget_daily: $3,000
    geo_targets: [US, GB, CA, AU, DE, FR, JP, KR]
    bidding: target_roas

  phase_3:  # Week 5+: 최적화
    budget_daily: $5,000+
    geo_targets: ROAS > 100% 국가 확대
    bidding: maximize_conversions
```

### 5.4 크리에이티브 전략

```yaml
creative_framework:
  video_ads:
    formats:
      - 15s portrait (9:16) - TikTok, Reels
      - 30s landscape (16:9) - YouTube, UAC
      - 30s square (1:1) - Facebook Feed

    content_types:
      - gameplay_highlight: 40%
      - character_showcase: 25%
      - feature_demo: 20%
      - ugc_style: 15%

    refresh_cycle: 2 weeks

  playable_ads:
    platforms: [Facebook, Unity, ironSource]
    duration: 15-30 seconds
    cta_timing: after core loop demo
```

---

## 6. 운영 대시보드

### 6.1 대시보드 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    Executive Dashboard                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │   DAU     │  │  Revenue  │  │   ROAS    │  │ LTV/CPI  │ │
│  │  52,340   │  │  $12,456  │  │   135%    │  │   2.1x   │ │
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Game-Level Dashboard                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Game Selector: [MG-0001 ▼]                              ││
│  ├─────────────────────────────────────────────────────────┤│
│  │  DAU Trend        │  Retention Curve   │  Revenue Mix   ││
│  │  [📈 Chart]       │  [📈 Chart]        │  [🥧 Chart]   ││
│  ├─────────────────────────────────────────────────────────┤│
│  │  Top Events       │  Funnel            │  Cohort        ││
│  │  [📊 Table]       │  [📊 Funnel]       │  [📊 Heatmap] ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Operational Dashboard                      │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐ │
│  │  Crash Rate   │  │  API Latency  │  │  Ad Fill Rate   │ │
│  │    0.12%      │  │    245ms      │  │     94.5%       │ │
│  └───────────────┘  └───────────────┘  └─────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Real-time Alerts                                       ││
│  │  - [WARN] Revenue drop in JP market (-15%)             ││
│  │  - [INFO] New version 2.1.0 rollout at 50%             ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Looker Studio 템플릿

```sql
-- 대시보드용 주요 쿼리

-- 1. 일간 KPI 요약
SELECT
  event_date,
  COUNT(DISTINCT user_pseudo_id) as dau,
  SUM(CASE WHEN event_name = 'purchase'
      THEN (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value')
      ELSE 0 END) as iap_revenue,
  SUM(CASE WHEN event_name = 'ad_impression'
      THEN (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value')
      ELSE 0 END) as ad_revenue
FROM `project.analytics.events_*`
WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
GROUP BY event_date
ORDER BY event_date DESC;

-- 2. 리텐션 히트맵
-- (Looker Studio에서 Pivot 테이블로 표현)

-- 3. 수익 믹스
SELECT
  event_date,
  SUM(iap_revenue) as iap,
  SUM(ad_revenue) as ads,
  SUM(iap_revenue) / NULLIF(SUM(iap_revenue) + SUM(ad_revenue), 0) * 100 as iap_percent
FROM daily_revenue
GROUP BY event_date;
```

---

## 7. 비용 최적화

### 7.1 Firebase 비용 관리

| 서비스 | 무료 한도 | 초과 비용 | 최적화 방법 |
|--------|-----------|-----------|-------------|
| Analytics | 무제한 | - | - |
| Crashlytics | 무제한 | - | - |
| Remote Config | 무제한 | - | - |
| BigQuery Export | 10GB/월 무료 | $5/TB | 파티션, 필터링 |
| Cloud Functions | 2M 호출/월 | $0.40/M | 콜드 스타트 최소화 |

### 7.2 환경별 비용 추정

```yaml
# 게임당 월간 비용 추정 (DAU 10,000 기준)

development:
  firebase: $0 (Spark 플랜)
  bigquery: $0 (무료 한도 내)
  total: $0

staging:
  firebase: $25 (Blaze 플랜 최소)
  bigquery: $5
  total: ~$30

production:
  firebase: $25
  bigquery: $50 (분석 쿼리 포함)
  cloud_storage: $30 (에셋, 백업)
  cloud_run: $50-200 (API 서버 규모에 따라)
  total: ~$150-300
```

### 7.3 비용 절감 전략

1. **공유 프로젝트 활용**
   - 개발/스테이징은 `mg-games-dev`, `mg-games-stg` 공유
   - 프로덕션만 개별 프로젝트

2. **BigQuery 최적화**
   - 파티션 테이블 사용 (event_date 기준)
   - 필요한 컬럼만 SELECT
   - 스케줄 쿼리로 집계 테이블 생성

3. **Cloud Functions 최적화**
   - 최소 인스턴스 설정으로 콜드 스타트 감소
   - 리전 최적화 (asia-northeast3 - 서울)

---

## 8. 체크리스트

### 8.1 론칭 전 체크리스트

#### Firebase 설정
- [ ] Firebase 프로젝트 생성 완료
- [ ] Android/iOS 앱 등록 완료
- [ ] google-services.json / GoogleService-Info.plist 적용
- [ ] firebase_options.dart 생성
- [ ] Analytics 이벤트 정의 및 구현
- [ ] Crashlytics 연동 확인
- [ ] Remote Config 초기값 설정
- [ ] BigQuery Export 활성화

#### 광고 설정
- [ ] AdMob 앱 등록
- [ ] 광고 유닛 ID 생성 (배너, 전면, 리워드)
- [ ] Mediation 파트너 설정
- [ ] SKAdNetwork IDs 추가 (iOS)
- [ ] 테스트 광고 → 프로덕션 전환
- [ ] 광고 빈도 제한 설정

#### Analytics/Attribution
- [ ] MMP SDK 연동 (Adjust/AppsFlyer 등)
- [ ] 인앱 이벤트 포스트백 설정
- [ ] 광고 수익 포스트백 설정
- [ ] 딥링크 설정 (옵션)

#### 마케팅
- [ ] 광고 채널 계정 설정
- [ ] 트래킹 링크 생성
- [ ] 초기 크리에이티브 준비 (최소 5세트)
- [ ] 초기 예산 및 입찰 전략 설정

### 8.2 일일 운영 체크리스트

- [ ] DAU/Revenue 이상 징후 확인
- [ ] Crash Rate 모니터링 (<0.5%)
- [ ] 광고 Fill Rate 확인 (>90%)
- [ ] UA 캠페인 ROAS 확인
- [ ] 주요 펀넬 전환율 확인

### 8.3 주간 운영 체크리스트

- [ ] 리텐션 코호트 분석
- [ ] 광고 크리에이티브 성과 분석
- [ ] A/B 테스트 결과 검토
- [ ] 경쟁사 동향 체크
- [ ] 주간 KPI 리포트 작성

---

## 부록

### A. mg-cli 명령어 요약

```bash
# 상태 확인
mg-cli status                           # 전체 게임 상태
mg-cli status --game 0001 -v            # 특정 게임 상세

# Firebase
mg-cli firebase create --game 0001      # 프로젝트 생성
mg-cli firebase configure --game 0001   # FlutterFire 설정
mg-cli firebase init --all              # 템플릿 일괄 적용

# 광고
mg-cli ads setup --game 0001            # AdMob 설정
mg-cli ads test-mode --enable           # 테스트 모드

# Analytics
mg-cli analytics setup --game 0001      # 스키마 생성
mg-cli analytics kpis                   # KPI 목록

# 마케팅
mg-cli marketing channels               # 채널 목록
mg-cli marketing plan --game 0001 --template global_launch

# 인프라
mg-cli infra terraform --game 0001 --env prod
mg-cli infra costs --env prod
```

### B. 유용한 링크

- [Firebase Console](https://console.firebase.google.com/)
- [Google AdMob](https://admob.google.com/)
- [Google Analytics](https://analytics.google.com/)
- [BigQuery Console](https://console.cloud.google.com/bigquery)
- [FlutterFire Documentation](https://firebase.flutter.dev/)
- [Google Mobile Ads Flutter](https://pub.dev/packages/google_mobile_ads)

---

*이 문서는 MG Games 운영팀에서 관리합니다. 최종 업데이트: 2024-12*
