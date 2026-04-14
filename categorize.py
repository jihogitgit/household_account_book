import msoffcrypto
import pandas as pd
import io

base = '/Users/mw/prodect/통장/'
files = [
    ('생활비', '토스뱅크_거래내역 _생활비.xlsx'),
    ('경조사', '토스뱅크_거래내역_경조사.xlsx'),
    ('급여통장', '토스뱅크_거래내역_급여통장.xlsx'),
    ('비상금', '토스뱅크_거래내역_비상금.xlsx'),
]
password = '911017'


def decrypt(path):
    with open(path, 'rb') as enc_file:
        office_file = msoffcrypto.OfficeFile(enc_file)
        office_file.load_key(password=password)
        decrypted = io.BytesIO()
        office_file.decrypt(decrypted)
    decrypted.seek(0)
    return decrypted


def load_all():
    all_rows = []
    for label, f in files:
        dec = decrypt(base + f)
        df = pd.read_excel(dec, engine='openpyxl', header=8)
        df['_통장'] = label
        all_rows.append(df)
    df = pd.concat(all_rows, ignore_index=True)
    return df.dropna(subset=['거래 일시'])


# ── 카테고리 규칙 (위에서 아래 순서로 첫 번째 매칭 적용) ──────────────
rules = [
    # 수입
    ('수입', '급여',
        lambda r: r['거래 유형'] == '입금' and r['적요'] in ['유지호', '김채현']),
    ('수입', '이자/캐시백',
        lambda r: r['거래 유형'] in ['이자입금', '프로모션입금']),
    ('수입', '모임통장 정산',
        lambda r: r['거래 유형'] == '모임원송금'
                  and float(str(r['거래 금액']).replace(',', '')) > 0),

    # 내부이체 (가계부 집계에서 제외)
    ('내부이체', '생활비 이체',
        lambda r: r['적요'] == '생활비'
                  and r['거래 유형'] in ['입금', '자동이체', '내계좌간자동이체', '출금']),
    ('내부이체', '여행비 이체',
        lambda r: r['적요'] == '여행비'
                  and r['거래 유형'] in ['입금', '자동이체', '내계좌간자동이체', '출금']),
    ('내부이체', '추가 저축',
        lambda r: r['적요'] == '추가 저축'),
    ('내부이체', '계좌간 이체',
        lambda r: r['거래 유형'] == '내계좌간자동이체'),

    # 고정지출
    ('고정지출', '월세/주거',   lambda r: r['적요'] == '월세/이자'),
    ('고정지출', '보험',        lambda r: '보험' in str(r['적요'])),
    ('고정지출', '연금',        lambda r: '연금' in str(r['적요'])),
    ('고정지출', '적금/저축',
        lambda r: any(x in str(r['적요']) for x in ['적금', '청약', '청년도약'])),
    ('고정지출', '교통/통신',
        lambda r: any(x in str(r['적요']) for x in ['교통', '통신'])
                  and r['거래 유형'] == '자동이체'),
    ('고정지출', '용돈',        lambda r: '용돈' in str(r['적요'])),
    ('고정지출', '공과금',      lambda r: r['거래 유형'] == '지로출금'),

    # 경조사
    ('경조사', '경조사',        lambda r: r['_통장'] == '경조사'),

    # 변동지출: 배달 (우아한형제들보다 먼저)
    ('변동지출', '배달',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in ['우아한형제들', '쿠팡이츠'])),

    # 변동지출: 식비
    ('변동지출', '식비',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      '구의문복합식당', '겐로쿠우동', '동대문곱창', '마마쿡', '멕시카나', '멘노아지',
                      '바다어묵나라', '삼진스트라이크존', '석문어', '속초오징어', '식물원복합식당',
                      '짬뽕지존', '탄토탄토', '해운대대구탕', '호미스피자', '훼미리손칼국수',
                      '유미분김밥', '란영양', '느굿', '담벼락핫도그', '레드브릭스모크하우스',
                      '레이지아워', '롱메', '몽마르카부덴', '소소달', '소풍', '아리계곡', '야생과',
                      '엠엠씨', '원효로105', '정안', '제이지푸드시스템', '제주돔베고기집',
                      '순천미향', '애월장인', '슬로보트', '심학산도토리',
                      '유니드라멘', '명랑핫도그', '옥이네수산', '미래',
                      '이마트', '정성마트', '이편한마트', '이편한 정육점', '롯데프레시', '샘터마트',
                  ])),

    # 변동지출: 카페/음료/베이커리
    ('변동지출', '카페/음료',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      '커피', '카페', '공차', '더벤티', '매머드', '메가엠지씨', '잔물결', '컴포즈',
                      '씨미트', '가배도', '브루브루', '마노커피', '뚜레쥬르', '오투', '베이커리',
                      '베이글', '런던베이글', '빵', '과자점', '제과', '젤라또', '배스킨', '팔레트',
                      '신세계제과', '우리쌀빵', '윤숲', '온더브레드', '피코야', '투썸플레이스',
                  ])),

    # 변동지출: 편의점
    ('변동지출', '편의점',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      'GS25', 'gs25', '지에스25', '씨유', 'CU', '세븐일레븐', '이마트24',
                  ])),

    # 변동지출: 쇼핑
    ('변동지출', '쇼핑',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      '쿠팡', '다이소', '아트박스', '에스에스지', '네이버페이', '현대백',
                      '에이케이플라자', '롯데물산', '29cm', '오늘의집', '마켓컬리',
                      '후추포인트',
                  ])),

    # 변동지출: 뷰티/미용
    ('변동지출', '뷰티/미용',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in ['올리브영', '엘라스틴', '와이즐리'])),

    # 변동지출: 의료/약국
    ('변동지출', '의료/약국',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      '약국', '병원', '의원', '린여성', '네이처스파',
                  ])),

    # 변동지출: 문화/여가
    ('변동지출', '문화/여가',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      'CGV', '출판도시', '스파랜드', '스너글리', '시소', 'JITTER', 'MILS',
                  ])),

    # 변동지출: 교통
    ('변동지출', '교통',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      '고속버스', '코레일', '티머니', '택시',
                  ])),

    # 변동지출: 여행
    ('변동지출', '여행',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in [
                      '놀유니버스', '리조트', '제주', '애월', '서귀포', '주유소', '휴게소',
                  ])),

    # 변동지출: 반려동물
    ('변동지출', '반려동물',
        lambda r: r['거래 유형'] == '체크카드결제'
                  and any(x in str(r['적요']) for x in ['길고양이', '마르못'])),

    # 변동지출: 현금
    ('변동지출', '현금(ATM)',    lambda r: r['거래 유형'] == 'ATM출금'),

    # 기타
    ('기타', '모임 출금',
        lambda r: r['거래 유형'] == '모임원송금'
                  and float(str(r['거래 금액']).replace(',', '')) < 0),
    ('기타', '개인 이체',
        lambda r: r['거래 유형'] in ['입금', '출금']),
]


def categorize(row):
    for 대분류, 소분류, cond in rules:
        try:
            if cond(row):
                return 대분류, 소분류
        except Exception:
            pass
    return '미분류', '미분류'


def main():
    df = load_all()
    df[['대분류', '소분류']] = df.apply(
        lambda r: pd.Series(categorize(r)), axis=1
    )

    # 컬럼 정리
    out = df[['거래 일시', '적요', '거래 유형', '거래 금액', '거래 후 잔액', '_통장', '대분류', '소분류', '메모']].copy()
    out.columns = ['거래일시', '적요', '거래유형', '거래금액', '잔액', '통장', '대분류', '소분류', '메모']

    # 미분류 리포트
    unc = df[df['대분류'] == '미분류'][['적요', '거래 유형', '_통장', '거래 금액']]
    if not unc.empty:
        print("=== 미분류 항목 ===")
        print(unc.drop_duplicates('적요').to_string())

    # 저장
    out_path = base + '가계부_카테고리.xlsx'
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        out.to_excel(writer, sheet_name='전체내역', index=False)

        # 월별 요약
        out['연월'] = pd.to_datetime(out['거래일시']).dt.to_period('M').astype(str)
        pivot = out[out['대분류'].isin(['변동지출', '고정지출', '경조사', '수입'])].copy()
        pivot['거래금액'] = pd.to_numeric(pivot['거래금액'], errors='coerce')
        summary = pivot.groupby(['연월', '대분류', '소분류'])['거래금액'].sum().reset_index()
        summary.to_excel(writer, sheet_name='월별요약', index=False)

    print(f"\n저장 완료: {out_path}")
    print(f"전체 {len(out)}건 처리")

    # 카테고리별 집계 미리보기
    out['거래금액'] = pd.to_numeric(out['거래금액'], errors='coerce')
    exp = out[out['대분류'].isin(['변동지출', '고정지출', '경조사'])]
    print("\n=== 대분류별 총합 ===")
    print(exp.groupby(['대분류', '소분류'])['거래금액'].sum().to_string())


if __name__ == '__main__':
    main()
