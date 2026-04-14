---
name: streamlit-wireframe
description: 가계부 Streamlit 앱의 화면 설계, 와이어프레임, 컴포넌트 사양을 정의하는 스킬. "와이어프레임 만들어줘", "화면 설계", "페이지 구조", "탭 구성", "UI 기획" 등의 요청 시 트리거. 리서치 결과를 기반으로 개발 전 설계도를 생성한다.
---

# 와이어프레임 설계 스킬

## 목표

`_workspace/research_gaegabu.md` 리서치 결과를 바탕으로 Streamlit 가계부 앱의 구체적인 화면 설계서를 만든다. 개발자가 바로 코딩에 착수할 수 있는 수준의 명세를 제공한다.

## 설계 원칙

1. **Streamlit 제약 인식** — 단방향 렌더링. 복잡한 인터랙션보다 명확한 정보 표시에 집중
2. **기존 코드 재활용 최대화** — `/Users/mw/prodect/통장/app.py`에서 이미 구현된 것을 확인하고 변경 범위 최소화
3. **한국어 UI** — 모든 레이블, 버튼, 에러 메시지 한국어
4. **모바일 고려** — 사이드바 필터 + 메인 콘텐츠 분리로 좁은 화면에서도 동작

## 필수 확인 사항

와이어프레임 작성 전 반드시 읽을 파일:
- `_workspace/research_gaegabu.md` — 리서치 인사이트 확인
- `/Users/mw/prodect/통장/app.py` — 현재 구현 상태 확인
- `/Users/mw/prodect/통장/utils.py` — 사용 가능한 함수/데이터 구조 확인

## 출력 형식

`_workspace/wireframe.md`에 저장:

```markdown
# 가계부 Streamlit 앱 화면 설계서

## 전체 구조 (탭/페이지 계층)
## 각 화면 와이어프레임 (ASCII 아트 또는 마크다운 표)
## 컴포넌트 사양
  - 사용할 st.* 컴포넌트
  - 데이터 바인딩 (session_state 키 명시)
  - 이벤트 핸들링 (on_change, on_click)
## 변경 vs 유지 (기존 app.py 기준)
## 개발 우선순위
  - Phase 1 MVP (즉시 구현)
  - Phase 2 고도화 (이후 개선)
## 데이터 흐름도
## 테스트 케이스 기준 (사용자 스토리)
```

## 협업

- 설계 완료 후 `streamlit-dev`에게 SendMessage로 개발 착수 요청
- `qa-engineer`에게 테스트 케이스 기준이 될 사용자 스토리 공유
