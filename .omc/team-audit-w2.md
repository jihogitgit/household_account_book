# Worker 2 감사 보고서: 코드 품질 / 버그 감사

**감사 범위:** `utils.py`, `database.py`, `tabs/` 전체 (`investment.py`, `pension.py`, `savings.py`, `uncategorized.py`), `app.py`  
**감사 일시:** 2026-04-28  
**담당:** Worker 2

---

## 심각 (Critical)

### [C1] `tabs/uncategorized.py:85` — DB 로드 시 `apply_categorization(None, ...)` 크래시
**위치:** `render_uncategorized_tab()` → 저장 버튼 클릭 처리  
**코드:**
```python
st.session_state.df = apply_categorization(
    st.session_state.raw_df, overrides  # raw_df가 None이면 crash
)
```
**문제:** 사이드바 "DB에서 불러오기"로 데이터를 로드하면 `raw_df = None`이 된다. 이 상태에서 미분류 탭에서 적요를 저장하면 `apply_categorization(None, overrides)` 호출 → `None.copy()` → `AttributeError` 런타임 크래시.  
**비교:** `app.py:734`의 카테고리 관리 탭(tab4)은 `if st.session_state.raw_df is not None:` 조건을 체크하지만, `uncategorized.py`는 이 가드가 없다.  
**재현 조건:** DB 불러오기 → 미분류 탭 → 적요 저장 클릭

---

### [C2] `app.py:88-91` — `@st.cache_resource` 다중 사용자 데이터 혼입
**위치:** `_shared_cache()` 함수  
**코드:**
```python
@st.cache_resource(ttl=900)
def _shared_cache():
    return {"raw_df": None, "df": None}
```
**문제:** `st.cache_resource`는 서버 프로세스 전체에서 공유되는 싱글턴이다. 다중 사용자 환경(Streamlit Cloud 등)에서 사용자 A가 데이터를 로드하면 `_c["df"] = user_A_df`로 덮어써져, 사용자 B가 새로고침 시 사용자 A의 거래내역을 그대로 보게 된다. 개인 금융 데이터 유출 위험.  
**수정 방향:** `st.session_state` 단독 사용 또는 세션 ID를 키로 하는 별도 캐싱.

---

### [C3] `database.py:131-132` — `save_transactions()` 전체 예외 묵음 처리
**위치:** `Database.save_transactions()` 루프 내부  
**코드:**
```python
except Exception:
    pass
```
**문제:** 디스크 풀, 타입 오류, 스키마 불일치 등 모든 예외가 묵음 처리된다. `inserted` 카운트가 실제 저장 수와 달라질 수 있고, 저장 실패 원인을 전혀 알 수 없다. 사용자는 "XX건 저장 완료" 메시지를 받지만 실제로는 0건 저장될 수 있다.

---

### [C4] `database.py:29` — UNIQUE 제약 조건이 정상 중복 거래를 삭제
**위치:** `_SCHEMA` transactions 테이블  
**코드:**
```sql
UNIQUE(날짜, 통장, 적요, 거래금액)
```
**문제:** 같은 날 같은 통장에서 동일 가맹점에 동일 금액으로 두 번 결제한 경우 (예: 카페 2회 방문, 같은 금액) 두 번째 건이 `INSERT OR IGNORE`로 묵음 드롭된다. 실제 거래 수와 앱 집계가 달라짐.

---

## 중간 (Medium)

### [M1] `utils.py:149-153` — 분류 규칙 평가 예외 전체 묵음 처리
**위치:** `categorize()` 함수  
**코드:**
```python
try:
    if cond(row):
        return 대분류, 소분류, is_fixed
except Exception:
    pass
```
**문제:** 규칙 람다 실행 중 발생하는 `KeyError`, `TypeError` 등이 묵음 처리되어 모든 규칙이 실패한 것처럼 보이고, 실제로는 분류 가능한 거래가 "미분류"로 빠진다. 디버깅이 불가능하다.

---

### [M2] `database.py:108-133` — 트랜잭션 행 단위 INSERT (성능)
**위치:** `Database.save_transactions()` 루프  
**문제:** DataFrame 행을 한 건씩 `execute()`로 삽입하며 매 행마다 `SELECT changes()`를 추가 실행한다. 거래 내역 1,000건 로드 시 약 2,000회 DB 쿼리 발생. `executemany` + 배치 inserted 카운트로 교체해야 한다.

---

### [M3] `tabs/savings.py:111-117` — 모든 저축 목표에 동일한 `actual_saving` 적용
**위치:** `render_savings_tab()` 목표 달성 진행도 섹션  
**코드:**
```python
for _, row in goals.iterrows():
    goal_amt = float(row["월목표금액"])
    ratio = actual_saving / goal_amt if goal_amt > 0 else 0
    st.progress(...)
```
**문제:** `actual_saving`은 총 적금/저축 합계 한 값을 모든 목표에 그대로 사용한다. 목표가 여러 개라면 동일한 금액이 각 목표 대비 진행도로 계산되어 허수 비율(>100%)이 나온다. 목표별 실제 달성액을 별도 추적하는 구조가 없어 진행도 의미가 없다.

---

### [M4] `database.py:181` — `upsert_asset()` 필수 키 직접 접근
**위치:** `Database.upsert_asset()` UPDATE 분기  
**코드:**
```python
asset["자산명"],  # KeyError if missing
float(asset.get("매입가", 0)),  # ValueError if non-numeric string
```
**문제:** `asset["자산명"]`은 `.get()` 없이 직접 접근하므로 키 누락 시 `KeyError`. `float()` 변환에 예외 처리 없어 비정상 입력 시 `ValueError`로 전체 페이지 오류.

---

### [M5] `app.py:493-503` — 지출 내역 탭 대분류 필터 미선택 시 전체 표시
**위치:** tab2 (지출 내역)  
**코드:**
```python
f_cat = st.multiselect("대분류", 대분류_opts, key="exp_cat")
...
if f_cat:
    filtered = filtered[filtered["대분류"].isin(f_cat)]
```
**문제:** 사용자가 multiselect를 모두 해제하면 `f_cat = []`이 되고 필터가 적용되지 않는다. 결과적으로 "수입", "내부이체" 등 지출이 아닌 모든 거래가 "지출 내역" 탭에 표시된다. 의도와 반대의 동작.

---

### [M6] `database.py:97-100` — WAL 모드 미설정, concurrent write 잠금 위험
**위치:** `Database._connect()`  
**문제:** SQLite 기본 journal 모드 사용으로 동시 쓰기 발생 시 `database is locked` 오류 가능. Streamlit 앱 특성상 빠른 재렌더링 중 write가 겹칠 수 있다. `PRAGMA journal_mode=WAL` 설정 권장.

---

### [M7] `app.py:419-425` — `build_monthly_kpis()` 대시보드에서 6회 반복 호출
**위치:** tab1 최근 6개월 추이 차트  
**문제:** 매 렌더링마다 전체 DataFrame을 순회하는 `build_monthly_kpis()`를 6번 호출. 데이터가 많아질수록 대시보드 렌더링 속도 저하. 한 번의 벡터화 계산으로 6개월치를 한 번에 산출해야 한다.

---

## 낮음 (Low)

### [L1] `utils.py:127-131` — `detect_account_name()` 하드코딩된 4개 통장명
**문제:** "생활비", "경조사", "급여통장", "비상금" 외의 통장 파일은 파일명 정제 결과 그대로 `_통장` 컬럼에 들어가 분류 규칙(`r["_통장"] == "급여통장"` 등)이 불일치할 수 있다.

---

### [L2] `database.py:94-95` — `migrate_from_json()` 매 인스턴스 생성마다 호출
**문제:** `Database.__init__`에서 매번 2회 DB 쿼리(overrides, budgets count)를 실행한다. `get_db()` 싱글턴이 있으나 초기 생성 비용이 존재.

---

### [L3] `tabs/uncategorized.py:39` — `groupby`에서 "거래 유형" 컬럼 의존
**코드:**
```python
거래유형=("거래 유형", "first"),
```
**문제:** DB 불러오기 경로에서 `_normalize_db_df`가 "거래 유형"으로 정상 rename하지만, 향후 스키마 변경 시 KeyError 취약점. 컬럼 존재 여부 확인 없음.

---

### [L4] `tabs/savings.py:126-132` — 연간 예상 저축액이 최신 1개월 기준 단순 곱
**코드:**
```python
yearly_actual = actual_saving * 12
```
**문제:** 가장 최근 1개월 저축액을 12배로 단순 추산. 계절성/일회성 지출이 있는 달이 최신 달일 경우 연간 예상치 왜곡.

---

### [L5] `utils.py:104-121` — `decrypt()` BytesIO 에러 시 메모리 누수
**문제:** `of.decrypt(dec)` 실패 시 `finally` 블록에서 파일 핸들만 닫히고 `dec` (BytesIO)는 GC에 의존해 정리된다. 대용량 Excel 파일 처리 중 반복 실패 시 메모리 일시 증가 가능.

---

## 요약 테이블

| ID | 파일 | 심각도 | 설명 |
|----|------|--------|------|
| C1 | tabs/uncategorized.py:85 | 심각 | DB 로드 후 저장 시 raw_df=None → 크래시 |
| C2 | app.py:88-91 | 심각 | cache_resource 다중 사용자 데이터 혼입 |
| C3 | database.py:131-132 | 심각 | save_transactions 전체 예외 묵음 |
| C4 | database.py:29 | 심각 | UNIQUE 제약 정상 중복 거래 삭제 |
| M1 | utils.py:149-153 | 중간 | 분류 규칙 예외 묵음 → 미분류 증가 |
| M2 | database.py:108-133 | 중간 | 행 단위 INSERT 성능 문제 |
| M3 | tabs/savings.py:111-117 | 중간 | 모든 목표에 동일 actual_saving 적용 |
| M4 | database.py:181 | 중간 | upsert_asset 직접 키 접근 KeyError |
| M5 | app.py:493-503 | 중간 | 지출 필터 해제 시 수입/내부이체 노출 |
| M6 | database.py:97-100 | 중간 | WAL 미설정 concurrent lock 위험 |
| M7 | app.py:419-425 | 중간 | build_monthly_kpis 6회 반복 호출 |
| L1 | utils.py:127-131 | 낮음 | detect_account_name 4개 통장만 지원 |
| L2 | database.py:94-95 | 낮음 | migrate_from_json 매 init 실행 |
| L3 | tabs/uncategorized.py:39 | 낮음 | "거래 유형" 컬럼 하드코딩 의존 |
| L4 | tabs/savings.py:126-132 | 낮음 | 연간 예상 저축 1개월 단순 12배 |
| L5 | utils.py:104-121 | 낮음 | BytesIO 에러 시 메모리 누수 |
