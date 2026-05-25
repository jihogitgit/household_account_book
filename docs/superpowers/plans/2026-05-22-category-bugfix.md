# Category Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CAT_MAP 불일치 수정(경조사/효도 소분류 위치 교정) 및 보안 위험 파일(`categorize.py`) 삭제

**Architecture:** `tabs/uncategorized.py`의 CAT_MAP을 `utils.py` 규칙과 일치시킨다. 변동지출에 잘못 배치된 경조사/효도 소분류를 경조사 대분류로 이동. 미사용 스크립트 삭제.

**Tech Stack:** Python 3, pytest, Streamlit (직접 실행 없이 단위 테스트만)

---

## 파일 구조

| 파일 | 동작 |
|-----|-----|
| `categorize.py` | 삭제 |
| `tabs/uncategorized.py` | CAT_MAP 수정 (변동지출 소분류 2개 제거, 경조사에 효도 추가) |
| `tests/test_cat_map.py` | 신규 생성 — CAT_MAP 구조 단위 테스트 |

---

## Task 1: 테스트 파일 작성 (실패 확인용)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_cat_map.py`

- [ ] **Step 1: tests 디렉토리 및 init 생성**

```bash
mkdir -p /Users/mw/prodect/통장/tests
touch /Users/mw/prodect/통장/tests/__init__.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_cat_map.py` 전체 내용:

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tabs.uncategorized import CAT_MAP


def test_변동지출_소분류_3개만():
    """변동지출에는 생활/배달/병원만 있어야 한다."""
    assert CAT_MAP["변동지출"] == ["생활", "배달", "병원"]


def test_변동지출에_경조사_없음():
    """경조사는 변동지출 소분류가 아니다."""
    assert "경조사" not in CAT_MAP["변동지출"]


def test_변동지출에_효도_없음():
    """효도는 변동지출 소분류가 아니다."""
    assert "효도" not in CAT_MAP["변동지출"]


def test_경조사_소분류에_효도_포함():
    """효도는 경조사 대분류의 소분류여야 한다."""
    assert "효도" in CAT_MAP["경조사"]


def test_경조사_소분류_순서():
    """경조사 소분류는 경조사, 효도 순서여야 한다."""
    assert CAT_MAP["경조사"] == ["경조사", "효도"]


def test_모든_대분류_존재():
    """6개 대분류가 모두 있어야 한다."""
    expected = {"수입", "고정지출", "변동지출", "경조사", "내부이체", "기타"}
    assert expected == set(CAT_MAP.keys())


def test_고정지출_소분류_유지():
    """고정지출 소분류는 변경되지 않아야 한다."""
    assert CAT_MAP["고정지출"] == [
        "월세/이자", "보험", "연금", "청약", "적금/저축", "교통/통신", "공과금", "용돈"
    ]
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
cd /Users/mw/prodect/통장 && python -m pytest tests/test_cat_map.py -v
```

예상 결과: `test_변동지출에_경조사_없음`, `test_변동지출에_효도_없음`, `test_경조사_소분류에_효도_포함`, `test_경조사_소분류_순서` 4개 FAIL

---

## Task 2: CAT_MAP 수정

**Files:**
- Modify: `tabs/uncategorized.py:9-16`

- [ ] **Step 1: CAT_MAP 교체**

`tabs/uncategorized.py`의 CAT_MAP을 아래로 교체:

```python
CAT_MAP = {
    "수입":    ["급여", "이자/캐시백", "기타"],
    "고정지출": ["월세/이자", "보험", "연금", "청약", "적금/저축", "교통/통신", "공과금", "용돈"],
    "변동지출": ["생활", "배달", "병원"],
    "경조사":  ["경조사", "효도"],
    "내부이체": ["생활비 이체", "여행비 이체", "계좌간 이체", "모임 출금"],
    "기타":    ["개인 이체", "기타"],
}
```

- [ ] **Step 2: 테스트 실행 — 전체 통과 확인**

```bash
cd /Users/mw/prodect/통장 && python -m pytest tests/test_cat_map.py -v
```

예상 결과: 7개 모두 PASSED

- [ ] **Step 3: 커밋**

```bash
cd /Users/mw/prodect/통장 && git add tabs/uncategorized.py tests/ && git commit -m "fix: correct CAT_MAP — move 효도 to 경조사, remove from 변동지출"
```

---

## Task 3: `categorize.py` 삭제

**Files:**
- Delete: `categorize.py`

- [ ] **Step 1: 파일이 앱 어디서도 임포트되지 않음을 확인**

```bash
grep -r "import categorize\|from categorize" /Users/mw/prodect/통장 --include="*.py" --exclude-dir=.venv
```

예상 결과: 출력 없음 (임포트 없음)

- [ ] **Step 2: 파일 삭제**

```bash
rm /Users/mw/prodect/통장/categorize.py
```

- [ ] **Step 3: 테스트 재실행 — 삭제 후 회귀 없음 확인**

```bash
cd /Users/mw/prodect/통장 && python -m pytest tests/ -v
```

예상 결과: 7개 모두 PASSED

- [ ] **Step 4: 커밋**

```bash
cd /Users/mw/prodect/통장 && git add -A && git commit -m "chore: delete unused categorize.py (hardcoded password risk)"
```

---

## 완료 기준

1. `python -m pytest tests/test_cat_map.py -v` → 7 passed
2. 미분류 탭 → 변동지출 소분류: ["생활", "배달", "병원"] 3개만 표시
3. 미분류 탭 → 경조사 소분류: ["경조사", "효도"] 2개 표시
4. `categorize.py` 파일 미존재
