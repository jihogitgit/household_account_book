# 가계부 앱 리서치 리포트

> 작성일: 2026-04-14
> 범위: 한국(뱅크샐러드·토스·카카오뱅크) + 글로벌(YNAB·Copilot·머니포워드)
> 대상 앱: `/Users/mw/prodect/통장` (Streamlit 기반, 토스뱅크 xlsx 자동 분류)

---

## 1. 경쟁 앱 비교 (기능 표)

| 기능 영역 | 뱅크샐러드 | 토스 | 카카오뱅크 | YNAB | Copilot (iOS) | 머니포워드 |
|---|---|---|---|---|---|---|
| 포지셔닝 | 데이터 기반 정밀 분석 | 심플/라이프스타일 | 은행 통합 기본 | 제로베이스 예산 | AI 프리미엄 대시보드 | 자산 통합(일본) |
| 자동 분류 | ◎ 머신러닝 기반 | ○ 기본 분류 | △ 단순 | 수동(철학) | ◎ AI 예측·Rebalance | ◎ 다계좌 통합 |
| 고정/변동 구분 | ○ 태그 가능 | △ 카테고리만 | △ | ◎ 카테고리 할당 | ◎ Recurring 자동 탐지 | ○ |
| 월별 리포트 | ◎ 드릴다운 | ◎ 주간/월간 요약 | ○ | ○ | ◎ 도넛+트렌드 | ○ |
| 예산 설정 | ○ 카테고리별 | ○ 챌린지 기반 | △ | ◎ (제로베이스) | ◎ AI 재배분 | ○ |
| 목표/저축 | ○ | ◎ 목표통장 | ◎ 세이프박스 | ◎ | ○ | ○ |
| 수기 수정 UX | 적요 일괄 재지정 | 개별 수정 | 개별 | 수동 입력 | 룰 기반 학습 | 일괄 수정 |
| 대시보드 톤 | 그래프 중심 | 큰 숫자·카드 | 미니멀 | 표 중심 | 글래스모피즘 | 정보 밀도 높음 |
| 웹 버전 | ○ | △ | △ | ◎ | ◎(2026 확장) | ◎ |

**핵심 시사점:** 2026년 트렌드는 "자동 분류 정확도 + AI 재배분(rebalance) + 예측(forecast)" 3축. 단순 "보여주기"를 넘어 능동적 제안(adaptive budgeting)으로 이동 중.

---

## 2. 사용자가 가장 중요하게 여기는 기능 TOP 10

앱스토어 리뷰·커뮤니티 종합 (영문/한국어):

1. **자동 분류 정확도** — 1순위 불만/요구 포인트. 주유소가 "카페"로 잡히는 류의 오분류 사례 빈번 (Quicken Simplifi 리뷰).
2. **고정/정기 지출 자동 탐지** — "recurring expense detection" 미흡이 budgeting 기능 불만의 핵심 (NerdWallet 2026).
3. **일괄 재분류(bulk recategorize)** — PocketGuard는 무료 횟수 제한으로 악평. 한국 유저는 "적요 단위 일괄 변경"을 선호.
4. **월별 수입/지출 한눈에 보기** — "큰 숫자 + 전월 대비 증감" 카드 UX (토스 영향).
5. **카테고리 드릴다운** — 도넛→리스트→거래 상세 3단계 (Copilot, 뱅크샐러드 공통 패턴).
6. **주간 루틴화** — 2026년 한국 권장은 "매일 쓰지 말고 주 1회 15분 점검" (luluworldya 2026).
7. **예산 초과 경고** — 카테고리별 진행 바, 남은 일수 기준 예측.
8. **여러 통장 통합 뷰** — 한국 유저의 "생활비/경조사/급여" 통장 분리 관행 반영 필요.
9. **목표 저축 시각화** — 토스 목표통장, 카카오뱅크 세이프박스가 벤치마크.
10. **CSV/엑셀 내보내기** — 파워유저의 기본 요구.

---

## 3. 효과적인 대시보드 UX 패턴

### 3.1 레이아웃 패턴 (2026 공통)
- **상단 KPI 카드 4~5개** — 수입/고정/변동/순수지 + 전월 대비 델타(색상 반전 주의: 지출 감소=green).
- **도넛 + 범례 사이드** — 카테고리 비중. Copilot은 hole=0.55~0.6, tap-to-expand.
- **최근 6개월 스택 바 + 순수지 라인 오버레이** — 현재 앱에 이미 구현됨 ✅.
- **드릴다운 흐름** — 도넛 클릭 → 거래 리스트 필터링 자동 적용 (현재 앱은 탭 전환 필요, 개선 여지).

### 3.2 색상/시각 트렌드
- **Copilot "liquid glass"** 스타일이 2026 표준화 중 (부드러운 그라데이션 배경).
- 수입=초록 계열, 고정지출=블루, 변동=옐로/오렌지, 경조사=핑크 — 현재 앱 팔레트와 일치 ✅.
- 미분류(미분류 강조 레드)는 action-needed 신호로 active.

### 3.3 인터랙션 패턴
- **주간 점검 모드(weekly check-in)** — 월 단위가 아닌 주 단위 요약 화면을 별도 탭으로 두는 추세.
- **AI 챗/자연어 검색** — "지난 달 배달음식 얼마 썼어?" 같은 쿼리 (Copilot 2026 신기능). Streamlit에서는 `st.chat_input` + 단순 필터 매핑으로 구현 가능.
- **Rebalance 제안** — 카테고리 초과 시 다른 카테고리 잉여분을 자동 추천.

---

## 4. Streamlit 구현 우선순위 추천

### 4.1 MVP 이미 구현됨 ✅
- KPI 카드 4종 + 전월 델타
- 도넛 차트 (소분류)
- 6개월 스택 바 + 순수지 라인
- 고정/변동 테이블
- 적요 단위 override + 일괄 편집 (`st.data_editor`) — **경쟁 앱 대비 오히려 우위**
- 미분류 리스트 액션 프롬프트

### 4.2 즉시 개선 권장 (High ROI, Streamlit 쉬움)
| 우선 | 기능 | Streamlit 구현 |
|---|---|---|
| P1 | **예산 설정 + 초과 경고** | `st.number_input` 카테고리별 예산 → `st.progress` 진행바 |
| P1 | **주간 점검 뷰** | 탭 추가, `isocalendar().week` 기준 그룹 |
| P1 | **고정비 자동 탐지 개선** | 3개월 이상 동일 적요·유사 금액 → IsFixed 자동 추천 |
| P2 | **전년 동월 비교** | delta 계산을 MoM + YoY 토글 |
| P2 | **카테고리 드릴다운 연동** | `st.session_state`에 클릭한 소분류 저장 → 지출탭 필터 자동 세팅 |
| P2 | **목표 저축 진행도** | Tab 5 수익률을 "저축 목표 진행도"로 우선 활성화 |

### 4.3 고도화 (Streamlit 한계 주의)
| 기능 | 구현 가능성 | 비고 |
|---|---|---|
| AI 자연어 검색 | ○ | `st.chat_input` + 키워드 파싱, LLM 연동 시 claude-api 스킬 활용 |
| Rebalance 제안 | ○ | 규칙 기반으로 충분 (LLM 불필요) |
| 다크모드/glassmorphism | △ | CSS 주입 한계, config.toml 테마로 근사 |
| 실시간 거래 동기화 | × | **Streamlit 외 도구 필요** — 오픈뱅킹 API + DB 백엔드 |
| PWA/모바일 최적화 | △ | Streamlit은 반응형 제한적, 태블릿 이상 권장 |
| 드래그&드롭 카테고리 편집 | × | 커스텀 컴포넌트 필요 (Components v2로 가능하나 공수 큼) |

---

## 5. 한국 사용자 특화 요소

### 5.1 거래 구조 (현재 앱 반영됨 ✅)
- **토스뱅크 xlsx 헤더=8행** — load_excel `header=8` OK.
- **거래 유형 다양성**: `체크카드결제`, `자동이체`, `내계좌간자동이체`, `지로출금`, `ATM출금`, `모임원송금`, `이자입금`, `프로모션입금` — 현재 rules가 잘 커버.
- **암호화된 xlsx (msoffcrypto)** — 한국 은행 공통 관행, 현재 구현 OK.

### 5.2 지출 카테고리 한국 맥락
- **공과금 = 지로출금** 매핑 (현재 앱 ✅).
- **통신비**: KT/LG/SK 3사 키워드 (현재 앱 ✅).
- **경조사**: 별도 통장 운영 문화 (현재 앱이 `_통장 == "경조사"`로 대분류 처리 — 탁월).
- **정기구독**: 넷플릭스/유튜브/웨이브/왓챠/스포티파이 (현재 앱 ✅), **추가 권장: 쿠팡와우, 네이버플러스, 디즈니+, 티빙, 라프텔**.
- **배달**: 우아한형제들/쿠팡이츠 (현재 앱 ✅), **요기요** 추가 권장.
- **간편결제**: 네이버페이, 카카오페이, 토스페이 — 소분류에서 원 가맹점 소실 이슈. 한국 특수 문제.

### 5.3 한국 금융 관행
- **청년도약계좌/청약** 키워드 별도 매핑 (현재 앱 ✅).
- **모임통장**: 정산/출금 양방향 구분 (현재 앱 ✅, rules 섬세함 우수).
- **내부이체 제외** KPI 계산: 생활비·여행비 이체는 중복 집계되면 안 됨 (현재 앱 `~df["대분류"].isin(["내부이체"])` ✅).

### 5.4 주거 관련 (개선 여지)
- 현재 "월세/주거"는 적요 == "월세/이자" exact match. 관리비/전세대출이자/수도세/가스비 등 세분화 필요.
- 공과금 아래 **수도·전기·가스·관리비** 소분류 추가 권장.

---

## 6. 기술 제약 (Streamlit 2026 기준)

### 6.1 버전 현황
- Streamlit 1.54+ (2026) 기준: **Custom Components v2** 도입 → React 위젯 임베드 개선.
- `st.tabs`, `st.popover`, `st.expander`에 `on_change` 콜백 및 프로그래매틱 open/close 지원 (신규).
- 현재 앱은 기본 컴포넌트만 사용 → 호환성 높음.

### 6.2 핵심 제약
- **전체 스크립트 재실행 모델**: 사용자 인터랙션마다 script rerun. 대용량 xlsx에 `@st.cache_data` 필수 (현재 미적용 — **개선 권장**).
- **파일 업로드 메모리**: Streamlit은 session 기반. `st.session_state.raw_df` 유지는 OK지만 멀티 유저 배포 시 메모리 누적.
- **차트 인터랙션**: Plotly click-event를 파이썬으로 받으려면 `streamlit-plotly-events` 커스텀 컴포넌트 필요.
- **모바일 레이아웃**: `st.columns`가 모바일에서 세로 스택 자동. 폰 최적화는 제한적.
- **인증/다중 사용자**: 기본 미지원. Streamlit Community Cloud의 OIDC 또는 `streamlit-authenticator` 라이브러리 필요.

### 6.3 성능 권장
```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_excel_cached(source_bytes: bytes, account_name: str) -> pd.DataFrame:
    ...
```
- `apply_categorization`의 `df.apply(...)`는 수만 행 이상에서 느림 → 벡터화(dict lookup + np.select) 또는 `@st.cache_data` 적용.

### 6.4 배포 옵션
- **Streamlit Community Cloud**: 무료, GitHub 연동, 공개 리포 제약.
- **Docker + 개인 서버**: 암호화 xlsx 비밀번호(현재 하드코딩된 `911017`)는 `st.secrets`로 이전 필수.
- **보안**: `PASSWORD = "911017"`이 코드 하드코딩 → secrets.toml로 분리 권장.

---

## 7. 현재 앱 SWOT (요약)

**Strengths**
- 한국 거래 유형/관행 반영도가 매우 높음 (경조사 통장, 청년도약, 지로출금).
- `overrides.json` + `st.data_editor` 기반 적요 단위 재분류 UX는 **경쟁 앱보다 빠름**.
- 대시보드 시각 언어(색상, KPI 델타)가 2026 트렌드와 일치.

**Weaknesses**
- 예산 설정/초과 경고 부재.
- 주간 점검 뷰 없음.
- PASSWORD 하드코딩, `@st.cache_data` 미적용.
- 간편결제(네이버페이/카카오페이/토스페이) 원가맹점 소실.

**Opportunities**
- 고정비 자동 탐지(3개월 규칙)로 IsFixed 자동화 → 수동 설정 부담 감소.
- 자연어 검색(`st.chat_input` + 룰 파서)로 차별화.
- 목표 저축 진행도(Tab 5 활성화)로 토스 벤치마크.

**Threats**
- 토스/뱅크샐러드의 오픈뱅킹 자동 수집 대비, xlsx 수동 업로드는 번거로움.
- Streamlit의 모바일 UX 한계 → 폰 유저 이탈 가능성.

---

## 출처

- [가계부 앱 추천 2026: 토스 vs 뱅크샐러드 — luluworldya](https://luluworldya.com/125)
- [토스 vs 뱅크샐러드 가계부 앱 비교 — smartlifepick](https://smartlifepick.com/entry/토스-vs-뱅크샐러드-가계부-앱-비교-기능-예산관리-UI)
- [뱅크셀러드, 토스 소비/가계부 비교 — Weekly UX/UI Challenge](https://weeklyuxuichallenge.oopy.io/f9b6105e-9473-42ca-bfa3-295c6ee086a5)
- [Copilot Money Review 2026 — The College Investor](https://thecollegeinvestor.com/41976/copilot-review/)
- [Copilot Money Spend Insights & AI Intelligence 2026 — aitools-directory](https://www.aitools-directory.com/tools/copilot-money-spend-insights/)
- [Best Budget Apps for 2026 — NerdWallet](https://www.nerdwallet.com/finance/learn/best-budget-apps)
- [Best Budgeting Apps 2026: Top 6 Compared — costbench](https://costbench.com/best/best-budgeting-apps/)
- [Top Personal Finance Apps with Customizable Categories — Quicken](https://www.quicken.com/blog/top-personal-finance-apps-with-customizable-budget-categories/)
- [Streamlit 2026 Release Notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026)
- [Streamlit vs Dash Python Dashboards April 2026 — Reflex](https://reflex.dev/blog/streamlit-vs-dash-python-dashboards/)
