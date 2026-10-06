import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from io import StringIO
from typing import Optional

import pandas as pd


@dataclass
class ValidationError:
    row: Optional[int]
    column: Optional[str]
    rule: str
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    is_valid: bool
    business_date: Optional[date]
    file_name: str
    row_count: int = 0
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    checksum: str = ""

    def add_error(self, row: Optional[int], column: Optional[str], rule: str, message: str) -> None:
        self.errors.append(ValidationError(row=row, column=column, rule=rule, message=message))
        self.is_valid = False

    def add_warning(self, row: Optional[int], column: Optional[str], rule: str, message: str) -> None:
        self.warnings.append(ValidationError(row=row, column=column, rule=rule, message=message, severity="warning"))

    def to_report(self) -> dict:
        return {
            "file_name": self.file_name,
            "is_valid": self.is_valid,
            "business_date": str(self.business_date) if self.business_date else None,
            "row_count": self.row_count,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "checksum": self.checksum,
            "errors": [
                {"row": e.row, "column": e.column, "rule": e.rule, "message": e.message}
                for e in self.errors
            ],
            "warnings": [
                {"row": w.row, "column": w.column, "rule": w.rule, "message": w.message}
                for w in self.warnings
            ],
        }


FILE_NAME_PATTERN = re.compile(r"^prices_(\d{4}-\d{2}-\d{2})\.csv$")
REQUIRED_COLUMNS = {"date", "symbol", "open", "high", "low", "close", "volume"}


class FileValidator:
    def __init__(self, constituent_symbols: list[str], missing_tolerance: float = 0.1):
        self.constituent_symbols = set(s.upper() for s in constituent_symbols)
        self.missing_tolerance = missing_tolerance

    def validate(self, file_name: str, content: str) -> ValidationResult:
        result = ValidationResult(is_valid=True, business_date=None, file_name=file_name)
        result.checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

        business_date = self._validate_file_name(file_name, result)
        if not business_date:
            return result

        result.business_date = business_date

        df = self._parse_csv(content, result)
        if df is None:
            return result

        result.row_count = len(df)
        self._validate_schema(df, result)
        if not result.is_valid:
            return result

        self._validate_rows(df, business_date, result)
        self._validate_completeness(df, result)
        return result

    def _validate_file_name(self, file_name: str, result: ValidationResult) -> Optional[date]:
        base_name = file_name.split("/")[-1]
        match = FILE_NAME_PATTERN.match(base_name)
        if not match:
            result.add_error(None, None, "file_name", f"File name '{base_name}' does not match pattern 'prices_YYYY-MM-DD.csv'")
            return None
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            result.add_error(None, None, "file_name", f"Invalid date in file name: {match.group(1)}")
            return None

    def _parse_csv(self, content: str, result: ValidationResult) -> Optional[pd.DataFrame]:
        try:
            df = pd.read_csv(StringIO(content))
            df.columns = [c.strip().lower() for c in df.columns]
            return df
        except Exception as e:
            result.add_error(None, None, "parse", f"Failed to parse CSV: {str(e)}")
            return None

    def _validate_schema(self, df: pd.DataFrame, result: ValidationResult) -> None:
        present_columns = set(df.columns)
        missing = REQUIRED_COLUMNS - present_columns
        if missing:
            result.add_error(None, None, "schema", f"Missing required columns: {sorted(missing)}")

    def _validate_rows(self, df: pd.DataFrame, business_date: date, result: ValidationResult) -> None:
        for idx, row in df.iterrows():
            row_num = idx + 2

            try:
                row_date = date.fromisoformat(str(row["date"]).strip())
                if row_date != business_date:
                    result.add_error(row_num, "date", "date_match", f"Row date {row_date} does not match file date {business_date}")
            except (ValueError, TypeError):
                result.add_error(row_num, "date", "date_format", f"Invalid date format: {row.get('date')}")
                continue

            symbol = str(row.get("symbol", "")).strip().upper()
            if not symbol:
                result.add_error(row_num, "symbol", "symbol_empty", "Symbol is empty")

            for price_col in ["open", "high", "low", "close"]:
                try:
                    val = float(row[price_col])
                    if val <= 0:
                        result.add_error(row_num, price_col, "price_positive", f"{price_col} must be > 0, got {val}")
                except (ValueError, TypeError):
                    result.add_error(row_num, price_col, "price_type", f"Invalid {price_col} value: {row.get(price_col)}")

            try:
                high = float(row["high"])
                low = float(row["low"])
                close = float(row["close"])
                if high < low:
                    result.add_error(row_num, "high", "high_low", f"High ({high}) must be >= Low ({low})")
                if close < low or close > high:
                    result.add_error(row_num, "close", "close_range", f"Close ({close}) must be within [{low}, {high}]")
            except (ValueError, TypeError):
                pass

            try:
                volume = int(float(row["volume"]))
                if volume < 0:
                    result.add_error(row_num, "volume", "volume_negative", f"Volume must be >= 0, got {volume}")
            except (ValueError, TypeError):
                result.add_error(row_num, "volume", "volume_type", f"Invalid volume value: {row.get('volume')}")

        if "symbol" in df.columns and "date" in df.columns:
            duplicates = df.groupby(["date", "symbol"]).size()
            dup_entries = duplicates[duplicates > 1]
            if not dup_entries.empty:
                for (dup_date, dup_symbol), count in dup_entries.items():
                    result.add_error(None, "symbol", "duplicate_symbol", f"Duplicate symbol {dup_symbol} on date {dup_date} ({count} entries)")

    def _validate_completeness(self, df: pd.DataFrame, result: ValidationResult) -> None:
        if "symbol" not in df.columns:
            return
        present_symbols = set(df["symbol"].str.strip().str.upper().unique())
        missing_symbols = self.constituent_symbols - present_symbols
        if missing_symbols:
            missing_ratio = len(missing_symbols) / len(self.constituent_symbols) if self.constituent_symbols else 0
            if missing_ratio > self.missing_tolerance:
                result.add_error(
                    None, None, "completeness",
                    f"Missing {len(missing_symbols)}/{len(self.constituent_symbols)} symbols ({missing_ratio:.1%}): {sorted(missing_symbols)[:10]}"
                )
            else:
                result.add_warning(
                    None, None, "completeness",
                    f"Missing {len(missing_symbols)} symbols within tolerance: {sorted(missing_symbols)}"
                )
