---
name: streamlit-deploy
description: 가계부 앱을 Streamlit Cloud 또는 로컬 서버에 배포하는 스킬. "배포해줘", "deploy", "Streamlit Cloud 올려줘", "서버에 올려", "배포 설정" 요청 시 트리거. QA 통과 후 최종 배포 단계에서 실행한다.
---

# Streamlit 배포 스킬

## 목표

QA 통과된 가계부 앱을 Streamlit Cloud 또는 로컬 서버에 안전하게 배포한다.

## 배포 전 필수 확인

### 1. QA 통과 확인
```bash
# _workspace/qa_report.md에서 전체 통과 상태 확인
grep -i "전체 통과\|all passed" /Users/mw/prodect/통장/_workspace/qa_report.md
```

### 2. 보안 감사
```bash
# 하드코딩된 비밀번호 검색
grep -n "911017\|password.*=.*\"" /Users/mw/prodect/통장/app.py
grep -n "911017\|PASSWORD.*=.*\"" /Users/mw/prodect/통장/utils.py
```

### 3. .gitignore 확인
필수 제외 항목:
- `*.xlsx` — 개인 거래내역
- `overrides.json` — 사용자 재지정 데이터
- `.env`, `.streamlit/secrets.toml` — 환경 변수
- `_workspace/` — 중간 산출물

### 4. requirements.txt 동기화
```bash
# 실제 import와 비교
grep -h "^import\|^from" /Users/mw/prodect/통장/app.py /Users/mw/prodect/통장/utils.py | sort -u
```

## Streamlit Cloud 배포

### GitHub 저장소
- URL: https://github.com/jihogitgit/household_account_book.git
- 브랜치: main

### 배포 단계
1. `git add app.py utils.py requirements.txt .gitignore`
2. `git commit -m "feat: 가계부 Streamlit 앱 배포"`
3. `git push origin main`
4. Streamlit Cloud (share.streamlit.io) 에서 저장소 연결
5. Main file path: `app.py`

## 로컬 서버 배포

```bash
cd /Users/mw/prodect/통장
pip install -r requirements.txt
streamlit run app.py --server.port 8502 --server.headless true
```

백그라운드 실행:
```bash
nohup streamlit run app.py --server.port 8502 > streamlit.log 2>&1 &
```

## 배포 후 검증 체크리스트

- [ ] 앱이 브라우저에서 로드됨
- [ ] 사이드바 파일 업로드 UI 표시됨
- [ ] xlsx 업로드 + 비밀번호 입력 후 데이터 로드됨
- [ ] 5개 탭 전환 정상 동작
- [ ] 대시보드 KPI 카드 표시됨
- [ ] 도넛차트 렌더링됨
- [ ] 카테고리 관리 탭에서 재지정 저장됨

## 출력

`_workspace/deploy_report.md`에 기록:
- 배포 타겟 (Cloud/로컬)
- 배포 URL
- 배포 시각
- 검증 결과
- 주의사항 (비밀번호 입력 필요 등)
