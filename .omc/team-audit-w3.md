# Worker 3 감사 보고서 — 분류규칙 / DB설계 / 미분류 탭

> 감사 일자: 2026-04-28  
> 담당 범위: `utils.py` rules + overrides, `database.py` 스키마, `tabs/uncategorized.py`

---

## 🔴 심각 (즉시 수정 권고)

### S-1. UNIQUE 제약으로 동일 거래 중복 누락
**파일:** `database.py:29`  
**내용:**
```sql
UNIQUE(날짜, 통장, 적요, 거래금액)
```
같은 날 같은 통장에서 동일 적요·금액의 거래가 2회 이상 발생하면 두 번째 건부터 `INSERT OR IGNORE`로 묵살됨.  
예) 편의점 2,000원 결제 두 번 → 1건만 저장. 실제 지출 합계가 과소 계상됨.  
**수정 방향:** UNIQUE 키에 시간(`거래 일시`) 컬럼 추가, 또는 UUID/hash 컬럼 도입.

---

### S-2. 공과금 자동이체 → 미분류 落穴
**파일:** `utils.py:68-72`  
**내용:**
```python
("고정지출", "교통/통신", True,
    lambda r: r["거래 유형"] in ["자동이체", "지로출금"]
              and any(x in str(r["적요"]) for x in ["교통", "통신", "KT"])),
("고정지출", "공과금", True,
    lambda r: r["거래 유형"] == "지로출금"),  # 지로출금만!
```
전기세·가스비가 **자동이체** 방식으로 출금되면 "지로출금" 조건에 걸리지 않아 공과금 규칙을 통과, 이후 매칭 규칙이 없으면 **미분류**가 됨.  
**수정 방향:** 공과금 규칙을 `거래 유형 in ["지로출금", "자동이체"]`로 확장, 대신 키워드 블랙리스트나 화이트리스트 추가.

---

### S-3. CAT_MAP에 실체 없는 소분류 "효도" 존재
**파일:** `tabs/uncategorized.py:12`  
```python
"변동지출": ["생활", "배달", "병원", "경조사", "효도"],
```
- `"효도"` 소분류는 `utils.py rules`에 정의되지 않음. 사용자가 이 소분류로 저장해도 rules에서 절대 자동 분류되지 않아 override에만 의존.  
- `"경조사"` 소분류가 **변동지출** 아래 노출됨. 실제 경조사 통장 거래는 `경조사/경조사`로 분류되지만, 사용자가 `변동지출/경조사`로 잘못 저장하면 경조사 집계가 틀어짐.  
**수정 방향:** CAT_MAP을 rules와 동기화. "효도" 제거 또는 rules에 추가. "변동지출" 아래 "경조사" 제거.

---

### S-4. overrides 키가 적요만 → 동일 적요 다른 맥락 구분 불가
**파일:** `utils.py:143-147`, `database.py:82-87`  
```python
if 적요 in overrides:
    ov = overrides[적요]
    return ov["대분류"], ov["소분류"], ...
```
같은 적요("KB국민은행")가 입금·출금 모두 발생할 수 있음. override를 저장하면 **거래 유형·통장 무관하게** 동일 분류 강제 적용됨. 수입과 지출이 같은 적요면 둘 다 오분류.  
**수정 방향:** overrides 키를 `(적요, 거래유형)` 또는 `(적요, 통장)` 복합키로 설계. DB 스키마 변경 필요.

---

### S-5. `raw_df` 세션 상태 누락 시 KeyError
**파일:** `tabs/uncategorized.py:85`  
```python
st.session_state.df = apply_categorization(
    st.session_state.raw_df, overrides  # raw_df 없으면 KeyError
)
```
저장 버튼 클릭 시 `raw_df`가 session_state에 없으면 앱이 예외로 터짐. 오류 처리 없음.  
**수정 방향:** `st.session_state.get("raw_df")` 후 None 체크 추가.

---

## 🟡 중간 (조기 수정 권고)

### M-1. overrides 테이블 NOT NULL / CHECK 제약 누락
**파일:** `database.py:82-87`  
```sql
CREATE TABLE IF NOT EXISTS overrides (
    적요    TEXT PRIMARY KEY,
    대분류  TEXT,          -- NULL 허용
    소분류  TEXT,          -- NULL 허용
    is_fixed INTEGER DEFAULT 0
);
```
`대분류`, `소분류`가 NULL 또는 빈 문자열로 저장되면, `categorize()`가 `(None, None, False)` 반환 → 집계 오류.  
유효한 대분류 값 검증도 없음(CHECK 없음).  
**수정 방향:** `NOT NULL`, `DEFAULT ''`, `CHECK(대분류 IN ('수입','고정지출',...))` 추가.

---

### M-2. categorize() 규칙 예외 조용히 무시 → 버그 숨김
**파일:** `utils.py:148-153`  
```python
try:
    if cond(row):
        return ...
except Exception:
    pass
```
`_통장` 컬럼 누락 등으로 규칙 lambda가 KeyError 발생 시, 해당 규칙을 skip하고 다음 규칙으로 이동. 실제 버그가 분류 오류로 조용히 흡수됨.  
**수정 방향:** 예외를 `logging.warning`으로 기록하거나, 컬럼 존재 여부를 `categorize` 진입 시 사전 체크.

---

### M-3. save_overrides 전체 DELETE 후 재삽입 — 부분 실패 위험
**파일:** `database.py:343-353`  
```python
conn.execute("DELETE FROM overrides")
for jeok, v in overrides.items():
    conn.execute("INSERT OR REPLACE ...")
```
`with conn:` 컨텍스트 안이므로 원자적으로 처리되지만, 루프 중 한 건에서 예외 발생 시 전체 롤백 → **기존 overrides 전부 삭제** 후 빈 상태가 됨.  
또한 단건 추가 시에도 전체 재삽입으로 성능 불필요한 낭비.  
**수정 방향:** `INSERT OR REPLACE INTO overrides ... WHERE 적요=?` 단건 upsert 메서드 분리.

---

### M-4. IsFixed 자동 설정이 대분류만으로 결정
**파일:** `tabs/uncategorized.py:82`  
```python
"IsFixed": selected_cat == "고정지출",
```
사용자가 "고정지출"을 선택하면 소분류 무관하게 무조건 IsFixed=True. 고정지출이지만 IsFixed=False로 분리하고 싶은 케이스(예: 임시 고정지출) 불가능.  
**수정 방향:** IsFixed를 별도 체크박스로 분리하고 기본값만 `대분류 == "고정지출"`로 설정.

---

### M-5. 수동 DB 편집과 overrides 재적용 충돌
**파일:** `database.py:157-171`, `utils.py:157-182`  
개별 트랜잭션을 `update_transaction_by_key`로 DB에서 직접 수정했더라도, 이후 새 파일 업로드 시 `apply_categorization`이 overrides 기준으로 **전체 재분류** 후 DB에 재삽입됨. 기존 수동 수정이 덮어씌워질 수 있음.  
**수정 방향:** overrides 적용 범위를 명확히 정의하거나, "수동 고정" 플래그를 트랜잭션에 추가하여 재분류에서 제외.

---

### M-6. budgets 테이블 음수 예산 DB 레벨 미검증
**파일:** `database.py:77-80`  
```sql
CREATE TABLE IF NOT EXISTS budgets (
    소분류      TEXT PRIMARY KEY,
    월예산금액  INTEGER DEFAULT 0
);
```
코드(`save_budgets:329`)에서 `> 0`만 저장하지만, 직접 SQL 접근 시 음수 삽입 가능. CHECK 제약 없음.  
**수정 방향:** `CHECK(월예산금액 >= 0)` 추가.

---

## 🟢 낮음 (개선 권고)

### L-1. 급여 적요 하드코딩 (사람 이름)
**파일:** `utils.py:36`  
```python
and r["적요"] in ["유지호", "김채현"]
```
가족 구성 변화 시 코드 수정 필요. overrides나 설정 파일로 외부화 권고.

---

### L-2. 규칙 순서 의존성 — 유지보수 리스크
**파일:** `utils.py:32-99`  
`("변동지출", "생활", ...)` 규칙이 체크카드/ATM 전체를 커버하므로, 이 규칙 앞에 배달/병원 규칙이 반드시 있어야 함. 순서 변경 시 분류 전체 오동작. 규칙 간 의존 관계를 주석으로 명시하거나 rule prioritization 구조로 개선 권고.

---

### L-3. 미분류 탭 정렬이 직관적이지 않음
**파일:** `tabs/uncategorized.py:42`  
```python
.sort_values("합계")
```
합계 오름차순이므로 음수(출금, 큰 금액)가 상단에 오지만, 건수 기준이나 절대값 기준 정렬이 작업 효율에 유리.

---

### L-4. 컬럼명 "거래 유형" vs "거래유형" 혼재
원본 DataFrame은 `"거래 유형"` (공백 있음), groupby agg 후 결과는 `"거래유형"` (공백 없음). 코드 내 혼재로 유지보수 혼란 가능.

---

## 요약 테이블

| ID  | 우선순위 | 파일 | 문제 |
|-----|---------|------|------|
| S-1 | 심각 | database.py:29 | 동일 거래 UNIQUE 충돌로 데이터 누락 |
| S-2 | 심각 | utils.py:68-72 | 자동이체 공과금 미분류 |
| S-3 | 심각 | uncategorized.py:12 | CAT_MAP "효도" 유령 소분류, "경조사" 대분류 혼선 |
| S-4 | 심각 | utils.py:143, database.py:82 | overrides 키 = 적요만, 맥락 구분 불가 |
| S-5 | 심각 | uncategorized.py:85 | raw_df 없으면 저장 시 KeyError 크래시 |
| M-1 | 중간 | database.py:82 | overrides NOT NULL/CHECK 제약 누락 |
| M-2 | 중간 | utils.py:148 | 규칙 예외 조용히 무시 |
| M-3 | 중간 | database.py:343 | save_overrides 전체 DELETE 방식 리스크 |
| M-4 | 중간 | uncategorized.py:82 | IsFixed 대분류만으로 자동 결정 |
| M-5 | 중간 | database.py:157, utils.py:157 | 수동 DB 편집과 overrides 재적용 충돌 |
| M-6 | 중간 | database.py:77 | budgets 음수 예산 DB 미검증 |
| L-1 | 낮음 | utils.py:36 | 급여 이름 하드코딩 |
| L-2 | 낮음 | utils.py:32 | 규칙 순서 의존성 문서화 부재 |
| L-3 | 낮음 | uncategorized.py:42 | 미분류 탭 정렬 비직관적 |
| L-4 | 낮음 | uncategorized.py:39 | 거래 유형 컬럼명 혼재 |
