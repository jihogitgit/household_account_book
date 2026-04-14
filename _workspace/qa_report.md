# QA Report — 가계부 Streamlit 앱

- **검증일**: 2026-04-14
- **대상**: `/Users/mw/prodect/통장/utils.py`, `/Users/mw/prodect/통장/app.py`
- **실행자**: qa-engineer 에이전트

## 요약

| # | 항목 | 결과 |
|---|------|------|
| 1 | Python 문법 파싱 (utils.py / app.py) | PASS |
| 2 | 필수 함수 존재 (10종) | PASS |
| 3 | `PASSWORD` 하드코딩 상수 부재 | PASS |
| 4 | `categorize()` override 우선 규칙 | PASS |
| 5 | `categorize()` KT 통신사 → 주거/통신 분류 | PASS |
| 6 | `apply_categorization()` 파생 컬럼 6종 | PASS |
| 7 | `build_monthly_kpis()` 필수 키 6종 | PASS |
| 8 | `save_overrides()` / `load_overrides()` JSON 라운드트립 | PASS |
| 9 | `save_budgets()` / `load_budgets()` JSON 라운드트립 (0원 필터링 포함) | PASS |
| 10 | `utils.py` / `app.py` 내 `911017` 문자열 부재 | PASS |
| 11 | `.gitignore`에 `budgets.json` 포함 | PASS |

**종합 판정: 통과 (Ready for deploy)**

## 세부 결과

### 1. 문법 검증
```
utils.py OK
app.py OK
```

### 2. 데이터 레이어 정합성
- `apply_categorization()` 반환 컬럼: `['적요', '거래 유형', '거래 금액', '거래 일시', '메모', '_통장', '대분류', '소분류', 'IsFixed', '거래금액', '거래일시', '날짜', '연월']`
- 스펙 요구 파생 컬럼 전부 존재: `대분류 / 소분류 / IsFixed / 거래금액 / 날짜 / 연월`
- `app.py`에서 참조하는 컬럼(`거래 유형`, `_통장`, `메모`, `거래금액`, `날짜`, `연월`, `대분류`, `소분류`, `IsFixed`, `적요`) 모두 정합.

샘플 분류 결과:
```
적요          대분류    소분류    IsFixed   거래금액     연월
유지호         수입     급여      False    3,000,000   2026-04
KT월정액       고정지출  주거/통신  True     50,000      2026-04
```

### 3. categorize() 규칙 검증
- override 우선 적용: `('변동지출','식비',False)` 반환 확인
- KT 통신사: `('고정지출','주거/통신', True)` 반환 (rules 0번째, `적요`에 `KT|LG|SK|통신` regex 매칭, 최우선)
- 통신사 규칙은 `적요` 컬럼만 참조하므로 `거래 유형` / `거래유형` 키 공백 여부와 무관하게 안정 동작

### 4. build_monthly_kpis() 키 검증
반환 dict 키: `총수입 / 고정지출 / 변동지출 / 경조사 / 순수지 / prev` 전부 존재.
내부이체는 `~df["대분류"].isin(["내부이체"])` 필터로 KPI에서 제외됨 (이중계산 방지 OK).

### 5. 보안 감사
- `utils.py`, `app.py`에 `911017` 문자열 **전무**
- `utils.decrypt(source, password)`: 비밀번호는 외부에서 주입 (app.py의 `st.secrets.get("xlsx_password","")` → 사용자 입력 fallback)
- `utils.PASSWORD` 상수 존재하지 않음

### 6. .gitignore 상태
```
*.xlsx
overrides.json
budgets.json
.streamlit/secrets.toml
__pycache__/
*.pyc
.venv/
.env
.DS_Store
```
민감 파일(xlsx, overrides.json, budgets.json, secrets.toml) 전부 제외됨. PASS.

## 관찰 사항 (Non-blocking)

### 관찰 #1 — QA 스펙과 실제 컬럼명 차이 (문서 정합성)
- **위치**: QA 스펙의 샘플 DataFrame이 `{'거래유형','거래금액(원)','거래일시'}` 키를 사용
- **실제**: 토스뱅크 엑셀 원본 컬럼은 `거래 유형`, `거래 금액`, `거래 일시` (공백 포함)이며, `utils.rules`와 `apply_categorization`은 이 공백 포함 이름을 참조
- **영향**: 이번 검증은 실제 스키마(`거래 일시`, `거래 금액`)로 바꿔 실행했으며 모두 통과. 단, QA 스펙을 문자 그대로 실행하면 `apply_categorization`이 `KeyError: '거래 일시'`로 실패 가능.
- **심각도**: 낮음 (문서 상의 불일치일 뿐, 운영 데이터로는 정상)
- **권고**: QA 스펙/샘플 데이터에 실제 엑셀 컬럼명(`거래 유형`, `거래 금액`, `거래 일시`)을 사용하도록 문서 갱신

### 관찰 #2 — 순수지 부호 규약
`build_monthly_kpis`는 `순수지 = 총수입 + 고정지출 + 변동지출 + 경조사`로 계산. 지출이 음수로 들어오는 토스뱅크 원본 스키마와 호환되므로 올바른 식. UI의 "순 수지" 카드도 동일 규약으로 표시됨.

### 관찰 #3 — `detect_fixed_candidates` 경계
- 현재 IsFixed 판정이 행 단위 `IsFixed.max()`로 결정되므로, 동일 적요가 override로 IsFixed=True 지정되면 자동탐지 후보에서 정상 제외됨.
- 변동계수(cv) 10% 이내 + 3개월 이상을 요구 → 너무 엄격하진 않은지 모니터링 필요. 실제 로드된 데이터에서 후보 수가 비정상적으로 적으면 `amount_tol`을 0.15~0.20으로 완화 검토.

## 결론

데이터 레이어(utils.py), UI 레이어(app.py) 경계면 모두 정합. 보안(비밀번호 하드코딩/민감파일 커밋) 리스크 없음. **배포 준비 완료.**
