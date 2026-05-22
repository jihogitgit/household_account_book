import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tabs.uncategorized import CAT_MAP


def test_변동지출_소분류_3개만():
    """변동지출에는 생활/배달/병원만 있어야 한다."""
    assert CAT_MAP["변동지출"] == ["생활", "배달", "병원"]


def test_변동지출에_경조사_없음():
    """경조사는 변동지출 소분류가 아니다."""
    assert "경조사" not in CAT_MAP["변동지출"]


def test_변동지출에_효도_없음():
    """효도는 변동지출 소분류가 아니다."""
    assert "효도" not in CAT_MAP["변동지출"]


def test_경조사_소분류에_효도_포함():
    """효도는 경조사 대분류의 소분류여야 한다."""
    assert "효도" in CAT_MAP["경조사"]


def test_경조사_소분류_순서():
    """경조사 소분류는 경조사, 효도 순서여야 한다."""
    assert CAT_MAP["경조사"] == ["경조사", "효도"]


def test_모든_대분류_존재():
    """6개 대분류가 모두 있어야 한다."""
    expected = {"수입", "고정지출", "변동지출", "경조사", "내부이체", "기타"}
    assert expected == set(CAT_MAP.keys())


def test_고정지출_소분류_유지():
    """고정지출 소분류는 변경되지 않아야 한다."""
    assert CAT_MAP["고정지출"] == [
        "월세/이자", "보험", "연금", "청약", "적금/저축", "교통/통신", "공과금", "용돈"
    ]
