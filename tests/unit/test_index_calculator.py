from datetime import date

import pytest

from core.index_calculator import IndexCalculator


class TestComputeDailyReturns:
    def setup_method(self):
        self.calculator = IndexCalculator(base_value=100.0, base_date="2024-01-01")

    def test_normal_returns(self):
        current = {"RELIANCE": 110.0, "TCS": 210.0}
        previous = {"RELIANCE": 100.0, "TCS": 200.0}
        returns = self.calculator.compute_daily_returns(current, previous)
        assert abs(returns["RELIANCE"] - 0.1) < 1e-10
        assert abs(returns["TCS"] - 0.05) < 1e-10

    def test_missing_previous_price(self):
        current = {"RELIANCE": 110.0, "TCS": 210.0}
        previous = {"RELIANCE": 100.0}
        returns = self.calculator.compute_daily_returns(current, previous)
        assert "RELIANCE" in returns
        assert "TCS" not in returns

    def test_zero_previous_price(self):
        current = {"RELIANCE": 110.0}
        previous = {"RELIANCE": 0.0}
        returns = self.calculator.compute_daily_returns(current, previous)
        assert "RELIANCE" not in returns

    def test_negative_return(self):
        current = {"RELIANCE": 90.0}
        previous = {"RELIANCE": 100.0}
        returns = self.calculator.compute_daily_returns(current, previous)
        assert abs(returns["RELIANCE"] - (-0.1)) < 1e-10

    def test_empty_prices(self):
        returns = self.calculator.compute_daily_returns({}, {})
        assert returns == {}


class TestComputeIndexLevel:
    def setup_method(self):
        self.calculator = IndexCalculator(base_value=100.0, base_date="2024-01-01")

    def test_positive_return(self):
        returns = {"A": 0.05, "B": 0.03}
        level, avg_return = self.calculator.compute_index_level(100.0, returns)
        expected_avg = 0.04
        assert abs(avg_return - expected_avg) < 1e-8
        assert abs(level - 104.0) < 1e-4

    def test_zero_return(self):
        returns = {"A": 0.0, "B": 0.0}
        level, avg_return = self.calculator.compute_index_level(100.0, returns)
        assert abs(avg_return) < 1e-8
        assert abs(level - 100.0) < 1e-4

    def test_empty_returns(self):
        level, avg_return = self.calculator.compute_index_level(100.0, {})
        assert level == 100.0
        assert avg_return == 0.0

    def test_negative_return(self):
        returns = {"A": -0.05, "B": -0.03}
        level, avg_return = self.calculator.compute_index_level(100.0, returns)
        expected_avg = -0.04
        assert abs(avg_return - expected_avg) < 1e-8
        assert abs(level - 96.0) < 1e-4


class TestHandleMissingPrices:
    def setup_method(self):
        self.calculator = IndexCalculator(base_value=100.0, base_date="2024-01-01")

    def test_carry_forward(self):
        current = {"A": 110.0}
        previous = {"A": 100.0, "B": 200.0}
        constituents = {"A", "B"}
        filled, carried, missing = self.calculator.handle_missing_prices(
            current, previous, constituents
        )
        assert filled["B"] == 200.0
        assert "B" in carried
        assert len(missing) == 0

    def test_no_previous_available(self):
        current = {"A": 110.0}
        previous = {"A": 100.0}
        constituents = {"A", "B"}
        filled, carried, missing = self.calculator.handle_missing_prices(
            current, previous, constituents
        )
        assert "B" not in filled
        assert "B" in missing
        assert len(carried) == 0

    def test_all_present(self):
        current = {"A": 110.0, "B": 210.0}
        previous = {"A": 100.0, "B": 200.0}
        constituents = {"A", "B"}
        filled, carried, missing = self.calculator.handle_missing_prices(
            current, previous, constituents
        )
        assert len(carried) == 0
        assert len(missing) == 0


class TestCalculateIndex:
    def setup_method(self):
        self.calculator = IndexCalculator(base_value=100.0, base_date="2024-01-01")

    def test_first_day_from_base(self):
        result = self.calculator.calculate_index(
            business_date=date(2024, 1, 2),
            current_prices={"A": 105.0, "B": 205.0},
            previous_prices={"A": 100.0, "B": 200.0},
            previous_level=None,
            constituent_symbols={"A", "B"},
        )
        assert result.business_date == date(2024, 1, 2)
        assert result.constituent_count == 2
        assert result.index_level > 100.0

    def test_with_missing_constituent(self):
        result = self.calculator.calculate_index(
            business_date=date(2024, 1, 2),
            current_prices={"A": 105.0},
            previous_prices={"A": 100.0},
            previous_level=100.0,
            constituent_symbols={"A", "B"},
        )
        assert "B" in result.missing_symbols
        assert result.constituent_count == 1

    def test_constituent_change(self):
        result = self.calculator.calculate_index(
            business_date=date(2024, 1, 2),
            current_prices={"A": 105.0, "C": 310.0},
            previous_prices={"A": 100.0, "B": 200.0, "C": 300.0},
            previous_level=100.0,
            constituent_symbols={"A", "C"},
        )
        assert result.constituent_count == 2
        assert "B" not in result.missing_symbols
