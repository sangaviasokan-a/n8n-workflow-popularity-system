from app.collectors.trends import (
    GoogleTrendsCollector,
)
from app.processors.scorer import growth_to_score


def test_growth_calculation():
    values = [20, 25, 30]

    result = (
        GoogleTrendsCollector
        ._calculate_growth(values)
    )

    assert result == 50.0


def test_growth_with_zero_start():
    values = [0, 20, 30]

    result = (
        GoogleTrendsCollector
        ._calculate_growth(values)
    )

    assert result == 0.0


def test_empty_growth():
    values = []

    result = (
        GoogleTrendsCollector
        ._calculate_growth(values)
    )

    assert result == 0.0


def test_growth_score():
    assert growth_to_score(0) == 50.0
    assert growth_to_score(50) == 75.0
    assert growth_to_score(100) == 100.0