"""
가계부 공유 유틸리티 — make_report.py 로직을 Streamlit 앱용으로 추출
"""
import io
import json
from pathlib import Path

import msoffcrypto
import pandas as pd

OVERRIDES_PATH = Path(__file__).parent / "overrides.json"
PASSWORD = "911017"

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
    # 수입
    ("수입", "급여", False,
        lambda r: r["거래 유형"] == "입금" and r["적요"] in ["유지호", "김채현"]),
    ("수입", "이자/캐시백", False,
        lambda r: r["거래 유형"] in ["이자입금", "프로모션입금"]),
    ("수입", "모임통장 정산", False,
        lambda r: r["거래 유형"] == "모임원송금"
                  and float(str(r["거래 금액"]).replace(",", "")) > 0),

    # 내부이체
    ("내부이체", "생활비 이체", False,
        lambda r: r["적요"] == "생활비"
                  and r["거래 유형"] in ["입금", "자동이체", "내계좌간자동이체", "출금"]),
    ("내부이체", "여행비 이체", False,
        lambda r: r["적요"] == "여행비"
                  and r["거래 유형"] in ["입금", "자동이체", "내계좌간자동이체", "출금"]),
    ("내부이체", "추가 저축", False,
        lambda r: r["적요"] == "추가 저축"),
    ("내부이체", "계좌간 이체", False,
        lambda r: r["거래 유형"] == "내계좌간자동이체"),

    # 고정지출: 주거/통신 (KT/LG/SK/통신 포함 — 최우선)
    ("고정지출", "주거/통신", True,
        lambda r: bool(
            pd.Series([str(r["적요"])]).str.contains(
                r"KT|LG|SK|통신", case=False, na=False
            ).iloc[0]
        )),

    # 고정지출
    ("고정지출", "월세/주거", True,   lambda r: r["적요"] == "월세/이자"),
    ("고정지출", "보험", True,        lambda r: "보험" in str(r["적요"])),
    ("고정지출", "연금", True,        lambda r: "연금" in str(r["적요"])),
    ("고정지출", "적금/저축", True,
        lambda r: any(x in str(r["적요"]) for x in ["적금", "청약", "청년도약"])),
    ("고정지출", "교통비", False,
        lambda r: r["적요"] == "채현 교통비" and r["거래 유형"] == "자동이체"),
    ("고정지출", "용돈", True,        lambda r: "용돈" in str(r["적요"])),
    ("고정지출", "공과금", True,      lambda r: r["거래 유형"] == "지로출금"),
    ("고정지출", "정기구독", True,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "JITTER", "MILS", "넷플릭스", "netflix",
                      "유튜브", "youtube", "spotify", "스포티파이", "왓챠", "웨이브",
                  ])),

    # 경조사
    ("경조사", "경조사", False,       lambda r: r["_통장"] == "경조사"),

    # 변동지출
    ("변동지출", "배달", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in ["우아한형제들", "쿠팡이츠"])),
    ("변동지출", "식비", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "구의문복합식당", "겐로쿠우동", "동대문곱창", "마마쿡", "멕시카나", "멘노아지",
                      "바다어묵나라", "삼진스트라이크존", "석문어", "속초오징어", "식물원복합식당",
                      "짬뽕지존", "탄토탄토", "해운대대구탕", "호미스피자", "훼미리손칼국수",
                      "유미분김밥", "란영양", "느굿", "담벼락핫도그", "레드브릭스모크하우스",
                      "레이지아워", "롱메", "몽마르카부덴", "소소달", "소풍", "아리계곡", "야생과",
                      "엠엠씨", "원효로105", "정안", "제이지푸드시스템", "제주돔베고기집",
                      "순천미향", "애월장인", "슬로보트", "심학산도토리",
                      "이마트", "정성마트", "이편한마트", "이편한 정육점", "롯데프레시", "샘터마트",
                      "유니드라멘", "명랑핫도그", "옥이네수산", "미래",
                  ])),
    ("변동지출", "카페/음료", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "커피", "카페", "공차", "더벤티", "매머드", "메가엠지씨", "잔물결", "컴포즈",
                      "씨미트", "가배도", "브루브루", "마노커피", "뚜레쥬르", "오투", "베이커리",
                      "베이글", "런던베이글", "빵", "과자점", "제과", "젤라또", "배스킨", "팔레트",
                      "신세계제과", "우리쌀빵", "윤숲", "온더브레드", "피코야", "투썸플레이스",
                  ])),
    ("변동지출", "편의점", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "GS25", "gs25", "지에스25", "씨유", "CU", "세븐일레븐", "이마트24",
                  ])),
    ("변동지출", "쇼핑", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "쿠팡", "다이소", "아트박스", "에스에스지", "네이버페이", "현대백",
                      "에이케이플라자", "롯데물산", "29cm", "오늘의집", "마켓컬리", "후추포인트",
                  ])),
    ("변동지출", "뷰티/미용", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in ["올리브영", "엘라스틴", "와이즐리"])),
    ("변동지출", "의료/약국", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "약국", "병원", "의원", "린여성", "네이처스파",
                  ])),
    ("변동지출", "문화/여가", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "CGV", "출판도시", "스파랜드", "스너글리", "시소",
                  ])),
    ("변동지출", "교통", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "고속버스", "코레일", "티머니", "택시",
                  ])),
    ("변동지출", "여행", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in [
                      "놀유니버스", "리조트", "제주", "애월", "서귀포", "주유소", "휴게소",
                  ])),
    ("변동지출", "반려동물", False,
        lambda r: r["거래 유형"] == "체크카드결제"
                  and any(x in str(r["적요"]) for x in ["길고양이", "마르못"])),
    ("변동지출", "현금(ATM)", False,   lambda r: r["거래 유형"] == "ATM출금"),

    # 기타
    ("기타", "모임 출금", False,
        lambda r: r["거래 유형"] == "모임원송금"
                  and float(str(r["거래 금액"]).replace(",", "")) < 0),
    ("기타", "개인 이체", False,
        lambda r: r["거래 유형"] in ["입금", "출금"]),
]


# ── 핵심 함수 ─────────────────────────────────────────────────────────

def decrypt(source) -> io.BytesIO:
    """파일 경로(str/Path) 또는 file-like object → 복호화된 BytesIO"""
    if isinstance(source, (str, Path)):
        f = open(source, "rb")
        should_close = True
    else:
        f = source
        should_close = False
    try:
        of = msoffcrypto.OfficeFile(f)
        of.load_key(password=PASSWORD)
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


def load_excel(source, account_name: str) -> pd.DataFrame:
    """복호화 → pd.read_excel(header=8) → _통장 컬럼 추가"""
    dec = decrypt(source)
    df = pd.read_excel(dec, engine="openpyxl", header=8)
    df["_통장"] = account_name
    return df


def categorize(row, overrides: dict) -> tuple:
    """(대분류, 소분류, IsFixed) 반환. overrides 우선 → rules → 미분류"""
    적요 = str(row.get("적요", ""))
    if 적요 in overrides:
        ov = overrides[적요]
        return ov["대분류"], ov["소분류"], bool(ov.get("IsFixed", False))
    for 대분류, 소분류, is_fixed, cond in rules:
        try:
            if cond(row):
                return 대분류, 소분류, is_fixed
        except Exception:
            pass
    return "미분류", "미분류", False


def apply_categorization(df: pd.DataFrame, overrides: dict) -> pd.DataFrame:
    """원본 DataFrame에 분류 컬럼 적용, 날짜/금액 변환"""
    df = df.copy()
    df = df.dropna(subset=["거래 일시"])
    result = df.apply(lambda r: pd.Series(categorize(r, overrides)), axis=1)
    df["대분류"]  = result[0]
    df["소분류"]  = result[1]
    df["IsFixed"] = result[2]
    df["거래금액"] = pd.to_numeric(df["거래 금액"], errors="coerce")
    df["거래일시"] = pd.to_datetime(df["거래 일시"], errors="coerce")
    df["날짜"]    = df["거래일시"].dt.date
    df["연월"]    = df["거래일시"].dt.to_period("M").astype(str)
    return df.sort_values("거래일시", ascending=False).reset_index(drop=True)


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
    if OVERRIDES_PATH.exists():
        try:
            return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_overrides(overrides: dict) -> None:
    OVERRIDES_PATH.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
