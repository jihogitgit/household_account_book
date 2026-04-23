"""
포트폴리오 · 수익률 · 세액공제 · 리밸런싱 탭
"""
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database import get_db

ASSET_TYPES = ["국내주식", "해외주식", "국내ETF", "해외ETF", "연금", "예금·적금", "부동산", "기타"]
TYPE_COLORS = {
    "국내주식":  "#4F8EF7",
    "해외주식":  "#7C3AED",
    "국내ETF":   "#10B981",
    "해외ETF":   "#F59E0B",
    "연금":      "#EF4444",
    "예금·적금": "#6B7280",
    "부동산":    "#D97706",
    "기타":      "#9CA3AF",
}


def render_investment_tab() -> None:
    st.markdown("""
    <style>
    .profit-pos { color: #10B981; font-weight: 700; }
    .profit-neg { color: #EF4444; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

    sub1, sub2, sub3, sub4 = st.tabs([
        "💼 포트폴리오 현황", "📅 월별 수익률", "💰 세액공제 트래커", "⚖️ 리밸런싱",
    ])
    with sub1:
        _render_portfolio()
    with sub2:
        _render_returns()
    with sub3:
        _render_tax()
    with sub4:
        _render_rebalancing()


# ════════════════════════════════════════════════════════════════════════
# 포트폴리오 현황
# ════════════════════════════════════════════════════════════════════════
def _render_portfolio() -> None:
    db = get_db()
    assets = db.get_assets()

    with st.expander("➕ 자산 추가 / 수정", expanded=assets.empty):
        with st.form("asset_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name   = st.text_input("자산명", placeholder="예) 삼성전자, S&P500 ETF")
                atype  = st.selectbox("유형", ASSET_TYPES)
                qty    = st.number_input("수량", min_value=0.0, value=1.0, step=0.01)
            with c2:
                cost   = st.number_input("매입가 (원, 주당/좌당)", min_value=0, step=1000)
                price  = st.number_input("현재가 (원, 주당/좌당)", min_value=0, step=1000)
                weight = st.number_input("목표비중 (%)", min_value=0.0, max_value=100.0, step=0.5)
            if st.form_submit_button("💾 저장", type="primary", use_container_width=True) and name:
                db.upsert_asset({"자산명": name, "유형": atype, "매입가": cost,
                                  "수량": qty, "현재가": price, "목표비중": weight})
                st.success(f"'{name}' 저장 완료!")
                st.rerun()

    if assets.empty:
        st.info("위 폼에서 자산을 추가하면 포트폴리오 현황이 표시됩니다.")
        return

    assets = assets.copy()
    assets["평가금액"] = assets["현재가"] * assets["수량"]
    assets["매입금액"] = assets["매입가"] * assets["수량"]
    assets["손익"]    = assets["평가금액"] - assets["매입금액"]
    with pd.option_context("mode.use_inf_as_na", True):
        assets["수익률(%)"] = (
            assets["손익"] / assets["매입금액"].replace(0, float("nan")) * 100
        ).round(2)

    total_eval   = assets["평가금액"].sum()
    total_cost   = assets["매입금액"].sum()
    total_profit = assets["손익"].sum()
    total_return = (total_profit / total_cost * 100) if total_cost else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("총 평가금액",   f"{total_eval:,.0f}원")
    c2.metric("총 손익",       f"{total_profit:+,.0f}원")
    c3.metric("전체 수익률",   f"{total_return:+.2f}%")

    st.divider()

    col_tbl, col_chart = st.columns([1.4, 1])
    with col_tbl:
        disp = assets[["자산명","유형","매입가","수량","현재가","평가금액","손익","수익률(%)"]].copy()
        disp["매입가"]   = disp["매입가"].map(lambda x: f"{x:,.0f}")
        disp["현재가"]   = disp["현재가"].map(lambda x: f"{x:,.0f}")
        disp["평가금액"] = disp["평가금액"].map(lambda x: f"{x:,.0f}원")
        disp["손익"]     = disp["손익"].map(lambda x: f"{x:+,.0f}원")
        disp["수익률(%)"] = disp["수익률(%)"].map(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
        )
        st.dataframe(disp, use_container_width=True, hide_index=True)

        del_name = st.selectbox("삭제할 자산", [""] + assets["자산명"].tolist(), key="del_asset")
        if del_name and st.button("🗑️ 삭제", key="del_asset_btn"):
            row = assets[assets["자산명"] == del_name].iloc[0]
            db.delete_asset(int(row["id"]))
            st.success(f"'{del_name}' 삭제 완료")
            st.rerun()

    with col_chart:
        type_eval = assets.groupby("유형")["평가금액"].sum().reset_index()
        colors = [TYPE_COLORS.get(t, "#9CA3AF") for t in type_eval["유형"]]
        fig = px.pie(
            type_eval, values="평가금액", names="유형",
            hole=0.55, color_discrete_sequence=colors, title="유형별 자산배분",
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0), height=320)
        st.plotly_chart(fig, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════
# 월별 수익률
# ════════════════════════════════════════════════════════════════════════
def _render_returns() -> None:
    db = get_db()
    ret_df = db.get_monthly_returns()

    with st.expander("➕ 월별 평가금액 입력", expanded=ret_df.empty):
        with st.form("return_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                ym     = st.text_input("연월 (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
            with c2:
                total  = st.number_input("총 평가금액 (원)", min_value=0, step=100000)
            with c3:
                contrib = st.number_input(
                    "순기여금 (원)", step=100000,
                    help="해당 월 추가납입 - 인출액. 수익률 왜곡 보정용"
                )
            memo = st.text_input("메모", placeholder="선택사항")
            if st.form_submit_button("💾 저장", type="primary", use_container_width=True):
                db.upsert_monthly_return(ym, total, contrib, memo)
                st.success(f"{ym} 저장 완료!")
                st.rerun()

    if ret_df.empty:
        st.info("월별 평가금액을 입력하면 수익률 분석이 표시됩니다.")
        return

    ret_df = ret_df.copy().reset_index(drop=True)
    rates, cum_rates, cum = [], [], 1.0
    for i, row in ret_df.iterrows():
        if i == 0:
            r = 0.0
        else:
            prev = ret_df.iloc[i - 1]["총평가금액"]
            base = prev + row["순기여금"]
            r = (row["총평가금액"] - base) / base * 100 if base else 0
        rates.append(round(r, 2))
        cum *= (1 + r / 100)
        cum_rates.append(round((cum - 1) * 100, 2))
    ret_df["월수익률(%)"]  = rates
    ret_df["누적수익률(%)"] = cum_rates

    last = ret_df.iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("최근 평가금액",   f"{last['총평가금액']:,.0f}원")
    c2.metric("최근 월 수익률",  f"{last['월수익률(%)']:+.2f}%")
    c3.metric("누적 수익률",     f"{last['누적수익률(%)']:+.2f}%")

    st.divider()
    col_l, col_r = st.columns(2)
    with col_l:
        fig1 = px.area(ret_df, x="연월", y="총평가금액", title="총 평가금액 추이",
                       color_discrete_sequence=["#4F8EF7"])
        fig1.update_layout(height=280, margin=dict(t=40, b=20), yaxis_tickformat=",")
        st.plotly_chart(fig1, use_container_width=True)
    with col_r:
        bar_colors = ["#EF4444" if r < 0 else "#4F8EF7" for r in ret_df["월수익률(%)"]]
        fig2 = go.Figure(go.Bar(x=ret_df["연월"], y=ret_df["월수익률(%)"],
                                 marker_color=bar_colors, name="월 수익률"))
        fig2.update_layout(title="월별 수익률", height=280,
                           margin=dict(t=40, b=20), yaxis_ticksuffix="%")
        st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(
        ret_df[["연월", "총평가금액", "순기여금", "월수익률(%)", "누적수익률(%)"]],
        use_container_width=True, hide_index=True,
        column_config={
            "총평가금액": st.column_config.NumberColumn("총평가금액", format="%d원"),
            "순기여금":   st.column_config.NumberColumn("순기여금",   format="%d원"),
        },
    )

    del_ym = st.selectbox("삭제할 연월", [""] + ret_df["연월"].tolist()[::-1], key="del_ret_ym")
    if del_ym and st.button("🗑️ 삭제", key="del_ret_btn"):
        db.delete_monthly_return(del_ym)
        st.rerun()


# ════════════════════════════════════════════════════════════════════════
# 세액공제 트래커
# ════════════════════════════════════════════════════════════════════════
def _render_tax() -> None:
    db = get_db()
    cur_year = datetime.now().year
    year = st.selectbox("조회 연도", [cur_year, cur_year - 1, cur_year - 2], key="tax_year")

    st.info(
        "**세액공제 한도 안내**  \n"
        "- 연금저축 단독 한도: 연 **600만원**  \n"
        "- 연금저축 + IRP 합산 한도: 연 **900만원**  \n"
        "- 세액공제율: 소득 5,500만원 이하 **16.5%** / 초과 **13.2%**"
    )

    ITEMS = ["연금저축펀드", "IRP", "퇴직연금(DC형)"]
    tax_df = db.get_tax_deductions(year)
    amounts = {row["항목"]: float(row["납입금액"]) for _, row in tax_df.iterrows()}

    with st.form("tax_form"):
        st.subheader(f"{year}년 납입금액 입력")
        c1, c2, c3 = st.columns(3)
        new_amounts: dict = {}
        for col, item in zip([c1, c2, c3], ITEMS):
            val = col.number_input(
                item, min_value=0, step=100000,
                value=int(amounts.get(item, 0)), key=f"tax_{item}"
            )
            new_amounts[item] = val
        if st.form_submit_button("💾 저장", type="primary", use_container_width=True):
            for item, amt in new_amounts.items():
                db.upsert_tax_deduction(year, item, amt)
            st.success("저장 완료!")
            st.rerun()

    st.divider()
    pension_amt = amounts.get("연금저축펀드", 0)
    irp_amt     = amounts.get("IRP", 0)
    dc_amt      = amounts.get("퇴직연금(DC형)", 0)
    pension_tot = pension_amt + dc_amt
    all_tot     = pension_amt + irp_amt + dc_amt

    PENSION_LIMIT, ALL_LIMIT = 6_000_000, 9_000_000
    eligible = min(all_tot, ALL_LIMIT)
    tax_low  = eligible * 0.165
    tax_high = eligible * 0.132

    c1, c2, c3 = st.columns(3)
    c1.metric("총 납입금액",        f"{all_tot:,.0f}원")
    c2.metric("공제 대상 금액",     f"{eligible:,.0f}원")
    c3.metric("예상 세액공제(13.2%)", f"{tax_high:,.0f}원",
              help=f"16.5% 기준: {tax_low:,.0f}원")

    st.divider()
    st.progress(
        min(pension_tot / PENSION_LIMIT, 1.0),
        text=f"연금저축 한도: {pension_tot:,.0f} / {PENSION_LIMIT:,.0f}원 ({pension_tot/PENSION_LIMIT*100:.0f}%)"
    )
    st.progress(
        min(all_tot / ALL_LIMIT, 1.0),
        text=f"연금저축+IRP 합산: {all_tot:,.0f} / {ALL_LIMIT:,.0f}원 ({all_tot/ALL_LIMIT*100:.0f}%)"
    )

    remaining = ALL_LIMIT - all_tot
    if remaining > 0:
        st.info(f"💡 {year}년 세액공제 한도 잔여: **{remaining:,.0f}원** 추가 납입 가능")
    else:
        st.success("✅ 세액공제 한도를 모두 채웠습니다!")


# ════════════════════════════════════════════════════════════════════════
# 리밸런싱
# ════════════════════════════════════════════════════════════════════════
def _render_rebalancing() -> None:
    db = get_db()
    assets = db.get_assets()

    if assets.empty:
        st.info("포트폴리오 현황 탭에서 자산과 목표비중을 먼저 입력해주세요.")
        return

    assets = assets.copy()
    assets["평가금액"] = assets["현재가"] * assets["수량"]
    total_eval = assets["평가금액"].sum()

    if total_eval == 0:
        st.warning("현재가 또는 수량이 0인 자산이 있습니다. 확인해주세요.")
        return

    type_df = assets.groupby("유형").agg(
        현재금액=("평가금액", "sum"),
        목표비중=("목표비중", "sum"),
    ).reset_index()
    type_df["현재비중(%)"] = (type_df["현재금액"] / total_eval * 100).round(2)
    type_df["편차(%)"]     = (type_df["현재비중(%)"] - type_df["목표비중"]).round(2)
    type_df["조정금액"]    = (
        (type_df["목표비중"] - type_df["현재비중(%)"]) / 100 * total_eval
    ).round(0)

    st.subheader("리밸런싱 현황")
    alert = False
    for _, row in type_df.iterrows():
        dev = abs(row["편차(%)"])
        msg = (
            f"**{row['유형']}**: 현재 {row['현재비중(%)']:.1f}% "
            f"vs 목표 {row['목표비중']:.1f}% (편차 {row['편차(%)']:+.1f}%)"
        )
        if dev > 5:
            st.error(f"🔴 {msg} — 즉시 리밸런싱 권장")
            alert = True
        elif dev > 3:
            st.warning(f"🟡 {msg} — 리밸런싱 고려")
            alert = True
        else:
            st.success(f"🟢 {msg}")

    st.divider()

    disp = type_df[["유형", "현재금액", "현재비중(%)", "목표비중", "편차(%)", "조정금액"]].copy()
    disp["현재금액"] = disp["현재금액"].map(lambda x: f"{x:,.0f}원")
    disp["조정금액"] = disp["조정금액"].map(lambda x: f"{x:+,.0f}원")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    fig = go.Figure()
    fig.add_bar(x=type_df["유형"], y=type_df["현재비중(%)"], name="현재비중",
                marker_color="#4F8EF7")
    fig.add_bar(x=type_df["유형"], y=type_df["목표비중"],    name="목표비중",
                marker_color="#10B981", opacity=0.7)
    fig.update_layout(
        barmode="group", title="현재비중 vs 목표비중", yaxis_ticksuffix="%",
        height=320, margin=dict(t=40, b=20),
        legend=dict(orientation="h", y=-0.25),
    )
    st.plotly_chart(fig, use_container_width=True)
