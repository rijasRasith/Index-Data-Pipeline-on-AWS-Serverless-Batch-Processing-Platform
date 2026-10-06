from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


@dataclass
class IndexResult:
    business_date: date
    index_level: float
    daily_return: Optional[float]
    constituent_count: int
    missing_symbols: list[str] = field(default_factory=list)
    carried_forward: list[str] = field(default_factory=list)


class IndexCalculator:
    def __init__(self, base_value: float = 100.0, base_date: str = "2024-01-01"):
        self.base_value = base_value
        self.base_date = date.fromisoformat(base_date)

    def compute_daily_returns(
        self,
        current_prices: dict[str, float],
        previous_prices: dict[str, float],
    ) -> dict[str, float]:
        returns = {}
        for symbol, current_close in current_prices.items():
            if symbol in previous_prices and previous_prices[symbol] > 0:
                returns[symbol] = (current_close / previous_prices[symbol]) - 1
        return returns

    def compute_index_level(
        self,
        previous_level: float,
        stock_returns: dict[str, float],
    ) -> tuple[float, float]:
        if not stock_returns:
            return previous_level, 0.0
        avg_return = sum(stock_returns.values()) / len(stock_returns)
        new_level = previous_level * (1 + avg_return)
        return round(new_level, 6), round(avg_return, 8)

    def handle_missing_prices(
        self,
        current_prices: dict[str, float],
        previous_prices: dict[str, float],
        constituent_symbols: set[str],
    ) -> tuple[dict[str, float], list[str], list[str]]:
        filled_prices = dict(current_prices)
        carried_forward = []
        still_missing = []

        for symbol in constituent_symbols:
            if symbol not in filled_prices:
                if symbol in previous_prices:
                    filled_prices[symbol] = previous_prices[symbol]
                    carried_forward.append(symbol)
                else:
                    still_missing.append(symbol)

        return filled_prices, carried_forward, still_missing

    def calculate_index(
        self,
        business_date: date,
        current_prices: dict[str, float],
        previous_prices: dict[str, float],
        previous_level: Optional[float],
        constituent_symbols: set[str],
    ) -> IndexResult:
        if previous_level is None:
            previous_level = self.base_value

        filled_prices, carried_forward, missing = self.handle_missing_prices(
            current_prices, previous_prices, constituent_symbols
        )

        active_prices = {
            s: p for s, p in filled_prices.items()
            if s in constituent_symbols and s not in missing
        }

        active_previous = {
            s: p for s, p in previous_prices.items()
            if s in active_prices
        }

        returns = self.compute_daily_returns(active_prices, active_previous)
        index_level, daily_return = self.compute_index_level(previous_level, returns)

        return IndexResult(
            business_date=business_date,
            index_level=index_level,
            daily_return=daily_return,
            constituent_count=len(returns),
            missing_symbols=missing,
            carried_forward=carried_forward,
        )

    def process_price_dataframe(
        self,
        df: pd.DataFrame,
        previous_prices: dict[str, float],
        previous_level: Optional[float],
        constituent_symbols: set[str],
        business_date: date,
    ) -> IndexResult:
        current_prices = {}
        for _, row in df.iterrows():
            symbol = str(row["symbol"]).strip().upper()
            current_prices[symbol] = float(row["close"])

        return self.calculate_index(
            business_date=business_date,
            current_prices=current_prices,
            previous_prices=previous_prices,
            previous_level=previous_level,
            constituent_symbols=constituent_symbols,
        )
