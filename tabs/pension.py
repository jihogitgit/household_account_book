"""
연금 시뮬레이션 탭
"""
import plotly.graph_objects as go
import streamlit as st

from database import get_db


def render_pension_tab() -> None:
    db = get_db()
    cfg = db.get_pension_config()

    col_input, col_result = st.columns([1, 1.5])

    # ── 입력 패널 ────────────────────────────────────────────────────────
    with col_input:
        st.subheader("⚙️ 연금 설정")
        with st.form("pension_form"):
            current_age    = st.number_input("현재 나이",             20, 70, int(cfg.get("현재나이", 35)),   step=1)
            retire_age     = st.number_input("은퇴 목표 나이",         45, 75, int(cfg.get("은퇴나이", 60)),   step=1)
            receive_age    = st.number_input("연금 수령 시작 나이",    55, 80, int(cfg.get("수령나이", 65)),   step=1)
            monthly_pay    = st.number_input("월 납입액 (원)",         min_value=0, step=50000,
                                             value=int(cfg.get("월납입액", 0)))
            rate           = st.number_input("예상 연수익률 (%)",      0.0, 15.0,
                                             float(cfg.get("예상수익률", 5.0)), step=0.5)
            national_pension = st.number_input(
                "국민연금 예상 월수령액 (원)", min_value=0, step=10000,
                value=int(cfg.get("국민연금_예상월액", 0)),
            )
            st.caption("💡 국민연금공단 내 연금 알아보기에서 확인 가능")
            monthly_expense = st.number_input(
                "은퇴 후 목표 월 생활비 (원)", min_value=0, step=100000,
                value=int(cfg.get("목표월생활비", 3000000)),
            )
            if st.form_submit_button("💾 계산 & 저장", type="primary", use_container_width=True):
                db.save_pension_config({
                    "현재나이": current_age, "은퇴나이": retire_age,
                    "수령나이": receive_age, "월납입액": monthly_pay,
                    "예상수익률": rate, "국민연금_예상월액": national_pension,
                    "목표월생활비": monthly_expense,
                })
                st.rerun()

    # ── 계산 ────────────────────────────────────────────────────────────
    accum_years  = max(retire_age - current_age, 0)
    recv_years   = max(90 - receive_age, 0)
    monthly_rate = rate / 12 / 100

    if monthly_rate > 0 and monthly_pay > 0 and accum_years > 0:
        accumulated = (
            monthly_pay
            * ((1 + monthly_rate) ** (accum_years * 12) - 1)
            / monthly_rate
        )
    else:
        accumulated = monthly_pay * accum_years * 12

    if monthly_rate > 0 and recv_years > 0:
        denom = 1 - (1 + monthly_rate) ** (-recv_years * 12)
        monthly_from_pension = accumulated * monthly_rate / denom if denom else 0
    elif recv_years > 0:
        monthly_from_pension = accumulated / (recv_years * 12)
    else:
        monthly_from_pension = 0

    total_monthly = monthly_from_pension + national_pension
    shortage      = max(0, monthly_expense - total_monthly)

    # 부족분 메우기 위한 추가 월납입액 역산
    if shortage > 0 and monthly_rate > 0 and accum_years > 0 and recv_years > 0:
        denom_recv = 1 - (1 + monthly_rate) ** (-recv_years * 12)
        needed_extra = shortage * denom_recv / monthly_rate if monthly_rate else shortage * recv_years * 12
        extra_monthly = (
            needed_extra * monthly_rate
            / ((1 + monthly_rate) ** (accum_years * 12) - 1)
        )
    else:
        extra_monthly = 0

    # ── 결과 패널 ───────────────────────────────────────────────────────
    with col_result:
        st.subheader("📊 시뮬레이션 결과")

        c1, c2 = st.columns(2)
        c1.metric("은퇴 시 예상 적립액",   f"{accumulated:,.0f}원")
        c2.metric("개인연금 월수령액",     f"{monthly_from_pension:,.0f}원")
        c3, c4 = st.columns(2)
        c3.metric("총 월수령액",           f"{total_monthly:,.0f}원",
                  help="개인연금 + 국민연금")
        if shortage > 0:
            c4.metric("목표 대비 부족액",  f"{shortage:,.0f}원/월",
                      delta=f"-{shortage:,.0f}원", delta_color="inverse")
        else:
            surplus = total_monthly - monthly_expense
            c4.metric("목표 초과액",       f"{surplus:,.0f}원/월",
                      delta=f"+{surplus:,.0f}원")

        if shortage > 0:
            st.warning(
                f"월 **{shortage:,.0f}원** 부족 — "
                f"납입액을 **{extra_monthly:,.0f}원** 추가하면 목표 달성 가능합니다."
            )
        else:
            st.success("🎉 목표 월 생활비를 충족합니다!")

        st.divider()

        # 적립 성장 곡선
        ages   = list(range(current_age, retire_age + 1))
        values = []
        for a in ages:
            y = a - current_age
            if monthly_rate > 0 and monthly_pay > 0:
                v = monthly_pay * ((1 + monthly_rate) ** (y * 12) - 1) / monthly_rate
            else:
                v = monthly_pay * y * 12
            values.append(v)

        recv_end_age = min(90, retire_age + recv_years)
        recv_ages    = list(range(retire_age, recv_end_age + 1))
        recv_values  = []
        bal = accumulated
        for _ in recv_ages:
            recv_values.append(max(0, bal))
            bal = max(0, bal * (1 + monthly_rate) ** 12 - monthly_from_pension * 12)

        fig = go.Figure()
        fig.add_scatter(
            x=ages, y=values, name="납입 적립금",
            fill="tozeroy", line=dict(color="#4F8EF7", width=2),
        )
        fig.add_scatter(
            x=recv_ages, y=recv_values, name="수령 후 잔액",
            fill="tozeroy", line=dict(color="#EF4444", width=2, dash="dash"),
        )
        fig.add_hline(
            y=accumulated, line_dash="dot", line_color="#10B981",
            annotation_text=f"은퇴 시 {accumulated:,.0f}원",
        )
        fig.update_layout(
            title="연도별 적립금 시뮬레이션", xaxis_title="나이", yaxis_title="금액 (원)",
            height=320, yaxis_tickformat=",",
            legend=dict(orientation="h", y=-0.25), margin=dict(t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            f"📌 납입기간: {accum_years}년 ({current_age}세→{retire_age}세) · "
            f"수령기간: {recv_years}년 ({receive_age}세→90세) · "
            f"예상수익률: {rate:.1f}%/년"
        )
