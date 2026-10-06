import csv
import io
import random
from datetime import date, timedelta
from typing import Optional

from core.constituents import CONSTITUENT_SYMBOLS, BASE_PRICES


class SyntheticDataGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.last_prices = dict(BASE_PRICES)

    def generate_daily_prices(
        self,
        business_date: date,
        symbols: Optional[list[str]] = None,
        missing_symbols: Optional[list[str]] = None,
        invalid_rows: Optional[list[dict]] = None,
        include_extra_column: bool = False,
    ) -> str:
        if symbols is None:
            symbols = list(CONSTITUENT_SYMBOLS)

        if missing_symbols:
            symbols = [s for s in symbols if s not in missing_symbols]

        output = io.StringIO()
        fieldnames = ["date", "symbol", "open", "high", "low", "close", "volume"]
        if include_extra_column:
            fieldnames.append("vwap")

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for symbol in symbols:
            base = self.last_prices.get(symbol, 1000.0)
            daily_return = self.rng.gauss(0.0005, 0.02)
            close = round(base * (1 + daily_return), 2)
            low = round(close * (1 - abs(self.rng.gauss(0, 0.01))), 2)
            high = round(close * (1 + abs(self.rng.gauss(0, 0.01))), 2)
            open_price = round(base * (1 + self.rng.gauss(0, 0.005)), 2)
            open_price = max(low, min(high, open_price))
            volume = self.rng.randint(100000, 50000000)

            row = {
                "date": business_date.isoformat(),
                "symbol": symbol,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
            if include_extra_column:
                row["vwap"] = round((high + low + close) / 3, 2)

            writer.writerow(row)
            self.last_prices[symbol] = close

        if invalid_rows:
            for inv_row in invalid_rows:
                writer.writerow(inv_row)

        return output.getvalue()

    def generate_bad_file_negative_price(self, business_date: date) -> str:
        return self.generate_daily_prices(
            business_date,
            invalid_rows=[
                {
                    "date": business_date.isoformat(),
                    "symbol": "FAKESYM",
                    "open": -100.0,
                    "high": 50.0,
                    "low": 60.0,
                    "close": 55.0,
                    "volume": -500,
                }
            ],
        )

    def generate_bad_file_wrong_date(self, business_date: date) -> str:
        wrong_date = business_date - timedelta(days=5)
        return self.generate_daily_prices(
            business_date,
            invalid_rows=[
                {
                    "date": wrong_date.isoformat(),
                    "symbol": "RELIANCE",
                    "open": 2500.0,
                    "high": 2550.0,
                    "low": 2480.0,
                    "close": 2530.0,
                    "volume": 1000000,
                }
            ],
        )

    def generate_duplicate_file(self, business_date: date) -> str:
        content = self.generate_daily_prices(business_date, symbols=["RELIANCE", "TCS"])
        lines = content.strip().split("\n")
        lines.append(lines[1])
        return "\n".join(lines) + "\n"

    def generate_week(
        self,
        start_date: date,
        days: int = 5,
        include_extra_column_on_day: Optional[int] = None,
    ) -> list[tuple[str, str]]:
        files = []
        current = start_date
        for i in range(days):
            while current.weekday() >= 5:
                current += timedelta(days=1)
            include_extra = include_extra_column_on_day is not None and i == include_extra_column_on_day
            file_name = f"prices_{current.isoformat()}.csv"
            content = self.generate_daily_prices(current, include_extra_column=include_extra)
            files.append((file_name, content))
            current += timedelta(days=1)
        return files
