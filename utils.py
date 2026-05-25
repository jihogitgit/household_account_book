"""
가계부 공유 유틸리티 — make_report.py 로직을 Streamlit 앱용으로 추출
"""
import io
import json
from pathlib import Path

import msoffcrypto
import pandas as pd

OVERRIDES_PATH = Path(__file__).parent / "overrides.json"
BUDGETS_PATH = Path(__file__).parent / "budgets.json"

# ── 색상 팔레트 ───────────────────────────────────────────────────────
CAT_COLOR_PLOTLY = {
    "수입":    "#A8E6A8",
    "고정지출": "#7EB3F5",
    "변동지출": "#FFD166",
    "경조사":  "#F4B8B8",
    "내부이체": "#DDDDDD",
    "기타":    "#CCCCCC",
    "미분류":  "#FF6666",
}

SUBCAT_COLORS = [
    "#5B9BD5", "#70AD47", "#FFC000", "#FF7043", "#AB47BC",
    "#26A69A", "#EC407A", "#8D6E63", "#78909C", "#42A5F5",
    "#D4E157", "#FF8A65",
]

# ── 카테고리 규칙 (대분류, 소분류, IsFixed, 조건 lambda) ──────────────
rules = [
    # ── 수입 ──────────────────────────────────────────────────────────────
    ("수입", "급여", False,
        lambda r: r["거래 유형"] == "입금"
                  and r["적요"] in ["유지호", "김채현"]
                  and r["_통장"] == "급여통장"),
    ("수입", "이자/캐시백", False,
        lambda r: r["거래 유형"] in ["이자입금", "프로모션입금"]),

    # ── 내부이체 (집계 제외) ───────────────────────────────────────────────
    ("내부이체", "생활비 이체", False,
        lambda r: r["적요"] == "생활비"
                  and r["거래 유형"] in ["입금", "자동이체", "내계좌간자동이체", "출금"]),
    ("내부이체", "여행비 이체", False,
        lambda r: r["적요"] == "여행비"
                  and r["거래 유형"] in ["입금", "자동이체", "내계좌간자동이체", "출금"]),
    ("내부이체", "계좌간 이체", False,
        lambda r: r["적요"] == "추가 저축"),
    ("내부이체", "모임 출금", False,
        lambda r: r["거래 유형"] == "모임원송금" and r["_통장"] != "경조사"),
    ("내부이체", "모임 출금", False,
        lambda r: r["거래 유형"] == "출금"
                  and "모임통장" in str(r["적요"]) and r["_통장"] != "경조사"),

    # ── 고정지출 ──────────────────────────────────────────────────────────
    ("고정지출", "월세/이자", True,
        lambda r: r["적요"] == "월세/이자"),
    ("고정지출", "보험", True,
        lambda r: "보험" in str(r["적요"]) and r["거래 유형"] == "자동이체"),
    ("고정지출", "연금", True,
        lambda r: "연금" in str(r["적요"]) and r["거래 유형"] == "자동이체"),
    ("고정지출", "청약", True,
        lambda r: "청약" in str(r["적요"]) and r["거래 유형"] == "자동이체"),
    ("고정지출", "적금/저축", True,
        lambda r: any(x in str(r["적요"]) for x in ["적금", "청년도약"])
                  and r["거래 유형"] in ["자동이체", "내계좌간자동이체"]),
    ("고정지출", "교통/통신", True,
        lambda r: r["거래 유형"] in ["자동이체", "지로출금"]
                  and any(x in str(r["적요"]) for x in ["교통", "통신", "KT"])),
    ("고정지출", "공과금", True,
        lambda r: r["거래 유형"] in ["지로출금", "자동이체"]
                  and any(x in str(r["적요"]) for x in [
                      "관리비", "전기", "가스", "수도", "도시가스", "한전", "가스공사", "열공급",
                  ])),
    ("고정지출", "용돈", True,
        lambda r: "용돈" in str(r["적요"]) and r["거래 유형"] == "자동이체"),

    # ── 경조사 ────────────────────────────────────────────────────────────
    ("경조사", "경조사", False,
        lambda r: r["_통장"] == "경조사"),

    # ── 변동지출: 배달 ────────────────────────────────────────────────────
    ("변동지출", "배달", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in ["우아한형제들", "쿠팡이츠"])),

    # ── 변동지출: 병원 ────────────────────────────────────────────────────
    ("변동지출", "병원", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "약국", "병원", "의원", "린여성", "네이처스파",
                  ])),

    # ── 변동지출: 생활 (나머지 카드/ATM 결제 전부) ───────────────────────
    ("변동지출", "생활", False,
        lambda r: r["거래 유형"] in ["체크카드결제", "ATM출금"]),

    # ── 기타 ──────────────────────────────────────────────────────────────
    ("기타", "개인 이체", False,
        lambda r: r["거래 유형"] in ["입금", "출금"]),
]


# ── 핵심 함수 ─────────────────────────────────────────────────────────

def decrypt(source, password: str) -> io.BytesIO:
    """파일 경로(str/Path) 또는 file-like object → 복호화된 BytesIO"""
    if isinstance(source, (str, Path)):
        f = open(source, "rb")
        should_close = True
    else:
        f = source
        should_close = False
    try:
        of = msoffcrypto.OfficeFile(f)
        of.load_key(password=password)
        dec = io.BytesIO()
        of.decrypt(dec)
    finally:
        if should_close:
            f.close()
    dec.seek(0)
    return dec


def detect_account_name(filename: str) -> str:
    """'토스뱅크_거래내역 _생활비.xlsx' → '생활비'"""
    stem = filename.replace("토스뱅크_거래내역", "").replace("_", "").replace(" ", "")
    stem = stem.replace(".xlsx", "").replace(".XLSX", "")
    for name in ["생활비", "경조사", "급여통장", "비상금"]:
        if name in stem:
            return name
    return stem or filename


def load_excel(source, account_name: str, password: str) -> pd.DataFrame:
    """복호화 → pd.read_excel(header=8) → _통장 컬럼 추가"""
    dec = decrypt(source, password)
    df = pd.read_excel(dec, engine="openpyxl", header=8)
    df["_통장"] = account_name
    return df


def categorize(row, overrides: dict) -> tuple:
    """(대분류, 소분류, IsFixed) 반환. overrides 우선 → rules → 미분류"""
    적요 = str(row.get("적요", ""))
    거래유형 = str(row.get("거래 유형", ""))
    key = (적요, 거래유형)
    fallback = (적요, "")
    if key in overrides:
        ov = overrides[key]
        return ov["대분류"], ov["소분류"], bool(ov.get("IsFixed", False))
    if fallback in overrides:
        ov = overrides[fallback]
        return ov["대분류"], ov["소분류"], bool(ov.get("IsFixed", False))
    for 대분류, 소분류, is_fixed, cond in rules:
        try:
            if cond(row):
                return 대분류, 소분류, is_fixed
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug("categorize rule error '%s': %s", 적요, e)
    return "미분류", "미분류", False


def apply_categorization(df: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    """원본 DataFrame에 분류 컬럼 적용, 날짜/금액 변환.
    성능: 단일 패스로 세 컬럼을 동시에 채워 df.apply(pd.Series) 오버헤드를 제거."""
    df = df.copy()
    df = df.dropna(subset=["거래 일시"]).reset_index(drop=True)

    n = len(df)
    cat_main = [None] * n
    cat_sub = [None] * n
    cat_fixed = [False] * n

    records = df.to_dict("records")
    for i, row in enumerate(records):
        m, s, f = categorize(row, overrides)
        cat_main[i] = m
        cat_sub[i] = s
        cat_fixed[i] = f

    df["대분류"] = cat_main
    df["소분류"] = cat_sub
    df["IsFixed"] = cat_fixed
    df["거래금액"] = pd.to_numeric(df["거래 금액"], errors="coerce")
    df["거래일시"] = pd.to_datetime(df["거래 일시"], errors="coerce")
    df["날짜"]    = df["거래일시"].dt.date
    df["연월"]    = df["거래일시"].dt.to_period("M").astype(str)
    return df.sort_values("거래일시", ascending=False).reset_index(drop=True)


def detect_fixed_candidates(
    df: pd.DataFrame,
    window_months: int = 3,
    amount_tol: float = 0.10,
) -> pd.DataFrame:
    """3개월 이상 연속으로 비슷한 금액(±amount_tol)이 출금된 적요를 IsFixed 후보로 반환.

    Returns: DataFrame with columns [적요, 평균금액, 발생월수, 현재IsFixed]
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["적요", "평균금액", "발생월수", "현재IsFixed"])

    exp = df[df["대분류"].isin(["고정지출", "변동지출", "기타"])].copy()
    if exp.empty:
        return pd.DataFrame(columns=["적요", "평균금액", "발생월수", "현재IsFixed"])

    # 적요 + 연월 단위 합산
    grp = exp.groupby(["적요", "연월"])["거래금액"].sum().reset_index()
    agg = grp.groupby("적요").agg(
        발생월수=("연월", "nunique"),
        평균금액=("거래금액", "mean"),
        표준편차=("거래금액", "std"),
    ).reset_index()

    # 변동계수 (|std / mean|); mean 0 또는 NaN 방지
    mean_abs = agg["평균금액"].abs().replace(0, pd.NA)
    agg["cv"] = (agg["표준편차"].abs() / mean_abs).fillna(0).astype(float)

    # 현재 IsFixed 여부
    fixed_by_jeok = (
        exp.groupby("적요")["IsFixed"].max().astype(bool).to_dict()
    )
    agg["현재IsFixed"] = agg["적요"].map(fixed_by_jeok).fillna(False).astype(bool)

    cand = agg[
        (agg["발생월수"] >= window_months)
        & (agg["cv"] <= amount_tol)
        & (~agg["현재IsFixed"])
    ].copy()

    cand["평균금액"] = cand["평균금액"].round(0)
    return (
        cand[["적요", "평균금액", "발생월수", "현재IsFixed"]]
        .sort_values("발생월수", ascending=False)
        .reset_index(drop=True)
    )


def build_monthly_kpis(df: pd.DataFrame, yearmonth: str) -> dict:
    """선택 월 KPI: {총수입, 고정지출, 변동지출, 경조사, 순수지, 이전월_총수입, ...}"""
    months = sorted(df["연월"].unique())
    idx = months.index(yearmonth) if yearmonth in months else len(months) - 1

    def _kpi(ym):
        m = df[(df["연월"] == ym) & ~df["대분류"].isin(["내부이체"])]
        income  = m[m["대분류"] == "수입"]["거래금액"].sum()
        fixed   = m[m["대분류"] == "고정지출"]["거래금액"].sum()
        var     = m[m["대분류"] == "변동지출"]["거래금액"].sum()
        event   = m[m["대분류"] == "경조사"]["거래금액"].sum()
        return {
            "총수입":   income,
            "고정지출": fixed,
            "변동지출": var,
            "경조사":   event,
            "순수지":   income + fixed + var + event,
        }

    curr = _kpi(yearmonth)
    prev_ym = months[idx - 1] if idx > 0 else None
    prev = _kpi(prev_ym) if prev_ym else {}
    curr["prev"] = prev
    return curr


def load_overrides() -> dict:
    from database import get_db
    return get_db().get_overrides()


def save_overrides(overrides: dict) -> None:
    from database import get_db
    get_db().save_overrides(overrides)


def load_budgets() -> dict:
    from database import get_db
    return get_db().get_budgets()


def save_budgets(budgets: dict) -> None:
    from database import get_db
    get_db().save_budgets(budgets)
