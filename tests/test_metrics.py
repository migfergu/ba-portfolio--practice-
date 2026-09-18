import pytest

from src.metrics import variance_pct


def test_variance_pct_positive():
    assert variance_pct(110, 100) == pytest.approx(0.10)


def test_variance_pct_negative():
    assert variance_pct(90, 100) == pytest.approx(-0.10)


def test_variance_pct_zero_budget_raises():
    with pytest.raises(ValueError):
        variance_pct(100, 0)
