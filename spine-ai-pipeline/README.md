# Spine AI Pipeline

> AI를 활용한 Spine 2D 캐릭터 자동 생성 파이프라인

## 전체 플로우

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

## 스크립트

| 스크립트 | 설명 |
|---------|------|
| gen_illustration.py | Stable Diffusion으로 일러스트 생성 |
| split_parts.py | 파츠 자동 분리 |
| rig_character.py | 리깅 자동 생성 |
| animate_character.py | 애니메이션 적용 |
| export_spine.py | Spine 프로젝트 출력 |

## 입력 형식

```json
{
  "character_id": "char_001",
  "style": "pixel anime",
  "description": "어두운 갑옷을 입은 붉은 눈의 소년 전사",
  "emotion": "냉정함"
}
```

## 출력 구조

```
output/
  char_001/
    parts/
      head.png
      arm_L.png
      arm_R.png
      body.png
      weapon.png
    spine/
      char_001.json
      char_001.atlas
      char_001.png
    metadata.json
```

## 사용법

```bash
# 단일 캐릭터
python scripts/gen_illustration.py --config config/char_001.json

# 배치 처리
python scripts/batch_generate.py --input characters.csv
```
