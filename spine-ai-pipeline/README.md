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

## 🔄 Hybrid Workflow (스마트 리깅)

AI의 불안정성을 보완하기 위해 **템플릿 매핑(Template Mapping)** 방식을 기본으로 사용합니다.

1.  **AI 이미지 생성 & 정밀 분리**: YOLO-World + SAM 2.1 + Inpainting을 사용하여 파츠를 깔끔하게 분리하고 가려진 부위를 복원합니다.
2.  **템플릿 리깅 (Smart Rigging)**: 분리된 파츠를 미리 검증된 표준 뼈대(Humanoid/Monster)에 매핑합니다. 이때 캐릭터의 등신대(Head-to-Body ratio)를 분석하여 **뼈대 전체 크기를 자동으로 조절**합니다.
3.  **공용 모션 적용**: 표준 뼈대를 사용하므로, 미리 제작된 `idle`, `run`, `attack` 등의 고품질 애니메이션이 깨짐 없이 적용됩니다.

## 사용법

```bash
# 기본 사용 (휴머노이드 템플릿 + 자동 애니메이션)
python scripts/batch_process.py --input_dir images --template humanoid

# 단일 캐릭터 처리 (UI 등 특수 목적)
python scripts/batch_process.py --input_dir single_char --template chibi --preset ui_character
```

## 출력 구조

```
output/
  char_name/
    clean.png       # 배경 제거된 원본
    parts/          # 분리된 파츠 (head.png, body.png...)
    spine/
      skeleton.json # Spine 프로젝트 파일 (Flame/Unity 런타임용)
      skeleton.atlas
      *.png         # 텍스처 아틀라스용 이미지
      # 참고: .spine 파일(에디터용)은 Spine Editor가 설치된 환경에서만 생성됩니다.
      # 게임 적용에는 .json 파일만 있으면 충분합니다.
```

## 사용법

```bash
# 단일 캐릭터
python scripts/gen_illustration.py --config config/char_001.json

# 배치 처리
python scripts/batch_generate.py --input characters.csv
```
