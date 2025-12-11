
# Spine 2D 캐릭터 제작 자동화 파이프라인 (AI 기반 실험 설계 문서)

> 목적: Spine 2D 기반 캐릭터 제작 파이프라인을 AI를 활용해 자동화하고, 실험 가능하도록 구현 단위까지 설계한다.  
> 대상: Monthly Games 라인업의 Spine 2D 기반 캐릭터 제작 자동화 워크플로우  
> 문서 위치 추천: `mg-common-automation/docs/spine_ai_pipeline.md`

---

## ✅ 전체 플로우 요약

```
[1. 캐릭터 콘셉트 입력]
   ↓
[2. 일러스트 생성 (StableDiffusion)]
   ↓
[3. 파츠 자동 분리 (KomikoAI or SAM)]
   ↓
[4. 리깅 자동 생성 (Spine2D AI)]
   ↓
[5. 애니메이션 자동 적용 (프리셋)]
   ↓
[6. Spine 프로젝트 출력]
   ↓
[7. GitHub + Preview 자동화]
```

---

## 🧩 모듈별 상세 설계

### 1. 캐릭터 콘셉트 입력

- 입력 형식: 텍스트 프롬프트 JSON
```json
{
  "character_id": "char_001",
  "style": "pixel anime",
  "description": "어두운 갑옷을 입은 붉은 눈의 소년 전사, 짧은 머리, 검을 든 공격형 캐릭터",
  "emotion": "냉정함"
}
```

- 자동화 방법:
  - 캐릭터 정의 템플릿 + UI로 입력 (Notion DB, Google Sheet 등)
  - API 또는 CLI로 다음 단계에 전달

---

### 2. 일러스트 생성

- 도구: Stable Diffusion WebUI API (SDXL + anime 체크포인트)
- 입력: 캐릭터 프롬프트
- 출력: PNG 이미지 (1024x1024)

```bash
curl -X POST http://localhost:7860/sdapi/v1/txt2img -d '{
  "prompt": "a pixel anime warrior boy with red eyes and sword, dark armor",
  "steps": 30,
  "width": 1024,
  "height": 1024
}'
```

- 자동화 스크립트 예시: `gen_illustration.py`

---

### 3. 파츠 자동 분리

- 도구:
  - KomikoAI API (권장)
  - 또는 SAM(OpenCV)+Layered PSD 추출기

- 입력: 일러스트 PNG
- 출력: 파츠 이미지 (`head.png`, `arm_L.png` 등), metadata.json

- 예시 출력 구조:
```
char_001/
  parts/
    head.png
    arm_L.png
    arm_R.png
    body.png
    weapon.png
  metadata.json
```

- 자동화 스크립트 예시: `split_parts.py`

---

### 4. 리깅 자동 생성

- 도구: Spine2D AI (GodMode 플랫폼)
- 입력: 파츠 이미지 + metadata.json
- 출력: Spine 프로젝트 파일 (`char_001.json`, `.atlas`, `.png`)

- 자동화 방식:
  - API 기반 업로드 + Spine용 본 자동 배치
  - `preset: humanoid` / `rig_type: warrior`

---

### 5. 애니메이션 자동 생성

- 도구: Spine2D AI 모션 프리셋 or Mixamo → FBX2Spine
- 출력 애니메이션:
  - idle, run, attack1, attack2, hit, die 등

- 자동화 포인트:
  - 애니 프리셋 명령 JSON으로 구성
```json
{
  "animations": ["idle", "run", "attack", "die"],
  "fps": 30,
  "loop_idle": true
}
```

---

### 6. Spine 프로젝트 출력

- 출력 경로 예시:
```
mg-game-000X/
  spine/
    char_001/
      char_001.json
      char_001.atlas
      char_001.png
```

- 자동 썸네일 생성:
  - Spine CLI 또는 Viewer로 WebP / GIF 렌더링

---

### 7. GitHub + CI/CD 연동

- 자동 커밋 구조:
  - `git add spine/char_001/`
  - `git commit -m "[auto] Add character char_001 Spine asset"`
  - `git push origin main`

- CI:
  - 썸네일 생성
  - PNG 최적화 (tinypng CLI)
  - CDN 업로드 / Firebase Hosting 연결

---

## 🔁 반복 구조

- 다수 캐릭터 연속 처리:
```bash
for i in $(cat characters.csv); do
  python gen_illustration.py $i
  python split_parts.py $i
  python rig_character.py $i
  python animate_character.py $i
  python export_spine.py $i
done
```

---

## ⛓ 추천 폴더 구조

```
mg-common-automation/
  spine_ai_pipeline/
    scripts/
      gen_illustration.py
      split_parts.py
      rig_character.py
      animate_character.py
      export_spine.py
    config/
      presets.json
      styles.json
    output/
      char_001/
        ...
```

---

## 🚦실험 주의사항

- SD 일러스트 스타일 통일성을 유지하기 위해 `LoRA` 혹은 `Style Template` 훈련 추천
- 본 분리 정확도는 중복 부위/배경 섞임에 따라 품질 저하
- Spine 출력 전 반드시 누락 파츠, 메시 연결 검증 필요

---
