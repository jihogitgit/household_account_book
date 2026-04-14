---
name: streamlit-builder
description: 가계부 app.py와 utils.py를 구현하거나 수정하는 스킬. "개발해줘", "코딩해줘", "구현해줘", "탭 추가", "차트 추가", "버그 수정", "기능 개선" 등 실제 코드 작성 요청 시 트리거. 와이어프레임을 Python/Streamlit 코드로 변환한다.
---

# Streamlit 빌더 스킬

## 목표

`_workspace/wireframe.md` 설계를 바탕으로 `/Users/mw/prodect/통장/app.py`, `utils.py`를 구현·개선한다.

## 기술 스택

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| streamlit | ≥1.32 | UI 렌더링, 상태 관리 |
| pandas | ≥2.0 | DataFrame 처리 |
| plotly | ≥5.18 | px.pie (도넛), go.Figure (바차트) |
| msoffcrypto-tool | ≥5.4 | CDFV2 암호화 xlsx 복호화 |
| openpyxl | ≥3.1 | xlsx 파일 엔진 |

## 핵심 구현 패턴

### 암호화 xlsx 로드
```python
import msoffcrypto, io
def decrypt(source) -> io.BytesIO:
    buf = io.BytesIO()
    if isinstance(source, (str, Path)):
        f = open(source, 'rb')
    else:
        source.seek(0); f = source  # st.file_uploader 호환
    office = msoffcrypto.OfficeFile(f)
    office.load_key(password=PASSWORD)
    office.decrypt(buf)
    buf.seek(0)
    return buf
```

### Session State 구조
```python
st.session_state = {
    "raw_df": pd.DataFrame,       # 복호화+원본 (재분류용)
    "df":     pd.DataFrame,       # 분류 완료 (탭 표시용)
    "overrides": dict,            # {적요: {대분류, 소분류, IsFixed}}
    "selected_month": str,        # "2026-04"
}
```

### Streamlit 베스트 프랙티스
- `@st.cache_data` — 파일 바이트 + 파일명 키로 복호화+로드 캐싱
- `st.session_state` — 탭 전환 후에도 데이터 유지
- `st.fragment` — 부분 리렌더링 (Streamlit 1.33+)
- 탭 내 `st.stop()` 절대 사용 금지 → `if/else:` 블록으로 대체
- CSS 주입으로 헤더 제거 + 패딩 조정

### CSS 픽스 (필수 포함)
```python
st.markdown("""<style>
  #MainMenu { visibility: hidden; }
  header[data-testid="stHeader"] { height: 0; min-height: 0; }
  .block-container { padding-top: 2rem !important; }
</style>""", unsafe_allow_html=True)
```

### KPI 카드 패턴
```python
col1, col2, col3, col4 = st.columns(4)
col1.metric("총수입", f"{kpis['총수입']:,}원",
            delta=f"{kpis['총수입'] - kpis['prev']['총수입']:,}원")
```

### 도넛차트
```python
import plotly.express as px
fig = px.pie(df_exp, values='거래금액', names='소분류',
             hole=0.55, color='소분류',
             color_discrete_map=CAT_COLOR_PLOTLY)
st.plotly_chart(fig, width='stretch')
```

## 작업 원칙

1. 기존 `app.py` 먼저 읽고 변경 범위 최소화 — 전체 재작성 금지
2. 기능 단위로 구현하고, 각 단위 완료 후 qa-engineer에게 SendMessage
3. 보안: 비밀번호 하드코딩 없이 `st.text_input(type="password")` 사용
4. 한국어 UI 유지
5. openpyxl PatternFill에 6자리 RGB hex 사용 (8자리 ARGB 사용 시 ValueError 발생)

## 작업 순서

1. `_workspace/wireframe.md` 읽기
2. 기존 `app.py`, `utils.py` 읽기
3. 변경이 필요한 부분만 Edit 도구로 수정
4. 기능 단위 완료마다 qa-engineer에게 검증 요청
