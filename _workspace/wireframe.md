# 가계부 Streamlit 앱 화면 설계서

> 작성일: 2026-04-14
> 기반: `_workspace/research_gaegabu.md` 인사이트 + 현재 `app.py` / `utils.py` 구현 상태
> 목표: 기존 5개 탭(대시보드·지출·수입·카테고리관리·수익률) 구조를 유지하되, 리서치 인사이트(예산 초과 경고, 고정비 자동 탐지, 보안, 캐싱)를 반영해 **P1 즉시 구현 / P2 고도화**로 세분화

---

## 1. 전체 구조 (탭/페이지 계층)

```
사이드바
├─ 파일 업로드 (비밀번호 입력 추가 ← st.secrets 또는 st.text_input)
├─ 데이터 로드 버튼
├─ 월 선택 (selectbox)
├─ 로드된 통장 표시
└─ ⭐ NEW: 예산 설정 접기 패널 (expander)

메인 탭 (6개 — 주간 점검 신규)
├─ 📊 대시보드         ... KPI + 도넛 + 6개월 추이 + ⭐ 예산 진행바 추가
├─ 🗓 주간 점검        ... ⭐ NEW. isocalendar().week 기준 요약
├─ 💸 지출 내역        ... 필터 + 테이블 + CSV (유지) + ⭐ 카테고리 드릴다운 연동
├─ 💵 수입 내역        ... 유지
├─ 🗂 카테고리 관리     ... 기존 3개 섹션 + ⭐ 고정비 자동 탐지 제안 섹션 추가
└─ 📈 수익률 / 목표저축 ... ⭐ 저축 목표 진행도 우선 활성화
```

---

## 2. 각 화면 와이어프레임

### 2.1 사이드바 (보안 개선 포함)

```
┌─────────────────────────────────┐
│ 💰 가계부                        │
│ 토스뱅크 거래내역 자동 분류      │
├─────────────────────────────────┤
│ 📁 파일 업로드                   │
│ [ xlsx 파일 선택 ... ]           │
│ ☐ 기본 파일 사용 (통장 폴더)     │
│                                  │
│ ⭐ 🔑 xlsx 비밀번호 (신규)       │
│ [ ●●●●●●  ] (st.text_input,     │
│    type="password",              │
│    value=st.secrets.get(...))    │
│                                  │
│ [🔄 데이터 로드]                 │
├─────────────────────────────────┤
│ 📅 조회 월  [2026-04 ▼]          │
│ 🏦 로드된 통장                   │
│   - 생활비: 128건                │
│   - 경조사: 12건                 │
├─────────────────────────────────┤
│ ⭐ 💰 예산 설정 (expander, 신규) │
│   ▸ 식비      [   500,000 원 ]  │
│   ▸ 카페/음료 [   100,000 원 ]  │
│   ▸ 쇼핑      [   300,000 원 ]  │
│   ... (소분류별 number_input)    │
│   [💾 예산 저장]                 │
└─────────────────────────────────┘
```

### 2.2 Tab 1: 대시보드 (예산 진행바 추가)

```
┌─ KPI 카드 4열 (유지) ────────────────────────────────────────┐
│ [총 수입 ↑]  [고정지출 ↓]  [변동지출 ↓]  [순수지]          │
└──────────────────────────────────────────────────────────────┘

┌─ ⭐ 예산 초과 경고 (NEW) ────────────────────────────────────┐
│ 🎯 4월 예산 현황                                              │
│ 식비    ████████████░░░  85%  425,000 / 500,000원            │
│ 카페    █████████████▓▓  102% ⚠️ 초과  102,340 / 100,000원   │
│ 쇼핑    █████░░░░░░░░░░  32%   96,500 / 300,000원            │
│ (st.progress 바, 100% 초과시 빨간색 + ⚠️ 아이콘)              │
└──────────────────────────────────────────────────────────────┘

┌─ 지출 구성 (도넛, 유지) ─┐ ┌─ 최근 6개월 추이 (유지) ────┐
│ [Plotly 도넛 hole=0.55]  │ │ [스택 바 + 순수지 라인]      │
└──────────────────────────┘ └──────────────────────────────┘

┌─ 고정 지출 내역 ─────────┐ ┌─ 변동 지출 내역 ─────────┐
│ [groupby(소분류) 테이블] │ │ [groupby(소분류) 테이블] │
└──────────────────────────┘ └──────────────────────────┘
```

### 2.3 ⭐ Tab 2 (NEW): 주간 점검

```
┌─ 주간 선택 ──────────────────────────────────────┐
│ 년도 [2026 ▼]  주차 [ISO Week 15 (4/6~4/12) ▼]    │
└──────────────────────────────────────────────────┘

┌─ 주간 KPI (4열) ─────────────────────────────────┐
│ [이번주 지출] [전주 대비] [일평균] [예산 잔여일]  │
└──────────────────────────────────────────────────┘

┌─ 일자별 지출 막대 ────────┐ ┌─ Top 5 카테고리 ─────┐
│ 월 ███ 22,000              │ │ 1. 식비    120,000   │
│ 화 ████ 35,000             │ │ 2. 쇼핑     80,000   │
│ 수 █ 8,000                 │ │ ...                   │
│ ...                         │ └──────────────────────┘
└───────────────────────────┘

┌─ 이번주 미분류 거래 (액션 프롬프트) ───────────────┐
│ 미분류 3건 → [🗂 카테고리 관리 탭으로 이동]        │
└──────────────────────────────────────────────────┘
```

### 2.4 Tab 3: 지출 내역 (드릴다운 연동 추가)

```
(유지) 필터 4열: 월 / 대분류 / 소분류 / 통장
     ↑ ⭐ st.session_state.drilldown_subcat 가 있으면 자동 적용 + 안내 배너:
       "📍 대시보드에서 '카페/음료' 클릭 → 자동 필터링됨. [해제]"

(유지) 소계 3열 + 테이블 + CSV 다운로드
```

### 2.5 Tab 4: 수입 내역 (유지)

현재 구현 그대로 유지.

### 2.6 Tab 5: 카테고리 관리 (고정비 자동 탐지 추가)

```
A. 현재 분류 규칙 (expander, 유지)
B. 적요 단위 재지정 (form, 유지)
C. 현재 재지정 목록 (data_editor, 유지)

⭐ D. NEW: 고정비 자동 탐지 제안
┌──────────────────────────────────────────────────────────┐
│ 💡 3개월 이상 연속 동일 적요 + 유사 금액(±10%) 탐지       │
│                                                           │
│ ┌─ 적요 ─────┬ 출현월 ─┬ 평균 금액 ─┬ 추천 ───┬─ 액션 ┐ │
│ │ KT 통신요금 │ 3개월   │ 55,000원   │ ✔ 고정   │ [적용]│ │
│ │ 건강보험    │ 4개월   │ 142,300원  │ ✔ 고정   │ [적용]│ │
│ │ 스포티파이  │ 3개월   │ 10,900원   │ ✔ 고정   │ [적용]│ │
│ └────────────┴────────┴───────────┴─────────┴──────┘   │
│ [📌 모두 적용]                                            │
└──────────────────────────────────────────────────────────┘

E. 미분류 항목 (유지)
```

### 2.7 Tab 6: 수익률 / 목표저축 (우선 저축 진행도 활성화)

```
┌─ ⭐ 저축 목표 진행도 (신규 활성화) ──────────────────┐
│ 2026 연간 저축 목표 [ 12,000,000 원 ]  [수정]         │
│                                                        │
│ 현재 저축 누계: 4,850,000원                            │
│ ████████░░░░░░░░░░░░░░░░░░░░  40.4%                   │
│                                                        │
│ 월평균 필요: 1,000,000원 / 현재 월평균: 808,333원     │
│ → 예상 연말 달성: 9,700,000원 (목표 대비 80.8%)       │
└──────────────────────────────────────────────────────┘

┌─ 주식 / 연금 (준비중, 유지) ──────────────────────┐
│ [주식 수익률] [연금 예상] [이번달 적금/저축]       │
└──────────────────────────────────────────────────┘
```

---

## 3. 컴포넌트 사양

### 3.1 사이드바 — xlsx 비밀번호 입력 (보안 개선)

| 항목 | 값 |
|---|---|
| 컴포넌트 | `st.text_input("xlsx 비밀번호", type="password", value=st.secrets.get("xlsx_password", ""))` |
| session_state 키 | `st.session_state.xlsx_password` |
| 이벤트 | 사용자 수정 시 즉시 반영 (다음 `load_excel` 호출에 사용) |
| utils.py 변경 | `decrypt(source, password: str)` / `load_excel(source, account_name, password)` 파라미터 추가. 모듈 전역 `PASSWORD` 상수 제거 |
| 우선순위 | **P1** |

`.streamlit/secrets.toml` (gitignore 필수):
```toml
xlsx_password = "911017"
```

### 3.2 사이드바 — 예산 설정 expander

| 항목 | 값 |
|---|---|
| 컴포넌트 | `st.expander("💰 예산 설정")` 내부에 소분류별 `st.number_input(min_value=0, step=10000)` |
| session_state 키 | `st.session_state.budgets = {소분류: amount}` |
| 영속화 | `budgets.json` (utils: `load_budgets()`, `save_budgets()`) |
| 이벤트 | `[💾 예산 저장]` 버튼 on_click → `save_budgets()` + `st.rerun()` |
| 우선순위 | **P1** |

### 3.3 대시보드 — 예산 진행바

| 항목 | 값 |
|---|---|
| 컴포넌트 | 루프 안에서 `st.progress(min(ratio, 1.0))` + `st.caption(f"{spent:,}/{budget:,}원 ({ratio:.0%})")` |
| 로직 | `ratio = abs(spent) / budget`; 100% 초과 시 `st.error(f"⚠️ {소분류} 예산 초과")`, 80% 이상 시 `st.warning` |
| 바인딩 | `df[(df.연월==ym) & (df.소분류==cat)]["거래금액"].sum()` |
| 우선순위 | **P1** |

### 3.4 카테고리 관리 — 고정비 자동 탐지

```python
def detect_fixed_candidates(df: pd.DataFrame, window_months: int = 3, amount_tol: float = 0.10) -> pd.DataFrame:
    """연속 N개월 이상 동일 적요가 등장하며 금액 표준편차/평균 <= tol 인 적요 반환."""
    exp = df[df["대분류"].isin(["고정지출", "변동지출", "기타"])]
    grp = exp.groupby(["적요", "연월"])["거래금액"].sum().reset_index()
    agg = grp.groupby("적요").agg(
        months=("연월", "nunique"),
        mean=("거래금액", "mean"),
        std=("거래금액", "std"),
    ).reset_index()
    agg["cv"] = (agg["std"].abs() / agg["mean"].abs()).fillna(0)
    return agg[(agg["months"] >= window_months) & (agg["cv"] <= amount_tol)]
```

| 항목 | 값 |
|---|---|
| 컴포넌트 | `st.dataframe` + 행별 `st.button("적용", key=f"fix_{적요}")` 또는 `[📌 모두 적용]` 일괄 버튼 |
| 이벤트 | 적용 시 `st.session_state.overrides[적요] = {..., "IsFixed": True}` → `save_overrides` → `apply_categorization` 재실행 |
| 우선순위 | **P1** |

### 3.5 주간 점검 탭

| 항목 | 값 |
|---|---|
| 주차 계산 | `df["주차"] = df["거래일시"].dt.isocalendar().week` ; `df["연주차"] = df["거래일시"].dt.strftime("%G-W%V")` |
| 컴포넌트 | `st.selectbox` (연도/주차), KPI `st.metric` 4개, `px.bar` 일자별, `st.dataframe` Top5 |
| 우선순위 | **P1** |

### 3.6 드릴다운 연동 (도넛 → 지출 탭)

| 항목 | 값 |
|---|---|
| 방식 | `streamlit-plotly-events` 라이브러리(옵션) 대신 **MVP는 radio/selectbox로 카테고리 선택 → 지출 탭으로 이동 버튼** 제공 |
| session_state 키 | `st.session_state.drilldown_subcat` |
| 우선순위 | **P2** (커스텀 컴포넌트 의존 최소화) |

### 3.7 `apply_categorization` 캐싱

```python
@st.cache_data(ttl=3600, show_spinner=False)
def apply_categorization_cached(raw_df_bytes: bytes, overrides_json: str) -> pd.DataFrame:
    raw = pd.read_pickle(io.BytesIO(raw_df_bytes))
    overrides = json.loads(overrides_json)
    return apply_categorization(raw, overrides)
```

| 항목 | 값 |
|---|---|
| 대안(더 간단) | `@st.cache_data` 를 `load_excel` 에 우선 적용 + `apply_categorization` 내부 `df.apply` → **벡터화** (카테고리 규칙을 dict lookup + np.select 로 재작성) |
| 우선순위 | **P1** (핵심 성능 이슈) |

### 3.8 목표 저축 진행도

| 항목 | 값 |
|---|---|
| session_state 키 | `st.session_state.savings_goal` (연간 목표 원) |
| 영속화 | `settings.json` 에 저장 |
| 계산 | `saved = abs(df[df.소분류=="적금/저축"]["거래금액"].sum())` |
| 컴포넌트 | `st.progress(saved/goal)` + `st.metric` 3개(누계/월평균/예상 연말) |
| 우선순위 | **P1** |

---

## 4. 변경 vs 유지 (기존 app.py 기준)

### 유지 (수정 없음)
- 사이드바 파일 업로드 / 기본파일 체크박스 / 데이터 로드 버튼 로직
- Tab 1 KPI 카드 4종, 도넛 차트, 6개월 스택 바, 고정/변동 테이블
- Tab 3 지출 내역 필터(4열) / 소계(3열) / 테이블 / CSV
- Tab 4 수입 내역 전체
- Tab 5 카테고리 관리 A/B/C/E 섹션
- `utils.py` 의 `rules`, `categorize`, `build_monthly_kpis`, `load/save_overrides`, `detect_account_name`

### 변경 (수정)
| 파일 | 변경 내용 | 우선 |
|---|---|---|
| `utils.py` | `PASSWORD` 상수 제거, `decrypt/load_excel`에 `password` 파라미터 추가 | P1 |
| `utils.py` | `apply_categorization` 벡터화 또는 `@st.cache_data` 래퍼 추가 | P1 |
| `utils.py` | `detect_fixed_candidates()` 신규 함수 | P1 |
| `utils.py` | `load_budgets()/save_budgets()/load_settings()/save_settings()` 신규 | P1 |
| `app.py` 사이드바 | 비밀번호 입력 위젯 + 예산 설정 expander | P1 |
| `app.py` Tab 1 | 예산 진행바 섹션 추가 (도넛 위) | P1 |
| `app.py` Tab 5(카테고리) | 고정비 자동 탐지 섹션 D 추가 | P1 |
| `app.py` Tab 6(수익률) | 저축 목표 진행도 섹션 활성화 | P1 |

### 추가 (신규)
| 대상 | 내용 | 우선 |
|---|---|---|
| 신규 탭 | 🗓 주간 점검 탭 (Tab 2 위치) | P1 |
| 신규 파일 | `.streamlit/secrets.toml` (gitignore) | P1 |
| 신규 파일 | `budgets.json`, `settings.json` | P1 |
| Tab 3 지출내역 | 드릴다운 연동 배너 | P2 |
| Tab 1 | MoM/YoY 토글 | P2 |
| 신규 탭/섹션 | 자연어 검색 `st.chat_input` | P2 |

---

## 5. 개발 우선순위

### Phase 1 — MVP 즉시 구현 (금주 내)
1. **PASSWORD 하드코딩 제거** — `st.secrets` + 사이드바 `st.text_input(type="password")` fallback
2. **`apply_categorization` 성능 개선** — `@st.cache_data` 적용 또는 벡터화
3. **예산 설정 + 초과 경고** — 사이드바 expander + 대시보드 `st.progress` 바 + 80%/100% 경고
4. **고정비 자동 탐지 제안** — 카테고리 관리 탭 D 섹션 (`detect_fixed_candidates` + 적용 버튼)
5. **주간 점검 탭 신규** — `isocalendar().week` 기준 요약
6. **저축 목표 진행도** — Tab 6에서 활성화

### Phase 2 — 고도화 (이후 개선)
- 카테고리 드릴다운 연동 (도넛 → 지출 탭 자동 필터)
- MoM/YoY 델타 토글
- 자연어 검색 (`st.chat_input` + 룰 파서)
- Rebalance 제안 (예산 초과 시 여유 카테고리 추천)
- 주거 소분류 세분화 (수도/전기/가스/관리비)
- 간편결제 원가맹점 파싱 (네이버페이/카카오페이/토스페이)
- 정기구독 확장 (쿠팡와우, 네이버플러스, 디즈니+, 티빙, 라프텔, 요기요)
- 다크모드 / glassmorphism 테마 (`config.toml`)

---

## 6. 데이터 흐름도

```
[xlsx 파일]  +  [secrets.xlsx_password 또는 사이드바 입력]
     │
     ▼
load_excel(source, name, password) ─── @st.cache_data
     │
     ▼
st.session_state.raw_df (원본 pandas DataFrame)
     │
     ▼  + overrides.json
apply_categorization() ─── @st.cache_data 또는 벡터화
     │
     ▼
st.session_state.df (대분류/소분류/IsFixed/연월 컬럼 추가)
     │
     ├──► build_monthly_kpis(df, ym) ─► Tab 1 KPI / 6개월 추이
     ├──► df.groupby(소분류).sum()   ─► Tab 1 예산 진행바 ◄── budgets.json
     ├──► df[연주차==w]              ─► Tab 2 주간 점검
     ├──► df[대분류 in 지출]         ─► Tab 3 지출내역
     ├──► df[대분류=="수입"]         ─► Tab 4 수입내역
     ├──► detect_fixed_candidates(df) ─► Tab 5 D 섹션 ─► overrides.json 갱신
     └──► df[소분류=="적금/저축"]    ─► Tab 6 저축 진행도 ◄── settings.json
```

---

## 7. 사용자 스토리 (QA 테스트 케이스 기준)

### US-01: xlsx 비밀번호 보안 [P1]
- **Given** `secrets.toml`에 `xlsx_password` 설정되어 있음
- **When** 앱 실행 → 파일 업로드 → 데이터 로드 클릭
- **Then** 하드코딩 없이 secrets 값으로 복호화 성공. 소스코드 grep `"911017"` 결과 없음.

### US-02: 비밀번호 런타임 입력 [P1]
- **Given** secrets 미설정 또는 다른 비밀번호 파일
- **When** 사이드바 비밀번호 입력란에 값 입력 후 데이터 로드
- **Then** 해당 값으로 복호화. 입력란은 `type="password"`로 마스킹.

### US-03: 예산 설정 & 저장 [P1]
- **Given** 데이터가 로드되어 있음
- **When** 사이드바 예산 expander에서 "식비" 500,000 입력 후 저장
- **Then** `budgets.json`에 기록되고, 앱 재실행 후에도 값이 유지됨.

### US-04: 예산 초과 경고 [P1]
- **Given** 식비 예산 100,000원 설정, 이번 달 식비 지출 120,000원
- **When** 대시보드 탭 진입
- **Then** `st.progress(1.0)` + "⚠️ 식비 예산 초과 (120%)" 경고 표시.

### US-05: 고정비 자동 탐지 [P1]
- **Given** "KT 통신요금"이 3개월 연속 54,000 / 55,000 / 56,000 원으로 존재
- **When** 카테고리 관리 탭 D 섹션 진입
- **Then** 해당 적요가 제안 리스트에 출현. [적용] 클릭 → `overrides.json`에 `IsFixed=True` 저장.

### US-06: 주간 점검 뷰 [P1]
- **Given** 데이터에 2026-W15 거래가 있음
- **When** 주간 점검 탭 → 주차 "2026-W15" 선택
- **Then** 해당 주 KPI / 일자별 막대 / Top5 카테고리가 정확히 표시.

### US-07: 저축 목표 진행도 [P1]
- **Given** `savings_goal = 12,000,000` 설정, 올해 누적 적금/저축 4,850,000
- **When** Tab 6 진입
- **Then** 진행바 40.4%, 예상 연말 달성률 계산 결과 표시.

### US-08: 성능 (캐싱) [P1]
- **Given** 5,000행 이상 xlsx 로드
- **When** 월 선택 변경만 수행
- **Then** `apply_categorization`가 재실행되지 않음 (캐시 hit). 월 변경 응답 < 500ms.

### US-09: 드릴다운 연동 [P2]
- **Given** 대시보드에서 "카페/음료" 선택
- **When** 지출 내역 탭 이동
- **Then** 소분류 필터가 자동으로 "카페/음료"로 세팅되고 배너 표시.

---

## 8. 협업 Handoff

- **streamlit-dev**: 본 문서의 Phase 1 항목 6가지를 순서대로 구현. `utils.py` 변경 먼저 → `app.py` 통합.
- **qa-engineer**: §7 사용자 스토리 US-01 ~ US-08을 테스트 케이스로 변환. 특히 US-08(캐싱)은 `time.time()`으로 벤치마크.
- **deployer**: `.streamlit/secrets.toml`를 `.gitignore`에 포함 확인. 배포 환경(Streamlit Cloud/Docker)에서 secrets 주입 방식 문서화.
