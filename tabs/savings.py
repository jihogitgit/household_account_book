"""
저축률 목표 탭
"""
import plotly.graph_objects as go
import streamlit as st

from database import get_db


def render_savings_tab(df) -> None:
    db = get_db()

    # ── 섹션 1: 현재 저축 현황 ─────────────────────────────────────────
    if df is not None and not df.empty:
        st.subheader("💵 현재 저축 현황")

        savings_df = df[
            (df["대분류"] == "고정지출") & (df["소분류"] == "적금/저축")
        ].copy()
        income_df = df[df["대분류"] == "수입"].copy()

        all_months    = sorted(df["연월"].unique(), reverse=True)
        recent_months = all_months[:6][::-1]

        m_save, m_income, m_rate = [], [], []
        for m in recent_months:
            save = abs(savings_df[savings_df["연월"] == m]["거래금액"].sum())
            inc  = income_df[income_df["연월"] == m]["거래금액"].sum()
            m_save.append(save)
            m_income.append(inc)
            m_rate.append(save / inc * 100 if inc > 0 else 0)

        if recent_months:
            c1, c2, c3 = st.columns(3)
            c1.metric("이번 달 저축액",        f"{m_save[-1]:,.0f}원")
            c2.metric("이번 달 저축률",         f"{m_rate[-1]:.1f}%")
            avg_rate = sum(m_rate) / len(m_rate) if m_rate else 0
            c3.metric("최근 6개월 평균 저축률", f"{avg_rate:.1f}%")

        col_l, col_r = st.columns(2)
        with col_l:
            fig1 = go.Figure(go.Bar(
                x=recent_months, y=m_save, marker_color="#4F8EF7", name="저축액"
            ))
            fig1.update_layout(
                title="월별 저축액", height=260,
                margin=dict(t=40, b=20), yaxis_tickformat=","
            )
            st.plotly_chart(fig1, use_container_width=True)
        with col_r:
            fig2 = go.Figure(go.Bar(
                x=recent_months, y=m_rate, marker_color="#10B981", name="저축률(%)"
            ))
            fig2.add_hline(y=20, line_dash="dot", line_color="#F59E0B",
                           annotation_text="권장 20%")
            fig2.update_layout(
                title="월별 저축률 (%)", height=260,
                margin=dict(t=40, b=20), yaxis_ticksuffix="%"
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

    # ── 섹션 2: 목표 설정 ─────────────────────────────────────────────
    st.subheader("🎯 저축 목표 설정")
    goals = db.get_savings_goals()

    with st.form("goal_form", clear_on_submit=True):
        gc1, gc2 = st.columns([2, 1])
        with gc1:
            goal_name = st.text_input("목표명", placeholder="예) 비상금 1천만원, 여행비")
        with gc2:
            goal_amount = st.number_input("월 목표 저축액 (원)", min_value=0, step=50000)
        if st.form_submit_button("➕ 목표 추가", type="primary", use_container_width=True):
            if goal_name:
                db.upsert_savings_goal({"목표명": goal_name, "월목표금액": goal_amount})
                st.success(f"'{goal_name}' 목표 추가!")
                st.rerun()

    if goals.empty:
        st.info("아직 설정된 저축 목표가 없습니다.")
        return

    st.caption(f"**총 월 목표 저축액: {goals['월목표금액'].sum():,.0f}원**")
    for _, row in goals.iterrows():
        col_n, col_a, col_d = st.columns([3, 2, 1])
        col_n.write(f"**{row['목표명']}**")
        col_a.write(f"{row['월목표금액']:,.0f}원/월")
        if col_d.button("🗑️", key=f"del_goal_{row['id']}"):
            db.delete_savings_goal(int(row["id"]))
            st.rerun()

    # ── 섹션 3: 진행도 ────────────────────────────────────────────────
    if df is None or df.empty:
        st.info("거래내역을 로드하면 목표 달성 진행도가 표시됩니다.")
        return

    st.divider()
    st.subheader("📊 목표 달성 진행도")

    latest_month  = sorted(df["연월"].unique())[-1]
    actual_saving = abs(
        df[
            (df["연월"] == latest_month) &
            (df["대분류"] == "고정지출") &
            (df["소분류"] == "적금/저축")
        ]["거래금액"].sum()
    )
    total_goal = float(goals["월목표금액"].sum())

    for _, row in goals.iterrows():
        goal_amt = float(row["월목표금액"])
        ratio    = actual_saving / goal_amt if goal_amt > 0 else 0
        st.progress(
            min(ratio, 1.0),
            text=f"**{row['목표명']}** — {actual_saving:,.0f}원 / {goal_amt:,.0f}원 ({ratio:.0%})",
        )

    st.divider()
    gap = actual_saving - total_goal
    if gap >= 0:
        st.success(f"✅ {latest_month} 전체 저축 목표 달성! (+{gap:,.0f}원)")
    else:
        st.info(f"{latest_month} 목표까지 **{abs(gap):,.0f}원** 남았습니다.")

    yearly_actual = actual_saving * 12
    yearly_goal   = total_goal * 12
    st.metric(
        "연간 저축 예상 (현재 페이스)",
        f"{yearly_actual:,.0f}원",
        delta=f"{yearly_actual - yearly_goal:+,.0f}원 vs 연간 목표",
    )
