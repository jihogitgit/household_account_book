# Deploy Report — 가계부 Streamlit 앱

- **배포 준비일**: 2026-04-14
- **대상**: `/Users/mw/prodect/통장/`
- **실행자**: deployer 에이전트
- **QA 상태**: 통과 (qa_report.md 전체 PASS 확인)

---

## 1. 배포 전 체크리스트 결과

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | `app.py` 문법/임포트 정상 | PASS | `streamlit, pandas, plotly.express, plotly.graph_objects`, `pathlib`, `warnings`, `utils` |
| 2 | `utils.py` 문법/임포트 정상 | PASS | `io, json, pathlib, msoffcrypto, pandas` |
| 3 | `requirements.txt` ↔ 실제 import 일치 | PASS | streamlit / pandas / msoffcrypto-tool / openpyxl / plotly 5개 모두 커버 |
| 4 | `app.py` / `utils.py` 하드코딩 비밀번호 부재 | PASS | `911017` 문자열 없음 (QA에서 이미 검증) |
| 5 | `app.py` / `utils.py` 하드코딩 경로 부재 | PASS | `/Users/mw/prodect/통장` 문자열 없음 |
| 6 | `.gitignore`에 민감파일 제외 | PASS | `*.xlsx`, `overrides.json`, `budgets.json`, `.streamlit/secrets.toml`, `.env`, `__pycache__/` 포함 |
| 7 | `load_overrides()` / `load_budgets()` 파일 부재 시 graceful 처리 | PASS | 기본값 반환 |
| 8 | `st.secrets.get("xlsx_password","")` → 사용자 입력 fallback | PASS | `app.py`에서 확인 |

### 보안 경고 (BLOCKER 후보)

리포지토리에 **이미 커밋된** 레거시 스크립트에 비밀번호/절대경로가 하드코딩되어 있다:

- `/Users/mw/prodect/통장/categorize.py`
  - line 5: `base = '/Users/mw/prodect/통장/'`
  - line 12: `password = '911017'`
- `/Users/mw/prodect/통장/make_report.py`
  - line 8: `base = '/Users/mw/prodect/통장/'`
  - line 15: `password = '911017'`

이 두 파일은 **Streamlit 앱이 import 하지 않으며** (grep으로 `app.py`에서 참조 없음 확인), QA 대상도 아니다.
그러나 GitHub 공개 저장소(`household_account_book`)에 이미 push 된 상태라면 **비밀번호 `911017`이 공개**되어 있을 가능성이 있다.

**권고 (사용자 결정 필요):**
1. `categorize.py`, `make_report.py`를 삭제하고 `git rm` 커밋 (레거시로 더 이상 필요 없음)
2. 또는 내부 상수를 `os.environ.get("XLSX_PASSWORD")`로 치환하고 `.env`는 gitignore 처리
3. 이미 push 된 이력은 `git filter-repo`/GitHub history rewrite로 제거하거나, 비밀번호 자체를 변경 권고

---

## 2. 실행 / 배포 방법

### 2-1. 로컬 실행

```bash
cd /Users/mw/prodect/통장
pip install -r requirements.txt
streamlit run app.py --server.port 8502
```

- 접속 URL: http://localhost:8502
- 백그라운드 실행:
  ```bash
  nohup streamlit run app.py --server.port 8502 > streamlit.log 2>&1 &
  ```

### 2-2. Streamlit Cloud 배포 (share.streamlit.io)

1. https://share.streamlit.io 로그인 (GitHub 계정 연동)
2. **New app** 클릭
3. 저장소: `jihogitgit/household_account_book`
4. Branch: `main`
5. Main file path: `app.py`
6. **Advanced settings → Secrets** 란에 아래 내용 붙여넣기:
   ```toml
   xlsx_password = "여기에_엑셀_비밀번호"
   ```
7. **Deploy** 클릭 → 자동 빌드
8. 배포 완료 후 URL 확정 (현재 미확정)

### 2-3. secrets.toml 설정 (로컬에서 secrets를 쓰려면)

`/Users/mw/prodect/통장/.streamlit/secrets.toml` 생성 (이미 `.gitignore` 처리됨):

```toml
# .streamlit/secrets.toml
xlsx_password = "본인의_토스뱅크_엑셀_비밀번호"
```

설정하면 `app.py`가 사이드바에서 비밀번호 입력을 자동으로 채운다. 비워두면 사용자가 업로드 시 직접 입력.

---

## 3. 사용자 매뉴얼 요약

1. **접속** → 로컬: http://localhost:8502 / 클라우드: 배포 URL
2. **사이드바**에서 토스뱅크 `.xlsx` 파일 업로드 (1개 또는 복수)
3. **비밀번호 입력** (secrets.toml에 저장했으면 생략 가능)
4. **"데이터 로드" 버튼** 클릭 → 파일 복호화 + 카테고리 분류 자동 실행
5. **5개 탭** 이용:
   - 대시보드 (KPI 카드, 도넛차트)
   - 월별 추이
   - 거래 내역
   - 카테고리 관리 (override 저장)
   - 예산 관리

### 주의사항

- `overrides.json`, `budgets.json`은 앱 루트에 저장되며 gitignore 대상. 로컬 사용자 상태만 보존됨.
- Streamlit Cloud 환경에서는 컨테이너 재시작 시 override/budget 파일이 초기화될 수 있음 (영구 저장 필요 시 DB 또는 외부 스토리지 연동 필요).

---

## 4. Git 상태

### 현재 상태
```
브랜치: main (origin/main 동기화됨)
원격: https://github.com/jihogitgit/household_account_book.git

변경된 추적 파일:
  modified: .gitignore  (+4 lines)
  modified: app.py      (+167 / -2 lines)
  modified: utils.py    (+95 / -7 lines)

미추적:
  .claude/        ← 하네스 설정. 커밋 여부는 선택.
  _workspace/     ← 중간 산출물. 커밋 제외 권고.

최근 커밋:
  c38da88 feat: 토스뱅크 거래내역 자동 분류 가계부 앱 초기 커밋
```

### 제안 커밋 계획 (사용자 확인 대기)

다음 파일만 스테이징:
- `app.py`
- `utils.py`
- `.gitignore`
- `requirements.txt` (변경 없음, 스테이징 불필요)

**커밋 메시지 초안:**
```
feat: Streamlit 가계부 앱 전면 개편 (5탭 UI + 예산/override 관리)

- app.py: 5개 탭(대시보드/월별추이/거래내역/카테고리/예산) UI 구성,
  KPI 카드, 도넛/바 차트, override/budget 편집 지원
- utils.py: categorize() 규칙 확장(KT/LG/SK 통신사 주거/통신 분류),
  apply_categorization() 파생 컬럼 6종, build_monthly_kpis() KPI 집계,
  save/load_overrides, save/load_budgets (0원 필터링), detect_fixed_candidates 추가
- .gitignore: budgets.json, .streamlit/secrets.toml, .env 추가 제외
- xlsx_password는 st.secrets 또는 사용자 입력으로 주입 (하드코딩 제거)
```

### _workspace/deploy_report.md에 명시하는 push 대상 파일 목록

```
app.py
utils.py
.gitignore
```

### 실행 예정 명령 (사용자 확인 후)

```bash
cd /Users/mw/prodect/통장
git add app.py utils.py .gitignore
git commit -m "feat: Streamlit 가계부 앱 전면 개편 (5탭 UI + 예산/override 관리)"
git push origin main
```

---

## 5. 배포 URL 상태

- **로컬**: http://localhost:8502  (실행 시 활성화)
- **Streamlit Cloud**: 미확정 (share.streamlit.io 연결 후 확정)

---

## 6. 다음 단계 (사용자 액션)

1. **보안 조치 결정** — `categorize.py` / `make_report.py`의 하드코딩된 `password='911017'` 처리 방침 결정 (삭제 / env 치환 / 비밀번호 교체)
2. **커밋/푸시 승인** — 위 "제안 커밋 계획" 검토 후 승인하면 deployer가 실행
3. **Streamlit Cloud 연결** — share.streamlit.io에서 저장소 연결 + secrets 입력
4. **배포 후 검증** — 5개 탭 정상 동작 확인 (qa_report.md 체크리스트 재사용)
