"""
저축률 목표 탭
"""
import math
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from database import get_db


def render_savings_tab(df) -> None:
    db = get_db()

    # ── 섹션 1: 현재 저축 현황 ─────────────────────────────────────────
    if df is not None and not df.empty:
        st.subheader("💵 현재 저축 현황")

        savings_df = df[
            (df["대분류"] == "고정지출") & df["소분류"].isin(["적금/저축", "청약", "연금"])
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
        gc3, gc4 = st.columns(2)
        with gc3:
            goal_total = st.number_input("목표 총액 (원, 선택)", min_value=0, step=100000)
        with gc4:
            goal_deadline = st.date_input("목표 기한 (선택)", value=None)
        if st.form_submit_button("➕ 목표 추가", type="primary", use_container_width=True):
            if goal_name:
                db.upsert_savings_goal({
                    "목표명": goal_name,
                    "월목표금액": goal_amount,
                    "목표총액": goal_total,
                    "기한": goal_deadline.isoformat() if goal_deadline else "",
                })
                st.success(f"'{goal_name}' 목표 추가!")
                st.rerun()

    if goals.empty:
        st.info("아직 설정된 저축 목표가 없습니다.")
        return

    st.caption(f"**총 월 목표 저축액: {goals['월목표금액'].sum():,.0f}원**")
    for _, row in goals.iterrows():
        col_n, col_a, col_d = st.columns([3, 2, 1])
        goal_total_val = float(row.get("목표총액", 0) or 0)
        goal_deadline = str(row.get("기한", "") or "")
        line = f"**{row['목표명']}** — {row['월목표금액']:,.0f}원/월"
        if goal_total_val > 0:
            line += f" (목표총액 {goal_total_val:,.0f}원)"
        if goal_deadline:
            line += f" ⏳ {goal_deadline}까지"
        col_n.write(line)
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
            df["소분류"].isin(["적금/저축", "청약", "연금"])
        ]["거래금액"].sum()
    )
    total_goal = float(goals["월목표금액"].sum())

    overall_ratio = actual_saving / total_goal if total_goal > 0 else 0
    st.progress(
        min(overall_ratio, 1.0),
        text=f"**전체** — {actual_saving:,.0f}원 / {total_goal:,.0f}원 ({overall_ratio:.0%})",
    )
    for _, row in goals.iterrows():
        goal_amt = float(row["월목표금액"])
        alloc = actual_saving * (goal_amt / total_goal) if total_goal > 0 else 0
        ratio = alloc / goal_amt if goal_amt > 0 else 0
        st.caption(f"  · **{row['목표명']}** 목표 {goal_amt:,.0f}원 → 배분 {alloc:,.0f}원 ({ratio:.0%})")

    # 목표총액 기반 예상 달성 시점
    total_goal_amount = sum(float(r.get("목표총액", 0) or 0) for _, r in goals.iterrows())
    if total_goal_amount > 0 and actual_saving > 0:
        months_needed = math.ceil(total_goal_amount / actual_saving)
        today = date.today()
        reach_month = today.month + months_needed
        reach_year = today.year + (reach_month - 1) // 12
        reach_month = (reach_month - 1) % 12 + 1
        reach_day = min(today.day, 28)
        reach_date = date(reach_year, reach_month, reach_day)
        st.caption(f"🎯 목표총액 {total_goal_amount:,.0f}원 달성 예상: 약 **{months_needed}개월** 후 ({reach_date:%Y년 %m월})")

    st.divider()
    gap = actual_saving - total_goal
    if gap >= 0:
        st.success(f"✅ {latest_month} 전체 저축 목표 달성! (+{gap:,.0f}원)")
    else:
        st.info(f"{latest_month} 목표까지 **{abs(gap):,.0f}원** 남았습니다.")

    recent3 = all_months[:3]
    avg3 = (
        sum(
            abs(df[(df["연월"] == m) & (df["대분류"] == "고정지출") &
                   (df["소분류"].isin(["적금/저축", "청약", "연금"]))]["거래금액"].sum())
            for m in recent3
        ) / len(recent3)
    ) if len(recent3) > 0 else actual_saving
    yearly_actual = avg3 * 12
    yearly_goal   = total_goal * 12
    st.metric(
        "연간 저축 예상 (최근 3개월 평균)",
        f"{yearly_actual:,.0f}원",
        delta=f"{yearly_actual - yearly_goal:+,.0f}원 vs 연간 목표",
    )
