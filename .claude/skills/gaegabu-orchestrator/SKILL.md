---
name: gaegabu-orchestrator
description: 가계부 Streamlit 앱 개발 전체 파이프라인을 조율하는 오케스트레이터 스킬. "가계부 개발 시작", "처음부터 만들어줘", "개발 파이프라인 실행", "리서치부터 배포까지", "하네스 실행", "다시 실행", "재실행", "업데이트", "개선", "기능 추가" 요청 시 반드시 이 스킬을 사용할 것. researcher → planner → streamlit-dev+qa-engineer → deployer 파이프라인을 자동 조율한다.
---

# 가계부 오케스트레이터 스킬

## 실행 모드

**하이브리드 파이프라인:**
- Phase 1 (리서치): 서브 에이전트 (researcher 단독 실행)
- Phase 2 (와이어프레임): 서브 에이전트 (planner 단독 실행)
- Phase 3 (개발+QA): 에이전트 팀 (streamlit-dev ↔ qa-engineer 협업)
- Phase 4 (배포): 서브 에이전트 (deployer 단독 실행)

---

## Phase 0: 컨텍스트 확인

오케스트레이터 시작 시 가장 먼저 실행:

1. `_workspace/` 디렉토리 존재 여부 확인
2. 존재하는 파일 확인:
   - `_workspace/research_gaegabu.md` → 리서치 완료 여부
   - `_workspace/wireframe.md` → 와이어프레임 완료 여부
   - `_workspace/qa_report.md` → QA 완료 여부
   - `_workspace/deploy_report.md` → 배포 완료 여부
3. 사용자 요청 분석:

| 상황 | 실행 모드 |
|------|----------|
| `_workspace/` 미존재 | **초기 실행** — Phase 1부터 전체 실행 |
| `_workspace/` 존재 + 특정 기능 수정 요청 | **부분 재실행** — 해당 Phase만 실행 |
| `_workspace/` 존재 + 새 기능/전체 개선 요청 | **새 실행** — `_workspace/`를 `_workspace_prev/`로 이동 후 전체 실행 |

---

## Phase 1: 리서치 (서브 에이전트)

**실행 모드:** 서브 에이전트

`_workspace/research_gaegabu.md`가 없거나 부분 재실행 요청 시 실행.

```
Agent(
  subagent_type="general-purpose",
  model="opus",
  prompt="""
  가계부 앱 UX·기능·트렌드를 리서치하라.
  
  gaegabu-research 스킬 파일을 읽고 지시에 따라 실행:
  /Users/mw/prodect/통장/.claude/skills/gaegabu-research/SKILL.md
  
  researcher 에이전트 역할로 작업:
  /Users/mw/prodect/통장/.claude/agents/researcher.md
  
  결과를 _workspace/research_gaegabu.md에 저장.
  완료 후 "리서치 완료" 메시지 반환.
  """
)
```

---

## Phase 2: 와이어프레임 (서브 에이전트)

**실행 모드:** 서브 에이전트

Phase 1 완료 후 또는 `_workspace/research_gaegabu.md` 존재 시 실행.

```
Agent(
  subagent_type="general-purpose",
  model="opus",
  prompt="""
  가계부 앱 화면 설계서를 작성하라.
  
  streamlit-wireframe 스킬 파일을 읽고 지시에 따라 실행:
  /Users/mw/prodect/통장/.claude/skills/streamlit-wireframe/SKILL.md
  
  planner 에이전트 역할로 작업:
  /Users/mw/prodect/통장/.claude/agents/planner.md
  
  필수 입력:
  - _workspace/research_gaegabu.md (리서치 결과)
  - /Users/mw/prodect/통장/app.py (현재 구현 상태)
  
  결과를 _workspace/wireframe.md에 저장.
  완료 후 "와이어프레임 완료" 메시지 반환.
  """
)
```

---

## Phase 3: 개발 + QA (에이전트 팀)

**실행 모드:** 에이전트 팀 (streamlit-dev ↔ qa-engineer)

Phase 2 완료 후 실행. streamlit-dev와 qa-engineer가 기능 단위로 협업한다.

### 팀 구성
```
TeamCreate(
  team_name="gaegabu-dev-team",
  members=["streamlit-dev", "qa-engineer"]
)
```

### 작업 할당
```
TaskCreate([
  {
    id: "dev-1",
    title: "utils.py 검토 및 개선",
    assignee: "streamlit-dev",
    description: """
      /Users/mw/prodect/통장/utils.py를 읽고 _workspace/wireframe.md의 요구사항과 비교.
      streamlit-builder 스킬 참조: .claude/skills/streamlit-builder/SKILL.md
      개선 완료 후 qa-engineer에게 SendMessage로 검증 요청.
    """
  },
  {
    id: "qa-1",
    title: "utils.py 검증",
    assignee: "qa-engineer",
    depends_on: ["dev-1"],
    description: """
      python-qa 스킬 참조: .claude/skills/python-qa/SKILL.md
      데이터 레이어 검증 실행. 결과를 _workspace/qa_report.md에 기록.
      통과 시 streamlit-dev에게 app.py 개발 진행 알림.
    """
  },
  {
    id: "dev-2",
    title: "app.py 탭별 기능 구현",
    assignee: "streamlit-dev",
    depends_on: ["qa-1"],
    description: """
      _workspace/wireframe.md 기반으로 5개 탭 구현/개선.
      기능 단위 완료마다 qa-engineer에게 SendMessage.
      주의: st.stop() 사용 금지, if/else 블록 사용.
    """
  },
  {
    id: "qa-2",
    title: "UI 검증",
    assignee: "qa-engineer",
    depends_on: ["dev-2"],
    description: """
      경계면 교차 검증 실행.
      전체 통과 시 deployer에게 배포 준비 완료 알림.
      결과를 _workspace/qa_report.md에 추가 기록.
    """
  }
])
```

### 팀 통신 프로토콜
- streamlit-dev → qa-engineer: `"[기능명] 구현 완료. 검증 요청."`
- qa-engineer → streamlit-dev: `"[기능명] 버그 발견: {버그 내용}. 수정 요청."` 또는 `"[기능명] 검증 통과."`
- qa-engineer → deployer: `"전체 검증 통과. 배포 준비 완료."`

---

## Phase 4: 배포 (서브 에이전트)

**실행 모드:** 서브 에이전트

Phase 3 전체 통과 후 실행. `_workspace/qa_report.md`에 "전체 통과" 기록 확인 후 착수.

```
Agent(
  subagent_type="general-purpose",
  model="opus",
  prompt="""
  가계부 앱을 배포하라.
  
  streamlit-deploy 스킬을 읽고 지시에 따라 실행:
  /Users/mw/prodect/통장/.claude/skills/streamlit-deploy/SKILL.md
  
  deployer 에이전트 역할로 작업:
  /Users/mw/prodect/통장/.claude/agents/deployer.md
  
  전제조건: _workspace/qa_report.md에서 전체 통과 상태 확인 후 착수.
  
  결과를 _workspace/deploy_report.md에 저장.
  완료 후 배포 URL과 함께 "배포 완료" 메시지 반환.
  """
)
```

---

## 에러 핸들링

| 에러 유형 | 처리 방법 |
|----------|----------|
| 리서치 실패 (WebSearch 권한 없음) | 오프라인 리서치(기존 지식 활용)로 대체, qa_report에 명시 |
| 에이전트 타임아웃 | 1회 재시도 후 실패 시 해당 Phase 결과 없이 진행, 리포트에 명시 |
| QA 버그 미해결 | streamlit-dev에게 재할당, 최대 3회 반복 |
| 배포 실패 | 로컬 실행 URL 제공 후 Cloud 배포 가이드 문서화 |

---

## 데이터 흐름

```
Phase 1: researcher → _workspace/research_gaegabu.md
Phase 2: planner ← research_gaegabu.md → _workspace/wireframe.md
Phase 3: streamlit-dev ← wireframe.md → app.py, utils.py
         qa-engineer → _workspace/qa_report.md
Phase 4: deployer ← qa_report.md → _workspace/deploy_report.md
```

---

## 테스트 시나리오

### 정상 흐름
1. `_workspace/` 없는 상태에서 "가계부 개발 시작" 입력
2. Phase 0: 초기 실행 판별
3. Phase 1: researcher가 research_gaegabu.md 생성
4. Phase 2: planner가 wireframe.md 생성
5. Phase 3: 팀이 app.py 구현 + QA 통과
6. Phase 4: deployer가 GitHub push + 배포 URL 반환

### 부분 재실행 흐름
1. `wireframe.md` 존재 상태에서 "대시보드 차트 개선해줘" 입력
2. Phase 0: wireframe.md 존재 확인 → 부분 재실행
3. Phase 3만 실행: streamlit-dev가 차트 수정 → qa-engineer 검증
4. Phase 4: 배포 업데이트

---

## 후속 작업 트리거

다음 표현으로 후속 실행이 트리거됨:
- "다시 실행", "재실행", "업데이트"
- "이 기능만 수정해줘", "탭 추가해줘"
- "이전 결과 기반으로 개선해줘"
- "QA 다시 해줘", "배포 업데이트"
