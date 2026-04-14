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

from utils import (
    CAT_COLOR_PLOTLY, SUBCAT_COLORS,
    apply_categorization, build_monthly_kpis,
    detect_account_name, load_excel, load_overrides,
    rules, save_overrides,
)

BASE_DIR = Path(__file__).parent

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

# ── Session State 초기화 ──────────────────────────────────────────────
if "overrides" not in st.session_state:
    st.session_state.overrides = load_overrides()
if "df" not in st.session_state:
    st.session_state.df = None
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "selected_month" not in st.session_state:
    st.session_state.selected_month = None


# ── 사이드바 ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💰 가계부")
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

    load_btn = st.button("🔄 데이터 로드", type="primary", use_container_width=True)

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
        else:
            with st.spinner("데이터 로딩 중..."):
                dfs = []
                errors = []
                for src, name in sources:
                    try:
                        dfs.append(load_excel(src, name))
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
                    st.success(f"{len(st.session_state.df):,}건 로드 완료")
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


# ── 메인 탭 ───────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 대시보드",
    "💸 지출 내역",
    "💵 수입 내역",
    "🗂️ 카테고리 관리",
    "📈 수익률",
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
                st.plotly_chart(fig_pie, use_container_width=True)

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
            st.plotly_chart(fig_bar, use_container_width=True)

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
            st.dataframe(fixed_tbl, use_container_width=True, hide_index=True)

        with col_v:
            st.subheader("🛒 변동 지출 내역")
            var_tbl = (
                month_df_all[month_df_all["대분류"] == "변동지출"]
                .groupby("소분류")["거래금액"].sum().reset_index()
                .rename(columns={"거래금액": "금액"}).sort_values("금액")
            )
            var_tbl["금액"] = var_tbl["금액"].map(lambda x: f"{x:,.0f}원")
            st.dataframe(var_tbl, use_container_width=True, hide_index=True)


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
            f_month = st.selectbox("월", all_months_opt,
                                   index=all_months_opt.index(
                                       st.session_state.selected_month or "전체"
                                   ) if st.session_state.selected_month in all_months_opt else 0,
                                   key="exp_month")
        with fc2:
            f_cat = st.multiselect("대분류", 대분류_opts,
                                    default=["고정지출", "변동지출", "경조사"],
                                    key="exp_cat")
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
            use_container_width=True,
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

        i_month = st.selectbox("월 선택", all_months_opt,
                                index=all_months_opt.index(
                                    st.session_state.selected_month or "전체"
                                ) if st.session_state.selected_month in all_months_opt else 0,
                                key="inc_month")

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
            use_container_width=True,
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
            st.plotly_chart(fig_inc, use_container_width=True)


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
        st.dataframe(rules_df, use_container_width=True, hide_index=True, height=320)

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
            submitted = st.form_submit_button("💾 저장", use_container_width=True)

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
            use_container_width=True,
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

    # ── D: 미분류 항목 ──
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
            st.dataframe(uncat, use_container_width=True, hide_index=True)
    else:
        st.info("데이터를 먼저 로드해주세요.")


# ════════════════════════════════════════════════════════════════════════
# Tab 5: 수익률 (준비중)
# ════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("📈 수익률 분석")
    st.info(
        "이 페이지는 추후 **주식/연금 수익률 추적** 기능이 추가될 예정입니다.\n\n"
        "계획 중인 기능:\n"
        "- 포트폴리오 자산 현황 입력\n"
        "- 월별 투자 수익률 트래킹\n"
        "- 연금 예상 수령액 시뮬레이션\n"
        "- 목표 대비 저축률 진행도"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("주식 수익률", "—", help="준비 중")
    with col2:
        st.metric("연금 예상 수령액", "—", help="준비 중")
    with col3:
        # 현재 저축 현황은 계산 가능
        if st.session_state.df is not None:
            df = st.session_state.df
            ym = st.session_state.selected_month
            if ym:
                savings = df[
                    (df["연월"] == ym) & (df["소분류"] == "적금/저축")
                ]["거래금액"].sum()
                st.metric("이번 달 적금/저축", f"{abs(savings):,.0f}원")
        else:
            st.metric("이번 달 적금/저축", "—")
