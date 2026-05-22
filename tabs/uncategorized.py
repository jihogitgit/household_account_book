"""
미분류 거래 탭 — 자동 분류되지 않은 거래를 수동으로 카테고리 지정합니다.
적요+거래유형별로 지정하면 동일 적요/거래유형의 모든 거래에 즉시 적용됩니다.
"""
import streamlit as st

from utils import apply_categorization, save_overrides

CAT_MAP = {
    "수입":    ["급여", "이자/캐시백", "기타"],
    "고정지출": ["월세/이자", "보험", "연금", "청약", "적금/저축", "교통/통신", "공과금", "용돈"],
    "변동지출": ["생활", "배달", "병원"],
    "경조사":  ["경조사", "효도"],
    "내부이체": ["생활비 이체", "여행비 이체", "계좌간 이체", "모임 출금"],
    "기타":    ["개인 이체", "기타"],
}


def render_uncategorized_tab():
    df = st.session_state.get("df")
    overrides: dict = st.session_state.get("overrides", {})

    if df is None:
        st.info("👈 사이드바에서 파일을 업로드하고 **데이터 로드** 버튼을 눌러주세요.")
        return

    unc = df[df["대분류"] == "미분류"].copy()

    if unc.empty:
        st.success("미분류 항목이 없습니다! ✅")
        return

    grouped = (
        unc.groupby(["적요", "거래 유형"])
        .agg(
            건수=("거래금액", "count"),
            합계=("거래금액", "sum"),
            통장=("_통장", "first"),
        )
        .reset_index()
    )
    grouped["합계절대값"] = grouped["합계"].abs()
    grouped = grouped.sort_values("합계절대값", ascending=False).drop(columns="합계절대값")

    st.warning(f"**{len(unc)}건** 미분류 | 고유 적요+거래유형 **{len(grouped)}개**")
    st.caption("카테고리를 지정하고 저장하면, 같은 적요+거래유형의 모든 거래에 자동 적용됩니다.")
    st.divider()

    # 헤더
    h = st.columns([0.5, 2.5, 1, 1, 2, 2, 2, 1])
    for col, label in zip(h, ["✓", "적요", "거래유형", "건수", "합계", "대분류", "소분류", ""]):
        col.caption(f"**{label}**")

    selected_items = []
    for _, row in grouped.iterrows():
        jeok = row["적요"]
        gtype = row["거래 유형"]
        c = st.columns([0.5, 2.5, 1, 1, 2, 2, 2, 1])

        checked = c[0].checkbox("✓", key=f"unc_chk_{jeok}_{gtype}", label_visibility="collapsed")
        c[1].markdown(f"**{jeok}**")
        c[2].caption(gtype)
        c[3].caption(f"{int(row['건수'])}건")
        amt = int(row["합계"])
        c[4].caption(f"{amt:+,}원")

        selected_cat = c[5].selectbox(
            "대분류",
            list(CAT_MAP.keys()),
            key=f"unc_cat_{jeok}_{gtype}",
            label_visibility="collapsed",
        )
        selected_sub = c[6].selectbox(
            "소분류",
            CAT_MAP[selected_cat],
            key=f"unc_sub_{jeok}_{gtype}",
            label_visibility="collapsed",
        )

        if checked:
            selected_items.append((jeok, gtype, selected_cat, selected_sub))

        if c[7].button("저장", key=f"unc_save_{jeok}_{gtype}", type="primary"):
            overrides[(jeok, gtype)] = {
                "대분류": selected_cat,
                "소분류": selected_sub,
                "IsFixed": selected_cat == "고정지출",
            }
            save_overrides(overrides)
            st.session_state.overrides = overrides

            raw_df = st.session_state.get("raw_df")
            if raw_df is not None:
                st.session_state.df = apply_categorization(raw_df, overrides)
            else:
                _df = st.session_state.df.copy()
                mask = (_df["적요"] == jeok) & (_df["거래 유형"] == gtype)
                _df.loc[mask, "대분류"] = selected_cat
                _df.loc[mask, "소분류"] = selected_sub
                _df.loc[mask, "IsFixed"] = selected_cat == "고정지출"
                st.session_state.df = _df
            st.rerun()

    # 일괄 저장
    if selected_items:
        st.divider()
        if st.button(f"💾 선택 {len(selected_items)}건 일괄 저장", key="unc_batch_save", type="primary"):
            for jeok, gtype, sel_cat, sel_sub in selected_items:
                overrides[(jeok, gtype)] = {
                    "대분류": sel_cat,
                    "소분류": sel_sub,
                    "IsFixed": sel_cat == "고정지출",
                }
            save_overrides(overrides)
            st.session_state.overrides = overrides
            raw_df = st.session_state.get("raw_df")
            if raw_df is not None:
                st.session_state.df = apply_categorization(raw_df, overrides)
            else:
                _df = st.session_state.df.copy()
                for jeok, gtype, sel_cat, sel_sub in selected_items:
                    mask = (_df["적요"] == jeok) & (_df["거래 유형"] == gtype)
                    _df.loc[mask, "대분류"] = sel_cat
                    _df.loc[mask, "소분류"] = sel_sub
                    _df.loc[mask, "IsFixed"] = sel_cat == "고정지출"
                st.session_state.df = _df
            st.rerun()

    st.divider()
    if st.button("💾 전체 저장", key="unc_save_all", type="primary"):
        new_ov = {}
        for _, row in grouped.iterrows():
            jeok = row["적요"]
            gtype = row["거래 유형"]
            cat_key = f"unc_cat_{jeok}_{gtype}"
            sub_key = f"unc_sub_{jeok}_{gtype}"
            sel_cat = st.session_state.get(cat_key, list(CAT_MAP.keys())[0])
            sel_sub = st.session_state.get(sub_key, CAT_MAP[sel_cat][0])
            new_ov[(jeok, gtype)] = {"대분류": sel_cat, "소분류": sel_sub, "IsFixed": sel_cat == "고정지출"}
        overrides.update(new_ov)
        save_overrides(overrides)
        st.session_state.overrides = overrides
        raw_df = st.session_state.get("raw_df")
        if raw_df is not None:
            st.session_state.df = apply_categorization(raw_df, overrides)
        else:
            _df = st.session_state.df.copy()
            for (jeok, gtype), ov in new_ov.items():
                mask = (_df["적요"] == jeok) & (_df["거래 유형"] == gtype)
                _df.loc[mask, "대분류"] = ov["대분류"]
                _df.loc[mask, "소분류"] = ov["소분류"]
                _df.loc[mask, "IsFixed"] = ov["IsFixed"]
            st.session_state.df = _df
        st.rerun()
