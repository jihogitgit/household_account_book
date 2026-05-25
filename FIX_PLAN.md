# 가계부 앱 수정·개발 계획

> 작성일: 2026-04-28  
> 기준: 3-워커 감사 결과 종합  
> 불변: 대분류/소분류 분류 체계는 현행 유지

---

## Phase 1 — 크래시·데이터 무결성 (즉시)

---

### 1-1. DB 로드 후 미분류 탭 저장 시 크래시

**파일:** `tabs/uncategorized.py:85`  
**원인:** "DB에서 불러오기"로 데이터를 로드하면 `raw_df=None`이 된다. 이 상태에서 저장 버튼을 누르면 `apply_categorization(None, overrides)` → `None.copy()` → `AttributeError` 런타임 크래시.

**현재 코드:**
```python
if c[6].button("저장", key=f"unc_save_{jeok}", type="primary"):
    overrides[jeok] = {
        "대분류": selected_cat,
        "소분류": selected_sub,
        "IsFixed": selected_cat == "고정지출",
    }
    save_overrides(overrides)
    st.session_state.overrides = overrides
    st.session_state.df = apply_categorization(   # ← raw_df가 None이면 여기서 터짐
        st.session_state.raw_df, overrides
    )
    st.rerun()
```

**수정 계획:**
```python
if c[6].button("저장", key=f"unc_save_{jeok}", type="primary"):
    overrides[jeok] = {
        "대분류": selected_cat,
        "소분류": selected_sub,
        "IsFixed": selected_cat == "고정지출",
    }
    save_overrides(overrides)
    st.session_state.overrides = overrides

    raw_df = st.session_state.get("raw_df")
    if raw_df is not None:
        # 파일 업로드 경로: 전체 재분류
        st.session_state.df = apply_categorization(raw_df, overrides)
    else:
        # DB 로드 경로: 해당 적요의 행만 직접 DB 업데이트
        db = get_db()
        current_df = st.session_state.get("df")
        if current_df is not None:
            rows = current_df[current_df["적요"] == jeok]
            for _, row in rows.iterrows():
                db.update_transaction_by_key(
                    str(row["날짜"]), str(row["_통장"]),
                    jeok, float(row["거래금액"]),
                    {"대분류": selected_cat, "소분류": selected_sub,
                     "IsFixed": selected_cat == "고정지출", "메모": ""}
                )
            # session df도 직접 갱신
            mask = current_df["적요"] == jeok
            st.session_state.df.loc[mask, "대분류"] = selected_cat
            st.session_state.df.loc[mask, "소분류"] = selected_sub
            st.session_state.df.loc[mask, "IsFixed"] = selected_cat == "고정지출"
    st.rerun()
```
- `database.py`에서 `from database import get_db` import 추가 필요.

---

### 1-2. 중복 거래 UNIQUE 충돌로 데이터 누락

**파일:** `database.py:29`  
**원인:** `UNIQUE(날짜, 통장, 적요, 거래금액)` — 같은 날 같은 통장에서 동일 가맹점·동일 금액으로 2회 결제 시 두 번째 건이 `INSERT OR IGNORE`로 묵음 DROP됨.

**현재 스키마:**
```sql
UNIQUE(날짜, 통장, 적요, 거래금액)
```

**수정 계획:**  
UNIQUE 키에 거래 일시(시간까지 포함) 컬럼 추가. 단 기존 DB는 ALTER로 제약 변경 불가(SQLite 한계)이므로 migration 필요.

```python
# database.py _SCHEMA 변경
_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    ...
    거래일시   TEXT,          -- ← 컬럼 추가
    ...
    UNIQUE(날짜, 통장, 적요, 거래금액, 거래일시)   -- ← 시간 포함
);
...
"""
```

`save_transactions()`에서 `거래일시` 함께 INSERT:
```python
conn.execute(
    """INSERT OR IGNORE INTO transactions
       (날짜,연월,통장,적요,거래유형,거래금액,대분류,소분류,is_fixed,메모,거래일시)
       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
    (
        ...,
        str(row.get("거래일시", row.get("거래 일시", ""))),   # ← 추가
    ),
)
```

migration 함수 추가 (`migrate_from_json` 내부에 추가):
```python
def _migrate_unique_key(self) -> None:
    """transactions UNIQUE 키에 거래일시 포함하도록 마이그레이션."""
    with self._connect() as conn:
        # 기존 테이블 백업 후 재생성
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transactions_new (
                ... -- 새 스키마 전체
                UNIQUE(날짜, 통장, 적요, 거래금액, 거래일시)
            );
            INSERT OR IGNORE INTO transactions_new
                SELECT *, '' as 거래일시 FROM transactions;
            DROP TABLE transactions;
            ALTER TABLE transactions_new RENAME TO transactions;
        """)
```

---

### 1-3. `@st.cache_resource` 세션 간 데이터 혼입

**파일:** `app.py:88-91`  
**원인:** `st.cache_resource`는 서버 프로세스 전체 공유 싱글턴. Streamlit Cloud 등 다중 접속 환경에서 다른 사용자의 거래내역이 보임.

**현재 코드:**
```python
@st.cache_resource(ttl=900)
def _shared_cache():
    return {"raw_df": None, "df": None}
```

그리고 앱 전반에서 `_c = _shared_cache()` 후 `_c["df"]` 형태로 캐시를 읽고 씀.

**수정 계획:**  
`_shared_cache()` 및 `_c` 참조를 전부 제거하고 `st.session_state`로 일원화.  

1. `_shared_cache()` 함수 정의 삭제  
2. 앱 내 `_c = _shared_cache()` 할당 라인 삭제  
3. `_c["df"]` → `st.session_state.df`, `_c["raw_df"]` → `st.session_state.raw_df`로 전부 교체  
4. Session State 초기화 블록(현재 `app.py:94-109`)은 이미 `st.session_state`를 사용하므로 그대로 유지  

grep으로 `_c[` 참조 전수 확인 후 치환:
```bash
grep -n "_c\[" app.py
```

---

### 1-4. 자동이체 공과금 미분류

**파일:** `utils.py:72`  
**원인:** 공과금 규칙이 `거래 유형 == "지로출금"`만 잡음. 전기·가스비가 자동이체로 출금되면 규칙 미매칭 → 미분류.

**현재 코드:**
```python
("고정지출", "공과금", True,
    lambda r: r["거래 유형"] == "지로출금"),
```

**수정 계획:**  
규칙 순서상 교통/통신·보험·연금·청약·적금 규칙이 먼저 매칭되므로, 공과금 규칙을 자동이체까지 확장해도 중복 분류 없음.

```python
("고정지출", "공과금", True,
    lambda r: r["거래 유형"] in ["지로출금", "자동이체"]
              and not any(x in str(r["적요"]) for x in [
                  "보험", "연금", "청약", "적금", "교통", "통신", "KT", "용돈"
              ])),
```

---

### 1-5. 지출 합계 음수 표시

**파일:** `app.py:512`  
**원인:** 지출은 음수 값으로 저장되어 있어 `sum()`이 `-1,234,567`로 표시됨.

**현재 코드:**
```python
st.metric("합계 금액", f"{filtered['거래금액'].sum():,.0f}원")
```

**수정 계획:**
```python
total = filtered["거래금액"].sum()
# 지출 탭(대분류 필터가 지출 계열)이면 절대값으로 표시
label = "합계 금액"
if total < 0:
    st.metric(label, f"{abs(total):,.0f}원")
else:
    st.metric(label, f"{total:,.0f}원")
```

또는 단순하게:
```python
st.metric("합계 금액", f"{filtered['거래금액'].sum():+,.0f}원")
```
`+` 포맷으로 부호를 명시해 수입/지출 구분을 직관적으로 표시.

---

## Phase 2 — 기능 오류 (1~2주 내)

---

### 2-1. 저축 집계 소분류 하드코딩 오류

**파일:** `tabs/savings.py:17-19`, `tabs/savings.py:102-108`  
**원인:** `소분류 == "적금/저축"` 단일 조건만 집계. 청약·연금·청년도약 등은 합산 안 됨.

**현재 코드:**
```python
savings_df = df[
    (df["대분류"] == "고정지출") & (df["소분류"] == "적금/저축")
].copy()
```

**수정 계획:**  
저축성 소분류를 상수로 정의하고 `isin()`으로 확장:

```python
# tabs/savings.py 상단에 상수 추가
SAVING_SUBCATS = ["적금/저축", "청약", "연금"]

# 집계 부분 변경
savings_df = df[
    (df["대분류"] == "고정지출") &
    (df["소분류"].isin(SAVING_SUBCATS))
].copy()
```

`tabs/savings.py:102-108`의 `actual_saving` 계산도 동일하게 수정:
```python
actual_saving = abs(
    df[
        (df["연월"] == latest_month) &
        (df["대분류"] == "고정지출") &
        (df["소분류"].isin(SAVING_SUBCATS))
    ]["거래금액"].sum()
)
```

---

### 2-2. 저축 목표 진행도 논리 오류

**파일:** `tabs/savings.py:111-117`  
**원인:** 목표가 여러 개여도 동일한 `actual_saving` 전체를 각 목표와 개별 비교 → 모든 목표 진행도가 동일하게 표시.

**현재 코드:**
```python
for _, row in goals.iterrows():
    goal_amt = float(row["월목표금액"])
    ratio    = actual_saving / goal_amt if goal_amt > 0 else 0
    st.progress(min(ratio, 1.0), text=f"...")
```

**수정 계획:**  
"이번 달 실제 저축액 vs 전체 목표 합계" 1개 진행도로 교체. 목표별 분리 비교는 목표에 소분류 매핑이 없는 한 의미 없음.

```python
total_goal = float(goals["월목표금액"].sum())
ratio = actual_saving / total_goal if total_goal > 0 else 0
st.progress(
    min(ratio, 1.0),
    text=f"이번 달 저축 **{actual_saving:,.0f}원** / 전체 목표 **{total_goal:,.0f}원** ({ratio:.0%})"
)

# 목표별로는 금액만 표시 (진행도 바 제거)
for _, row in goals.iterrows():
    st.caption(f"· {row['목표명']}: 월 {row['월목표금액']:,.0f}원 목표")
```

---

### 2-3. 편집 중 월 필터 변경 시 데이터 소실

**파일:** `app.py:545`  
**원인:** `key=f"exp_editor_{f_month}"` — 월이 바뀌면 data_editor key가 교체되어 편집 내용이 초기화됨.

**수정 계획:**  
key를 월 고정으로 변경하고, 현재 편집 중인 월을 session_state에 별도 저장. 월 변경 시 저장 여부 확인 경고 추가.

```python
# data_editor key 고정
key="exp_editor_main"   # 월 포함하지 않음

# 월 변경 감지 후 경고
prev_month = st.session_state.get("_prev_exp_month")
if prev_month and prev_month != f_month:
    st.warning(f"⚠️ 월이 변경되었습니다. 저장하지 않은 편집 내용은 사라집니다.")
st.session_state["_prev_exp_month"] = f_month
```

---

### 2-4. 지출 탭 대분류 필터 해제 시 수입 노출

**파일:** `app.py:493-503`  
**원인:** `f_cat = []` 이면 `if f_cat:` 조건이 False → 필터 미적용으로 수입·내부이체까지 전부 표시.

**현재 코드:**
```python
f_cat = st.multiselect("대분류", 대분류_opts, key="exp_cat")
...
if f_cat:
    filtered = filtered[filtered["대분류"].isin(f_cat)]
```

**수정 계획:**  
지출 탭은 항상 지출 계열 대분류만 기본 필터링. multiselect를 해제하면 기본값으로 fallback.

```python
# session state 초기값 변경 (app.py:109)
if "exp_cat" not in st.session_state:
    st.session_state.exp_cat = ["고정지출", "변동지출", "경조사", "기타"]

# 필터 로직 변경
DEFAULT_EXP_CATS = ["고정지출", "변동지출", "경조사", "기타"]
f_cat = st.multiselect("대분류", 대분류_opts, key="exp_cat")
active_cat = f_cat if f_cat else DEFAULT_EXP_CATS
filtered = filtered[filtered["대분류"].isin(active_cat)]
```

---

### 2-5. overrides 키 = 적요만 → 같은 적요 입금/출금 구분 불가

**파일:** `utils.py:143-147`, `database.py:82-87`, `tabs/uncategorized.py:78`  
**원인:** `"KB국민은행"` 적요가 입금·출금 모두 있으면 override가 둘 다 동일 분류로 강제됨.

**수정 계획:**

**Step 1 — DB 스키마 변경 (`database.py`):**
```sql
CREATE TABLE IF NOT EXISTS overrides (
    적요      TEXT NOT NULL,
    거래유형  TEXT NOT NULL DEFAULT '',
    대분류    TEXT NOT NULL DEFAULT '',
    소분류    TEXT NOT NULL DEFAULT '',
    is_fixed  INTEGER DEFAULT 0,
    PRIMARY KEY (적요, 거래유형)        -- 복합 PK
);
```

**Step 2 — `get_overrides()` 반환 구조 변경:**
```python
def get_overrides(self) -> dict:
    # 키: (적요, 거래유형) 튜플 → 값: {대분류, 소분류, IsFixed}
    rows = conn.execute("SELECT 적요,거래유형,대분류,소분류,is_fixed FROM overrides").fetchall()
    return {
        (r[0], r[1]): {"대분류": r[2], "소분류": r[3], "IsFixed": bool(r[4])}
        for r in rows
    }
```

**Step 3 — `categorize()` 조회 순서 변경 (`utils.py:143-147`):**
```python
def categorize(row, overrides: dict) -> tuple:
    적요 = str(row.get("적요", ""))
    거래유형 = str(row.get("거래 유형", ""))
    # 복합키 우선, 없으면 적요 단독 fallback
    if (적요, 거래유형) in overrides:
        ov = overrides[(적요, 거래유형)]
        return ov["대분류"], ov["소분류"], bool(ov.get("IsFixed", False))
    if (적요, "") in overrides:
        ov = overrides[(적요, "")]
        return ov["대분류"], ov["소분류"], bool(ov.get("IsFixed", False))
    for 대분류, 소분류, is_fixed, cond in rules:
        ...
```

**Step 4 — 미분류 탭 저장 시 거래유형 함께 저장 (`tabs/uncategorized.py:78`):**
```python
overrides[(jeok, row["거래유형"])] = {
    "대분류": selected_cat,
    "소분류": selected_sub,
    "IsFixed": selected_cat == "고정지출",
}
```

---

### 2-6. save_transactions 예외 묵음 처리

**파일:** `database.py:131-132`

**현재 코드:**
```python
except Exception:
    pass
```

**수정 계획:**
```python
import logging

# database.py 상단
logger = logging.getLogger(__name__)

# save_transactions except 변경
except Exception as e:
    logger.warning("transaction insert skip: %s", e)
    skipped += 1   # skipped 카운터 추가

# 반환값 변경: (inserted, skipped) 반환
return inserted, skipped
```

`app.py`에서 결과 표시:
```python
inserted, skipped = db.save_transactions(st.session_state.df)
if skipped:
    st.warning(f"{inserted}건 저장, {skipped}건 스킵 (중복 또는 오류)")
else:
    st.success(f"{inserted}건 저장 완료")
```

---

### 2-7. 분류 규칙 예외 묵음 처리

**파일:** `utils.py:149-153`

**현재 코드:**
```python
except Exception:
    pass
```

**수정 계획:**
```python
import logging
logger = logging.getLogger(__name__)

except Exception as e:
    logger.debug("rule eval error (적요=%s): %s", 적요, e)
```

silent pass → debug 로그로 변경. 프로덕션에선 출력 안 되고 개발 중 `--log-level debug`로 확인 가능.

---

### 2-8. 미분류 탭 일괄 저장 버튼 추가

**파일:** `tabs/uncategorized.py`  
**수정 계획:**  
각 행에 체크박스 컬럼 추가 → 상단 "선택 항목 일괄 저장" 버튼으로 한 번에 처리.

```python
# 헤더에 체크박스 컬럼 추가
h = st.columns([0.5, 3, 2, 1, 2, 2, 2])
for col, label in zip(h, ["✓", "적요", "거래유형/통장", "건수", "합계", "대분류", "소분류"]):
    col.caption(f"**{label}**")

selected_rows = {}
for _, row in grouped.iterrows():
    jeok = row["적요"]
    c = st.columns([0.5, 3, 2, 1, 2, 2, 2])
    checked = c[0].checkbox("", key=f"unc_chk_{jeok}", label_visibility="collapsed")
    # ... (기존 셀 렌더링)
    if checked:
        selected_rows[jeok] = {
            "대분류": st.session_state.get(f"unc_cat_{jeok}"),
            "소분류": st.session_state.get(f"unc_sub_{jeok}"),
        }

# 상단 일괄 저장 버튼
if selected_rows:
    if st.button(f"💾 선택 {len(selected_rows)}건 일괄 저장", type="primary"):
        for jeok, cats in selected_rows.items():
            overrides[jeok] = {**cats, "IsFixed": cats["대분류"] == "고정지출"}
        save_overrides(overrides)
        st.session_state.overrides = overrides
        # raw_df None 체크 포함 (1-1과 동일 로직)
        ...
        st.rerun()
```

---

### 2-9. 연금 탭 계산 오류 3종

**파일:** `tabs/pension.py`

**오류 A — 기적립금 입력 불가 (`:pension.py:20-35`)**  
폼에 `initial_amount` 필드 추가:
```python
initial_amount = st.number_input(
    "현재 적립금 (원)", min_value=0, step=1000000,
    value=int(cfg.get("현재적립금", 0)),
    help="이미 쌓인 연금 잔액"
)
```
`accumulated` 계산 시 초기값 포함:
```python
# 현재 코드
accumulated = monthly_pay * ((1+r)**n - 1) / r

# 수정 후
future_value_of_initial = initial_amount * (1 + monthly_rate) ** (accum_years * 12)
accumulated = future_value_of_initial + (
    monthly_pay * ((1 + monthly_rate) ** (accum_years * 12) - 1) / monthly_rate
    if monthly_rate > 0 else monthly_pay * accum_years * 12
)
```
DB `pension_config` 테이블에 `현재적립금 REAL DEFAULT 0` 컬럼 추가 필요.

**오류 B — 은퇴나이 > 수령나이 검증 없음 (`pension.py:46`)**
```python
# 폼 submit 후, 계산 전에 검증
if retire_age > receive_age:
    st.error("⚠️ 은퇴 나이가 연금 수령 나이보다 늦습니다. 수령 나이를 은퇴 나이 이후로 설정해주세요.")
    st.stop()
```

**오류 C — 국민연금 나이 무관 합산 (`pension.py:67`)**
```python
# 현재 코드
total_monthly = monthly_from_pension + national_pension

# 수정 후: 수령 나이 이후에만 국민연금 합산
# 국민연금은 수령 나이(receive_age)부터 받으므로
# 시뮬레이션상 은퇴 시점(retire_age) < 수령나이 구간엔 개인연금만
national_pension_applicable = national_pension if retire_age >= receive_age else 0
total_monthly = monthly_from_pension + national_pension_applicable
if retire_age < receive_age:
    st.caption(f"※ 국민연금은 {receive_age}세부터 수령. 은퇴 후 {receive_age - retire_age}년간 개인연금만 수령.")
```

---

### 2-10. 투자 탭 현재가 수정 불편

**파일:** `tabs/investment.py`  
**원인:** 현재가 수정 시 자산 전체 삭제 후 재추가가 유일한 방법.

**수정 계획:**  
자산 목록 테이블에 "현재가" 인라인 수정 컬럼 추가:
```python
# 자산 목록 렌더링 시 현재가 number_input 인라인 추가
for _, asset in assets.iterrows():
    col_name, col_type, col_price, col_btn = st.columns([3, 2, 2, 1])
    col_name.write(asset["자산명"])
    col_type.write(asset["유형"])
    new_price = col_price.number_input(
        "현재가", value=float(asset["현재가"]),
        key=f"price_{asset['id']}", label_visibility="collapsed",
        step=100.0
    )
    if col_btn.button("저장", key=f"save_price_{asset['id']}"):
        updated = asset.to_dict()
        updated["현재가"] = new_price
        db.upsert_asset(updated)
        st.rerun()
```

---

### 2-11. 카테고리 관리 탭 미분류 목록 중복 노출

**파일:** `app.py:862-876`  
**원인:** Tab 4 E섹션과 Tab 8(미분류 탭)이 동일한 미분류 목록을 이중 표시. Tab 4 것은 읽기 전용이라 혼란만 가중.

**수정 계획:**  
`app.py:862-876` 미분류 표 섹션을 제거하고 Tab 8 링크 안내로 대체:
```python
# 기존 미분류 표 코드 제거 후
st.info("💡 미분류 항목은 **❓ 미분류** 탭에서 일괄 처리할 수 있습니다.")
unc_count = len(df[df["대분류"] == "미분류"]) if df is not None else 0
if unc_count:
    st.warning(f"현재 미분류 **{unc_count}건** 있습니다.")
```

---

## Phase 3 — DB·성능 개선 (2~4주 내)

---

### 3-1. SQLite WAL 모드 설정

**파일:** `database.py:97-100`  
**수정 계획:**
```python
def _connect(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # ← 추가
    conn.execute("PRAGMA synchronous=NORMAL") # ← 성능 균형
    return conn
```

---

### 3-2. save_transactions 배치 INSERT

**파일:** `database.py:108-133`  
**원인:** 행 단위 `execute()` + 매 행 `SELECT changes()` → 1,000건 시 ~2,000회 쿼리.

**수정 계획:**
```python
def save_transactions(self, df: pd.DataFrame) -> tuple[int, int]:
    rows = []
    for _, row in df.iterrows():
        rows.append((
            str(row.get("날짜", "")),
            str(row.get("연월", "")),
            str(row.get("_통장", "")),
            str(row.get("적요", "")),
            str(row.get("거래 유형", "")),
            float(row.get("거래금액", 0) or 0),
            str(row.get("대분류", "")),
            str(row.get("소분류", "")),
            int(bool(row.get("IsFixed", False))),
            str(row.get("메모", "")),
            str(row.get("거래일시", "")),
        ))

    with self._connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        conn.executemany(
            """INSERT OR IGNORE INTO transactions
               (날짜,연월,통장,적요,거래유형,거래금액,대분류,소분류,is_fixed,메모,거래일시)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        after = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

    inserted = after - before
    skipped = len(rows) - inserted
    return inserted, skipped
```

---

### 3-3. save_overrides 전체 DELETE → 단건 upsert 분리

**파일:** `database.py:343-353`  
**원인:** 저장 시 `DELETE FROM overrides` 후 전체 재삽입. 루프 중 예외 발생 시 기존 overrides 전부 소실.

**수정 계획:**  
단건 upsert 메서드 추가:
```python
def upsert_override(self, 적요: str, 거래유형: str, 대분류: str, 소분류: str, is_fixed: bool) -> None:
    with self._connect() as conn:
        conn.execute(
            """INSERT INTO overrides (적요,거래유형,대분류,소분류,is_fixed)
               VALUES (?,?,?,?,?)
               ON CONFLICT(적요,거래유형) DO UPDATE SET
               대분류=excluded.대분류, 소분류=excluded.소분류, is_fixed=excluded.is_fixed""",
            (적요, 거래유형, 대분류, 소분류, int(is_fixed)),
        )
```
`save_overrides()`는 초기 마이그레이션 시만 사용하고, 이후 저장은 `upsert_override()` 사용.

---

### 3-4. build_monthly_kpis 반복 호출 최적화

**파일:** `app.py:419-425`  
**원인:** 6개월 추이를 그리기 위해 `build_monthly_kpis(df, m)` 6회 반복 호출. 매 호출마다 전체 df 순회.

**수정 계획:**  
6개월 데이터를 groupby 단 1회로 처리:
```python
# 기존 for 루프 대체
recent_df = df[df["연월"].isin(recent) & ~df["대분류"].isin(["내부이체"])]
kpi_pivot = recent_df.groupby(["연월", "대분류"])["거래금액"].sum().unstack(fill_value=0)

m_income = [kpi_pivot.get("수입", {}).get(m, 0) for m in recent]
m_fixed  = [abs(kpi_pivot.get("고정지출", {}).get(m, 0)) for m in recent]
m_var    = [abs(kpi_pivot.get("변동지출", {}).get(m, 0)) for m in recent]
m_event  = [abs(kpi_pivot.get("경조사", {}).get(m, 0)) for m in recent]
m_net    = [
    kpi_pivot.get("수입", {}).get(m, 0)
    + kpi_pivot.get("고정지출", {}).get(m, 0)
    + kpi_pivot.get("변동지출", {}).get(m, 0)
    + kpi_pivot.get("경조사", {}).get(m, 0)
    for m in recent
]
```

---

### 3-5. overrides DB NOT NULL·CHECK 제약 추가

**파일:** `database.py:82-87`  
```sql
-- 변경 후
CREATE TABLE IF NOT EXISTS overrides (
    적요      TEXT NOT NULL,
    거래유형  TEXT NOT NULL DEFAULT '',
    대분류    TEXT NOT NULL DEFAULT '',
    소분류    TEXT NOT NULL DEFAULT '',
    is_fixed  INTEGER NOT NULL DEFAULT 0 CHECK(is_fixed IN (0,1)),
    PRIMARY KEY (적요, 거래유형)
);
```

---

## Phase 4 — UX 개선 (4주+)

---

### 4-1. 대시보드 파이차트 "기타" 대분류 포함

**파일:** `app.py:387`
```python
# 변경 전
month_df = df[(df["연월"] == ym) & df["대분류"].isin(["고정지출", "변동지출", "경조사"])]

# 변경 후
month_df = df[(df["연월"] == ym) & df["대분류"].isin(["고정지출", "변동지출", "경조사", "기타"])]
```

---

### 4-2. 6개월 추이 차트 선택 월 하이라이트

**파일:** `app.py:428-431`  
Plotly bar color 배열로 선택 월만 다른 색 적용:
```python
colors_income = ["#6FCF97" if m == ym else "#A8E6A8" for m in recent]
colors_fixed  = ["#2F80ED" if m == ym else "#7EB3F5" for m in recent]
# add_bar marker_color에 리스트 전달
fig_bar.add_bar(x=recent, y=m_income, name="수입", marker_color=colors_income)
```

---

### 4-3. 미분류 탭 정렬 개선

**파일:** `tabs/uncategorized.py:42`
```python
# 변경 전 (합계 오름차순 = 음수 큰 금액 상단)
.sort_values("합계")

# 변경 후 (절대값 기준 내림차순 = 금액 큰 것 우선)
.assign(합계절대값=lambda x: x["합계"].abs())
.sort_values("합계절대값", ascending=False)
.drop(columns="합계절대값")
```

---

### 4-4. 앱 타이틀 오탈자 수정

**파일:** `app.py:137`  
`grep -n "쀼" app.py`로 위치 확인 후:
```python
# "💰 채지pt쀼 가계부" → 원하는 타이틀로
st.sidebar.title("💰 가계부")
```

---

### 4-5. 사이드바·탭 내 월 필터 연동

**파일:** `app.py:491`, `app.py:600`  
사이드바의 `selected_month`를 지출·수입 탭 selectbox 기본값으로 연동:
```python
# 지출 탭 월 selectbox 기본값
default_idx = all_months_opt.index(st.session_state.selected_month) \
    if st.session_state.selected_month in all_months_opt else 0
f_month = st.selectbox("월", all_months_opt, index=default_idx, key="exp_month")
```

---

### 4-6. 연간 저축 예상 계산 개선

**파일:** `tabs/savings.py:126`
```python
# 변경 전 (최신 1개월 × 12)
yearly_actual = actual_saving * 12

# 변경 후 (최근 3개월 평균 × 12)
recent3 = all_months[:3]
avg3 = sum(
    abs(df[(df["연월"] == m) & (df["대분류"] == "고정지출") &
           (df["소분류"].isin(SAVING_SUBCATS))]["거래금액"].sum())
    for m in recent3
) / len(recent3) if recent3 else actual_saving
yearly_actual = avg3 * 12
```

---

### 4-7. 저축 목표 달성 기한 설정 (신규 기능)

**파일:** `tabs/savings.py`, `database.py`

**DB 변경:**
```sql
ALTER TABLE savings_goals ADD COLUMN 목표총액 REAL DEFAULT 0;
ALTER TABLE savings_goals ADD COLUMN 기한 TEXT DEFAULT '';
```

**폼 변경:**
```python
with st.form("goal_form", clear_on_submit=True):
    goal_name   = st.text_input("목표명")
    goal_amount = st.number_input("월 목표 저축액 (원)", min_value=0, step=50000)
    goal_total  = st.number_input("목표 총액 (원, 선택)", min_value=0, step=100000)
    goal_date   = st.date_input("목표 기한 (선택)", value=None)
```

**예상 달성 시점 계산:**
```python
if goal_total > 0 and actual_saving > 0:
    months_needed = math.ceil(goal_total / actual_saving)
    reach_date = date.today() + relativedelta(months=months_needed)
    st.caption(f"현재 페이스로 약 {months_needed}개월 후 ({reach_date:%Y년 %m월}) 달성 예상")
```

---

## 수정 우선순위 요약

| Phase | 항목 | 예상 소요 |
|-------|------|---------|
| **Phase 1** — 크래시·무결성 5건 | 1-1 ~ 1-5 | 1~2일 |
| **Phase 2** — 기능 오류 11건 | 2-1 ~ 2-11 | 1~2주 |
| **Phase 3** — DB·성능 5건 | 3-1 ~ 3-5 | 1~2주 |
| **Phase 4** — UX 개선 7건 | 4-1 ~ 4-7 | 지속 |

---

## 변경하지 않는 것

- 대분류/소분류 분류 체계 (수입·고정지출·변동지출·경조사·내부이체·기타)
- 소분류 목록 전체
- overrides 우선 → rules → 미분류 순 적용 흐름
- IsFixed 자동 설정 기준 (고정지출 = True)
