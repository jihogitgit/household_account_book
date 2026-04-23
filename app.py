"""
가계부 Streamlit 앱
실행: streamlit run app.py
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database import get_db
from tabs.investment import render_investment_tab
from tabs.pension import render_pension_tab
from tabs.savings import render_savings_tab
from utils import (
    CAT_COLOR_PLOTLY, SUBCAT_COLORS,
    apply_categorization, build_monthly_kpis,
    detect_account_name, detect_fixed_candidates,
    load_budgets, load_excel, load_overrides,
    rules, save_budgets, save_overrides,
)

BASE_DIR = Path(__file__).parent


def _normalize_db_df(df: pd.DataFrame) -> pd.DataFrame:
    """DB에서 로드한 DataFrame을 앱 내부 형식으로 변환."""
    df = df.rename(columns={"통장": "_통장", "거래유형": "거래 유형", "is_fixed": "IsFixed"})
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce").dt.date
    df["IsFixed"] = df["IsFixed"].astype(bool)
    return df


# ── 기본 설정 ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="가계부",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  /* 상단 헤더/햄버거 메뉴 영역 숨기기 */
  #MainMenu { visibility: hidden; }
  header[data-testid="stHeader"] { height: 0; min-height: 0; }
  footer { visibility: hidden; }

  /* 본문 상단 여백 확보 */
  .block-container {
    padding-top: 2rem !important;
    padding-bottom: 1rem !important;
  }

  /* 탭 스타일 */
  .stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: #F0F4FF;
    border-radius: 10px;
    padding: 4px 6px;
  }
  .stTabs [data-baseweb="tab"] {
    font-size: 14px;
    font-weight: 500;
    border-radius: 8px;
    padding: 6px 14px;
  }
  .stTabs [aria-selected="true"] {
    background: #FFFFFF;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12);
  }

  /* KPI 카드 */
  [data-testid="metric-container"] {
    background: #F8FAFF;
    border: 1px solid #E0EAFF;
    border-radius: 10px;
    padding: 14px 18px;
  }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(ttl=900)  # 15분간 서버 메모리에 유지
def _shared_cache():
    """페이지 새로고침 후에도 DataFrame을 15분간 보존하는 공유 캐시."""
    return {"raw_df": None, "df": None}


# ── Session State 초기화 ──────────────────────────────────────────────
if "overrides" not in st.session_state:
    st.session_state.overrides = load_overrides()
if "df" not in st.session_state:
    st.session_state.df = None
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "selected_month" not in st.session_state:
    st.session_state.selected_month = None
if "budgets" not in st.session_state:
    st.session_state.budgets = load_budgets()
# 탭 필터 초기값 (key 충돌 방지)
if "exp_month" not in st.session_state:
    st.session_state.exp_month = "전체"
if "exp_cat" not in st.session_state:
    st.session_state.exp_cat = ["고정지출", "변동지출", "경조사"]
if "inc_month" not in st.session_state:
    st.session_state.inc_month = "전체"

# ── 새로고침 후 캐시 복원 (15분 이내) ──────────────────────────────────
_cache = _shared_cache()
if st.session_state.df is None and _cache.get("df") is not None:
    st.session_state.raw_df = _cache["raw_df"]
    st.session_state.df = _cache["df"]
    _months = sorted(st.session_state.df["연월"].unique(), reverse=True)
    if st.session_state.selected_month is None and _months:
        st.session_state.selected_month = _months[0]
    if st.session_state.exp_month == "전체" and _months:
        st.session_state.exp_month = _months[0]
    if st.session_state.inc_month == "전체" and _months:
        st.session_state.inc_month = _months[0]


def _default_xlsx_password() -> str:
    """st.secrets 우선, 없으면 빈 문자열"""
    try:
        return st.secrets.get("xlsx_password", "")
    except Exception:
        return ""


# ── 사이드바 ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💰 채지pt쀼 가계부")
    st.caption("토스뱅크 거래내역 자동 분류")
    st.divider()

    st.subheader("📁 파일 업로드")
    uploaded_files = st.file_uploader(
        "xlsx 파일 선택 (복수 가능)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="토스뱅크 암호화된 거래내역 xlsx 파일",
        label_visibility="collapsed",
    )

    # 기본 파일 자동 로드 옵션
    use_default = st.checkbox(
        "기본 파일 사용 (통장 폴더)",
        value=(not uploaded_files),
        help="앱과 같은 폴더의 xlsx 파일 자동 로드",
    )

    # 🔑 xlsx 비밀번호 입력 (기본값: st.secrets → 없으면 빈값)
    default_pw = _default_xlsx_password() if use_default else ""
    password = st.text_input(
        "🔑 xlsx 비밀번호",
        type="password",
        value=default_pw,
        help="토스뱅크 암호화 xlsx 복호화 비밀번호. 기본값은 .streamlit/secrets.toml 의 xlsx_password",
        key="xlsx_password",
    )

    load_btn = st.button("🔄 데이터 로드", type="primary", width='stretch')

    # ── 파일 로드 처리 ──
    if load_btn:
        sources = []
        if uploaded_files:
            for f in uploaded_files:
                name = detect_account_name(f.name)
                sources.append((f, name))
        elif use_default:
            xlsx_files = list(BASE_DIR.glob("토스뱅크_거래내역*.xlsx"))
            for fp in xlsx_files:
                name = detect_account_name(fp.name)
                sources.append((str(fp), name))

        if not sources:
            st.error("파일을 찾을 수 없습니다.")
        elif not password:
            st.error("🔑 xlsx 비밀번호를 입력하세요.")
        else:
            with st.spinner("데이터 로딩 중..."):
                dfs = []
                errors = []
                for src, name in sources:
                    try:
                        dfs.append(load_excel(src, name, password))
                    except Exception as e:
                        errors.append(f"{name}: {e}")
                if errors:
                    for e in errors:
                        st.warning(e)
                if dfs:
                    raw = pd.concat(dfs, ignore_index=True)
                    st.session_state.raw_df = raw
                    st.session_state.df = apply_categorization(
                        raw, st.session_state.overrides
                    )
                    months = sorted(st.session_state.df["연월"].unique(), reverse=True)
                    st.session_state.selected_month = months[0] if months else None
                    # 탭 필터 초기값 리셋
                    st.session_state.exp_month = months[0] if months else "전체"
                    st.session_state.inc_month = months[0] if months else "전체"
                    st.session_state.exp_cat = ["고정지출", "변동지출", "경조사"]
                    # SQLite에 저장
                    saved = get_db().save_transactions(st.session_state.df)
                    # 캐시에 저장 (새로고침 후 15분간 복원)
                    _c = _shared_cache()
                    _c["raw_df"] = raw
                    _c["df"] = st.session_state.df
                    st.success(f"{len(st.session_state.df):,}건 로드 완료 (신규 {saved}건 저장)")
                    st.rerun()

    # ── DB에서 불러오기 ──
    _db = get_db()
    if _db.has_transactions() and st.session_state.df is None:
        st.divider()
        st.subheader("💾 저장된 데이터")
        months_in_db = _db.get_available_months()
        st.caption(f"총 {len(months_in_db)}개월 저장됨 ({months_in_db[-1] if months_in_db else '—'} ~ {months_in_db[0] if months_in_db else '—'})")
        if st.button("📂 DB에서 불러오기", use_container_width=True):
            with st.spinner("불러오는 중..."):
                loaded = _db.load_transactions()
                if not loaded.empty:
                    st.session_state.df = _normalize_db_df(loaded)
                    st.session_state.raw_df = None
                    months = sorted(st.session_state.df["연월"].unique(), reverse=True)
                    st.session_state.selected_month = months[0] if months else None
                    st.session_state.exp_month = months[0] if months else "전체"
                    st.session_state.inc_month = months[0] if months else "전체"
                    st.session_state.exp_cat = ["고정지출", "변동지출", "경조사"]
                    st.success(f"{len(loaded):,}건 불러옴")
                    st.rerun()

    # ── 월 선택 & 로드 현황 ──
    if st.session_state.df is not None:
        st.divider()
        df_all = st.session_state.df
        months = sorted(df_all["연월"].unique(), reverse=True)

        st.subheader("📅 조회 월")
        selected = st.selectbox(
            "월 선택",
            months,
            index=0,
            label_visibility="collapsed",
        )
        st.session_state.selected_month = selected

        st.divider()
        st.subheader("🏦 로드된 통장")
        for acct, cnt in df_all.groupby("_통장").size().items():
            st.caption(f"  **{acct}**: {cnt}건")

        # ── 💰 예산 설정 ──
        st.divider()
        with st.expander("💰 예산 설정 (소분류별 월 목표)", expanded=False):
            # 소분류 옵션: 지출 계열만
            exp_df = df_all[df_all["대분류"].isin(["고정지출", "변동지출", "경조사", "기타"])]
            subcats = sorted(exp_df["소분류"].dropna().unique().tolist())
            if not subcats:
                st.caption("지출 소분류가 없습니다.")
            else:
                with st.form("budgets_form"):
                    new_budgets = {}
                    for sc in subcats:
                        cur = int(st.session_state.budgets.get(sc, 0))
                        val = st.number_input(
                            sc,
                            min_value=0,
                            step=10000,
                            value=cur,
                            key=f"budget_{sc}",
                        )
                        if val and val > 0:
                            new_budgets[sc] = int(val)
                    saved = st.form_submit_button(
                        "💾 예산 저장", width='stretch', type="primary"
                    )
                    if saved:
                        st.session_state.budgets = new_budgets
                        save_budgets(new_budgets)
                        st.success("예산이 저장되었습니다.")
                        st.rerun()


# ── 메인 탭 ───────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 대시보드",
    "💸 지출 내역",
    "💵 수입 내역",
    "🗂️ 카테고리 관리",
    "📈 투자",
    "🏦 연금",
    "💰 저축목표",
])

# ── 데이터 없을 때 공통 안내 ──────────────────────────────────────────
def no_data_notice():
    st.info("👈 사이드바에서 파일을 업로드하고 **데이터 로드** 버튼을 눌러주세요.")


# ════════════════════════════════════════════════════════════════════════
# Tab 1: 대시보드
# ════════════════════════════════════════════════════════════════════════
with tab1:
    if st.session_state.df is None:
        no_data_notice()
    else:
        df = st.session_state.df
        ym = st.session_state.selected_month
        kpi = build_monthly_kpis(df, ym)
        prev = kpi.get("prev", {})

        def fmt(v):
            return f"{v:,.0f}원"

        def delta(key):
            if prev and key in prev and prev[key] != 0:
                return kpi[key] - prev[key]
            return None

        # ── KPI 카드 ──
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("💵 총 수입", fmt(kpi["총수입"]),
                      delta=fmt(delta("총수입")) if delta("총수입") else None)
        with c2:
            st.metric("🔒 고정 지출", fmt(kpi["고정지출"]),
                      delta=fmt(delta("고정지출")) if delta("고정지출") else None,
                      delta_color="inverse")
        with c3:
            st.metric("🛒 변동 지출", fmt(kpi["변동지출"]),
                      delta=fmt(delta("변동지출")) if delta("변동지출") else None,
                      delta_color="inverse")
        with c4:
            net = kpi["순수지"]
            st.metric("📊 순 수지", fmt(net),
                      delta=fmt(delta("순수지")) if delta("순수지") else None,
                      delta_color="normal")

        st.divider()

        # ── 🎯 예산 진행도 ──
        budgets = st.session_state.get("budgets", {})
        if budgets:
            st.subheader(f"🎯 {ym} 예산 현황")
            month_exp = df[
                (df["연월"] == ym)
                & df["대분류"].isin(["고정지출", "변동지출", "경조사", "기타"])
            ]
            spend_by_sub = (
                month_exp.groupby("소분류")["거래금액"].sum().abs().to_dict()
            )

            # 예산 설정된 소분류만, 예산 큰 순
            items = sorted(budgets.items(), key=lambda x: -x[1])
            if items:
                for sub, budget in items:
                    if budget <= 0:
                        continue
                    spent = int(spend_by_sub.get(sub, 0))
                    ratio = spent / budget if budget else 0
                    bar_val = min(max(ratio, 0.0), 1.0)
                    label = f"**{sub}** — {spent:,}원 / {budget:,}원 ({ratio:.0%})"
                    st.progress(bar_val, text=label)
                    if ratio >= 1.0:
                        st.error(f"⚠️ {sub} 예산 초과 ({ratio:.0%})")
                    elif ratio >= 0.8:
                        st.warning(f"🟡 {sub} 예산의 80% 이상 소진 ({ratio:.0%})")
            st.divider()
        else:
            st.caption("💡 사이드바 **예산 설정**에서 소분류별 목표를 입력하면 이 영역에 진행도가 표시됩니다.")
            st.divider()

        # ── 차트 행 ──
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader(f"📎 {ym} 지출 구성")
            month_df = df[(df["연월"] == ym) & df["대분류"].isin(["고정지출", "변동지출", "경조사"])]
            if month_df.empty:
                st.info("해당 월 지출 데이터가 없습니다.")
            else:
                pie_df = month_df.groupby(["대분류", "소분류"])["거래금액"].sum().reset_index()
                pie_df["금액(절대값)"] = pie_df["거래금액"].abs()
                subcats = pie_df["소분류"].unique().tolist()
                color_map = {s: SUBCAT_COLORS[i % len(SUBCAT_COLORS)] for i, s in enumerate(subcats)}
                fig_pie = px.pie(
                    pie_df, values="금액(절대값)", names="소분류",
                    hole=0.55, color="소분류", color_discrete_map=color_map,
                    custom_data=["대분류", "거래금액"],
                )
                fig_pie.update_traces(
                    textposition="inside", textinfo="percent+label",
                    hovertemplate="<b>%{label}</b><br>%{value:,.0f}원 (%{percent})<extra></extra>",
                )
                fig_pie.update_layout(
                    showlegend=True,
                    legend=dict(orientation="v", x=1.02, y=0.5),
                    margin=dict(t=10, b=10, l=0, r=120),
                    height=350,
                )
                st.plotly_chart(fig_pie, width='stretch')

        with col_right:
            st.subheader("📈 최근 6개월 추이")
            all_months = sorted(df["연월"].unique())
            idx = all_months.index(ym) if ym in all_months else len(all_months) - 1
            recent = all_months[max(0, idx - 5): idx + 1]

            m_income, m_fixed, m_var, m_event, m_net = [], [], [], [], []
            for m in recent:
                k = build_monthly_kpis(df, m)
                m_income.append(k["총수입"])
                m_fixed.append(abs(k["고정지출"]))
                m_var.append(abs(k["변동지출"]))
                m_event.append(abs(k["경조사"]))
                m_net.append(k["순수지"])

            fig_bar = go.Figure()
            fig_bar.add_bar(x=recent, y=m_income, name="수입",    marker_color="#A8E6A8")
            fig_bar.add_bar(x=recent, y=[-v for v in m_fixed], name="고정지출", marker_color="#7EB3F5")
            fig_bar.add_bar(x=recent, y=[-v for v in m_var],   name="변동지출", marker_color="#FFD166")
            fig_bar.add_bar(x=recent, y=[-v for v in m_event], name="경조사",   marker_color="#F4B8B8")
            fig_bar.add_scatter(
                x=recent, y=m_net, name="순수지",
                mode="lines+markers",
                line=dict(color="#1A2E4A", width=2, dash="dot"),
                marker=dict(size=7),
            )
            fig_bar.update_layout(
                barmode="relative",
                legend=dict(orientation="h", y=-0.2),
                margin=dict(t=10, b=40, l=0, r=0),
                height=350,
                yaxis_tickformat=",",
            )
            st.plotly_chart(fig_bar, width='stretch')

        st.divider()

        # ── 고정/변동 테이블 ──
        month_df_all = df[df["연월"] == ym]
        col_f, col_v = st.columns(2)

        with col_f:
            st.subheader("🔒 고정 지출 내역")
            fixed_tbl = (
                month_df_all[month_df_all["대분류"] == "고정지출"]
                .groupby("소분류")["거래금액"].sum().reset_index()
                .rename(columns={"거래금액": "금액"}).sort_values("금액")
            )
            fixed_tbl["금액"] = fixed_tbl["금액"].map(lambda x: f"{x:,.0f}원")
            st.dataframe(fixed_tbl, width='stretch', hide_index=True)

        with col_v:
            st.subheader("🛒 변동 지출 내역")
            var_tbl = (
                month_df_all[month_df_all["대분류"] == "변동지출"]
                .groupby("소분류")["거래금액"].sum().reset_index()
                .rename(columns={"거래금액": "금액"}).sort_values("금액")
            )
            var_tbl["금액"] = var_tbl["금액"].map(lambda x: f"{x:,.0f}원")
            st.dataframe(var_tbl, width='stretch', hide_index=True)


# ════════════════════════════════════════════════════════════════════════
# Tab 2: 지출 내역
# ════════════════════════════════════════════════════════════════════════
with tab2:
    if st.session_state.df is None:
        no_data_notice()
    else:
        df = st.session_state.df

        # 필터
        fc1, fc2, fc3, fc4 = st.columns(4)
        all_months_opt = ["전체"] + sorted(df["연월"].unique(), reverse=True)
        대분류_opts = ["고정지출", "변동지출", "경조사", "기타", "미분류"]
        소분류_opts = sorted(df["소분류"].unique().tolist())
        acct_opts   = sorted(df["_통장"].unique().tolist())

        with fc1:
            f_month = st.selectbox("월", all_months_opt, key="exp_month")
        with fc2:
            f_cat = st.multiselect("대분류", 대분류_opts, key="exp_cat")
        with fc3:
            f_subcat = st.multiselect("소분류", 소분류_opts, key="exp_subcat")
        with fc4:
            f_acct = st.multiselect("통장", acct_opts, key="exp_acct")

        filtered = df.copy()
        if f_month != "전체":
            filtered = filtered[filtered["연월"] == f_month]
        if f_cat:
            filtered = filtered[filtered["대분류"].isin(f_cat)]
        if f_subcat:
            filtered = filtered[filtered["소분류"].isin(f_subcat)]
        if f_acct:
            filtered = filtered[filtered["_통장"].isin(f_acct)]

        # 소계
        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("합계 금액", f"{filtered['거래금액'].sum():,.0f}원")
        with s2:
            st.metric("건 수", f"{len(filtered):,}건")
        with s3:
            avg = filtered["거래금액"].mean()
            st.metric("평균 단가", f"{avg:,.0f}원" if not pd.isna(avg) else "—")

        # 테이블
        show_cols = ["날짜", "적요", "거래 유형", "_통장", "대분류", "소분류", "IsFixed", "거래금액", "메모"]
        display = filtered[show_cols].copy()
        display.columns = ["날짜", "적요", "거래유형", "통장", "대분류", "소분류", "고정여부", "거래금액", "메모"]
        display["고정여부"] = display["고정여부"].map(lambda x: "✔" if x else "")

        st.dataframe(
            display,
            width='stretch',
            hide_index=True,
            height=420,
            column_config={
                "날짜": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
                "거래금액": st.column_config.NumberColumn("거래금액", format="%d원"),
            },
        )

        csv = display.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 CSV 다운로드", csv, "지출내역.csv", "text/csv")


# ════════════════════════════════════════════════════════════════════════
# Tab 3: 수입 내역
# ════════════════════════════════════════════════════════════════════════
with tab3:
    if st.session_state.df is None:
        no_data_notice()
    else:
        df = st.session_state.df
        all_months_opt = ["전체"] + sorted(df["연월"].unique(), reverse=True)

        i_month = st.selectbox("월 선택", all_months_opt, key="inc_month")

        income_df = df[df["대분류"] == "수입"]
        if i_month != "전체":
            income_df = income_df[income_df["연월"] == i_month]

        ic1, ic2, ic3 = st.columns(3)
        with ic1:
            st.metric("💵 총 수입", f"{income_df['거래금액'].sum():,.0f}원")
        with ic2:
            st.metric("건 수", f"{len(income_df)}건")
        with ic3:
            # 소분류별 분포
            main_source = income_df.groupby("소분류")["거래금액"].sum().idxmax() \
                if not income_df.empty else "—"
            st.metric("주 수입원", main_source)

        show_cols = ["날짜", "적요", "거래 유형", "_통장", "소분류", "거래금액", "메모"]
        disp = income_df[show_cols].copy()
        disp.columns = ["날짜", "적요", "거래유형", "통장", "소분류", "거래금액", "메모"]

        st.dataframe(
            disp,
            width='stretch',
            hide_index=True,
            height=400,
            column_config={
                "날짜": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
                "거래금액": st.column_config.NumberColumn("거래금액", format="%d원"),
            },
        )

        # 소분류별 수입 바차트
        if not income_df.empty:
            src_df = income_df.groupby("소분류")["거래금액"].sum().reset_index()
            fig_inc = px.bar(
                src_df, x="소분류", y="거래금액",
                title="소분류별 수입 합계",
                color_discrete_sequence=["#A8E6A8"],
            )
            fig_inc.update_layout(height=280, margin=dict(t=40, b=10))
            st.plotly_chart(fig_inc, width='stretch')


# ════════════════════════════════════════════════════════════════════════
# Tab 4: 카테고리 관리
# ════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("🗂️ 카테고리 관리")

    # ── A: 현재 분류 규칙 ──
    with st.expander("현재 분류 규칙 보기", expanded=False):
        rules_df = pd.DataFrame([
            {"대분류": r[0], "소분류": r[1], "IsFixed": "✔" if r[2] else ""}
            for r in rules
        ])
        st.dataframe(rules_df, width='stretch', hide_index=True, height=320)

    st.divider()

    # ── B: 적요 단위 재지정 ──
    st.subheader("적요 단위 카테고리 재지정")

    대분류_list = ["수입", "고정지출", "변동지출", "경조사", "내부이체", "기타"]

    if st.session_state.df is not None:
        all_적요 = sorted(st.session_state.df["적요"].dropna().unique().tolist())
    else:
        all_적요 = []

    with st.form("override_form", clear_on_submit=True):
        ov1, ov2, ov3, ov4 = st.columns(4)
        with ov1:
            target = st.selectbox("적요 선택", [""] + all_적요, key="ov_target")
        with ov2:
            new_대분류 = st.selectbox("대분류", 대분류_list, key="ov_main")
        with ov3:
            new_소분류 = st.text_input("소분류", placeholder="예) 식비", key="ov_sub")
        with ov4:
            new_fixed = st.checkbox("IsFixed (고정 지출)", key="ov_fixed")
            st.write("")  # 높이 맞춤
            submitted = st.form_submit_button("💾 저장", width='stretch')

        if submitted and target:
            st.session_state.overrides[target] = {
                "대분류": new_대분류,
                "소분류": new_소분류 or new_대분류,
                "IsFixed": new_fixed,
            }
            save_overrides(st.session_state.overrides)
            if st.session_state.raw_df is not None:
                st.session_state.df = apply_categorization(
                    st.session_state.raw_df, st.session_state.overrides
                )
            st.success(f"'{target}' → {new_대분류} / {new_소분류 or new_대분류} 저장 완료!")
            st.rerun()

    st.divider()

    # ── C: 현재 재지정 목록 ──
    st.subheader("현재 재지정 목록")
    overrides = st.session_state.overrides

    if overrides:
        ov_df = pd.DataFrame([
            {"적요": k, "대분류": v["대분류"], "소분류": v["소분류"],
             "IsFixed": bool(v.get("IsFixed", False))}
            for k, v in overrides.items()
        ])

        edited = st.data_editor(
            ov_df,
            width='stretch',
            num_rows="dynamic",
            key="overrides_editor",
            column_config={
                "IsFixed": st.column_config.CheckboxColumn("IsFixed"),
            },
        )

        if st.button("변경 사항 적용", type="secondary"):
            new_ov = {}
            for _, row in edited.iterrows():
                if pd.notna(row.get("적요")) and str(row["적요"]).strip():
                    new_ov[str(row["적요"])] = {
                        "대분류": row["대분류"],
                        "소분류": row["소분류"],
                        "IsFixed": bool(row["IsFixed"]),
                    }
            st.session_state.overrides = new_ov
            save_overrides(new_ov)
            if st.session_state.raw_df is not None:
                st.session_state.df = apply_categorization(
                    st.session_state.raw_df, new_ov
                )
            st.success("변경 사항이 적용되었습니다.")
            st.rerun()
    else:
        st.info("아직 재지정된 항목이 없습니다.")

    st.divider()

    # ── D: 고정비 자동 탐지 ──
    st.subheader("💡 고정비 자동 탐지 제안")
    st.caption("3개월 이상 연속으로 유사 금액(±10%)이 출금된 적요를 IsFixed 후보로 제안합니다.")

    if st.session_state.df is not None:
        fx_df = detect_fixed_candidates(
            st.session_state.df, window_months=3, amount_tol=0.10
        )
        if fx_df.empty:
            st.info("현재 후보가 없습니다. (이미 IsFixed로 지정되었거나 조건 미충족)")
        else:
            disp_fx = fx_df.copy()
            disp_fx.insert(0, "선택", False)
            disp_fx["평균금액"] = disp_fx["평균금액"].map(lambda x: f"{x:,.0f}원")
            edited_fx = st.data_editor(
                disp_fx,
                width='stretch',
                hide_index=True,
                disabled=["적요", "평균금액", "발생월수", "현재IsFixed"],
                column_config={
                    "선택": st.column_config.CheckboxColumn("선택"),
                },
                key="fixed_candidates_editor",
            )

            col_fa, col_fb = st.columns([1, 1])
            with col_fa:
                apply_selected = st.button(
                    "📌 선택 항목 IsFixed 지정",
                    width='stretch',
                    key="apply_selected_fixed",
                )
            with col_fb:
                apply_all = st.button(
                    "📌 모두 IsFixed 지정",
                    width='stretch',
                    key="apply_all_fixed",
                )

            targets = []
            if apply_all:
                targets = fx_df["적요"].tolist()
            elif apply_selected:
                sel = edited_fx[edited_fx["선택"] == True]["적요"].tolist()
                targets = sel

            if targets:
                # 현재 분류 결과에서 각 적요의 (대분류, 소분류)를 가져와 IsFixed=True로 세팅
                cur_df = st.session_state.df
                for jeok in targets:
                    sub_rows = cur_df[cur_df["적요"] == jeok]
                    if sub_rows.empty:
                        continue
                    대 = sub_rows["대분류"].mode().iat[0] if not sub_rows["대분류"].mode().empty else "고정지출"
                    소 = sub_rows["소분류"].mode().iat[0] if not sub_rows["소분류"].mode().empty else 대
                    # 변동지출/기타에서 올라온 경우 대분류도 고정지출로 격상
                    if 대 in ("변동지출", "기타"):
                        대 = "고정지출"
                    st.session_state.overrides[jeok] = {
                        "대분류": 대,
                        "소분류": 소,
                        "IsFixed": True,
                    }
                save_overrides(st.session_state.overrides)
                if st.session_state.raw_df is not None:
                    st.session_state.df = apply_categorization(
                        st.session_state.raw_df, st.session_state.overrides
                    )
                st.success(f"{len(targets)}건을 IsFixed로 지정했습니다.")
                st.rerun()
    else:
        st.info("데이터를 먼저 로드해주세요.")

    st.divider()

    # ── E: 미분류 항목 ──
    st.subheader("⚠️ 미분류 항목")
    if st.session_state.df is not None:
        uncat = (
            st.session_state.df[st.session_state.df["대분류"] == "미분류"]
            [["적요", "거래 유형", "_통장", "거래금액"]]
            .drop_duplicates("적요")
            .sort_values("거래금액")
        )
        if uncat.empty:
            st.success("미분류 항목이 없습니다! ✅")
        else:
            st.warning(f"{len(uncat)}개의 미분류 항목이 있습니다.")
            st.dataframe(uncat, width='stretch', hide_index=True)
    else:
        st.info("데이터를 먼저 로드해주세요.")


# ════════════════════════════════════════════════════════════════════════
# Tab 5: 투자
# ════════════════════════════════════════════════════════════════════════
with tab5:
    render_investment_tab()


# ════════════════════════════════════════════════════════════════════════
# Tab 6: 연금
# ════════════════════════════════════════════════════════════════════════
with tab6:
    render_pension_tab()


# ════════════════════════════════════════════════════════════════════════
# Tab 7: 저축목표
# ════════════════════════════════════════════════════════════════════════
with tab7:
    render_savings_tab(st.session_state.df)
