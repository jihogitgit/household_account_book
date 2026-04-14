---
name: python-qa
description: 가계부 app.py와 utils.py의 기능 정확성, 데이터 정합성, UI 일관성을 검증하는 QA 스킬. "테스트해줘", "검증해줘", "버그 찾아줘", "QA 실행", "정합성 확인" 요청 시 트리거. 구현 완료 후 또는 버그 수정 후 반드시 실행한다.
---

# Python QA 스킬

## 목표

`app.py`와 `utils.py`의 기능적 정확성, 데이터 정합성, UI 일관성을 검증한다.

## 검증 방법

Python 스크립트로 직접 실행 (Streamlit 미실행 상태에서):

```python
import sys; sys.path.insert(0, '/Users/mw/prodect/통장')
from utils import load_excel, apply_categorization, build_monthly_kpis, load_overrides
import pandas as pd
```

## 검증 체크리스트

### 데이터 레이어 (utils.py)

**1. categorize() 규칙 검증**
```python
# 통신사 분류 확인 (최우선 규칙)
test_rows = [
    {'적요': 'KT월정액', '거래유형': '출금', '거래금액': 50000},
    {'적요': 'LG유플러스', '거래유형': '출금', '거래금액': 30000},
]
for row in test_rows:
    result = categorize(row, {})
    assert result[0] == '고정지출' and result[1] == '주거/통신', f"통신사 분류 실패: {row['적요']}"
```

**2. build_monthly_kpis() 계산 검증**
```python
kpis = build_monthly_kpis(df, '2026-04')
# 수동 계산과 비교
manual_income = df[(df['연월']=='2026-04') & (df['대분류']=='수입')]['거래금액'].sum()
assert kpis['총수입'] == manual_income, f"수입 불일치: {kpis['총수입']} vs {manual_income}"
```

**3. 내부이체 제외 확인**
```python
# 내부이체는 KPI에서 제외되어야 함
internal_df = df[(df['연월']=='2026-04') & (df['대분류']=='내부이체')]
assert internal_df['거래금액'].sum() not in [kpis['총수입'], kpis['고정지출']], "내부이체 이중계산!"
```

**4. 미분류 항목 0건 확인**
```python
unclassified = df[df['대분류'] == '미분류']
if len(unclassified) > 0:
    print("미분류 항목 발견:", unclassified[['적요', '거래유형']].values)
```

**5. overrides 직렬화 정합성**
```python
import json
overrides = {'테스트적요': {'대분류': '변동지출', '소분류': '식비', 'IsFixed': False}}
save_overrides(overrides)
loaded = load_overrides()
assert loaded == overrides, "overrides 직렬화 오류"
```

### 경계면 검증

**컬럼명 일치 확인**
```python
required_cols = ['대분류', '소분류', 'IsFixed', '거래금액', '거래일시', '날짜', '연월', '통장']
missing = [c for c in required_cols if c not in df.columns]
assert not missing, f"누락 컬럼: {missing}"
```

**KPI 키 일치 확인**
```python
kpis = build_monthly_kpis(df, '2026-04')
required_keys = ['총수입', '고정지출', '변동지출', '경조사', '순수지', 'prev']
missing = [k for k in required_keys if k not in kpis]
assert not missing, f"누락 KPI 키: {missing}"
```

## 버그 리포트 형식

발견된 버그는 `_workspace/qa_report.md`에 기록:

```markdown
## 버그 #{n}
- **재현 단계**: ...
- **기대값**: ...
- **실제값**: ...
- **심각도**: 높음/중간/낮음
- **상태**: 발견 / 수정 완료
```

## 협업

- 기능 단위 완료 알림 수신 → 해당 기능 검증 후 결과를 streamlit-dev에게 SendMessage
- 전체 통과 시 → deployer에게 배포 준비 완료 알림
- `_workspace/qa_report.md`가 존재하면 읽고 이전 버그 수정 여부 재검증부터 시작
