"""Source corporate actions and benchmark observations, separate from stock quotes."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from . import Contract


class CorporateAction(Contract):
    security_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    action_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    action_type: Literal["cash_dividend", "split", "rights", "spinoff", "buyback"]
    action_status: Literal["proposed", "approved", "effected", "cancelled"]
    updates_action_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$")
    announcement_date: date
    ex_date: date | None = None
    effective_date: date | None = None
    payment_date: date | None = None
    payment_date_precision: Literal["date", "year", "period", "unknown"] = "unknown"
    payment_period_start: date | None = None
    payment_period_end: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    cash_per_share: Decimal | None = None
    ratio: Decimal | None = None
    ratio_definition: str | None = None
    share_class: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    record_kind: Literal["source_reported"] = "source_reported"

    @model_validator(mode="before")
    @classmethod
    def explicit_payment_precision(cls, value):
        if (
            isinstance(value, dict)
            and "payment_date_precision" not in value
            and value.get("payment_date") is not None
        ):
            return dict(value, payment_date_precision="date")
        return value

    @model_validator(mode="after")
    def semantics(self):
        if self.payment_date_precision == "date":
            if (
                self.payment_date is None
                or self.payment_period_start is not None
                or self.payment_period_end is not None
            ):
                raise ValueError("Date precision requires an exact payment date and no interval")
        elif self.payment_date_precision == "year":
            start, end = self.payment_period_start, self.payment_period_end
            if (
                self.payment_date is not None
                or start is None
                or end is None
                or start.year != end.year
                or (start.month, start.day) != (1, 1)
                or (end.month, end.day) != (12, 31)
            ):
                raise ValueError(
                    "Year precision requires a complete calendar year and no exact payment date"
                )
        elif self.payment_date_precision == "period":
            if (
                self.payment_date is not None
                or self.payment_period_start is None
                or self.payment_period_end is None
                or self.payment_period_start > self.payment_period_end
            ):
                raise ValueError(
                    "Period precision requires an ordered explicit interval and no exact payment date"
                )
        elif any(
            value is not None
            for value in (self.payment_date, self.payment_period_start, self.payment_period_end)
        ):
            raise ValueError("Unknown payment precision cannot contain a date or interval")

        for value in (self.cash_per_share, self.ratio):
            if value is not None and (not value.is_finite() or value <= 0):
                raise ValueError("Action amounts and ratios must be finite and positive")
        if (self.cash_per_share is None) != (self.currency is None):
            raise ValueError("Cash per share and currency must be supplied together")
        if self.ratio is not None and (
            not self.ratio_definition or not self.ratio_definition.strip()
        ):
            raise ValueError("Action ratios require their explicit numerator/denominator meaning")
        if self.ratio is None and self.ratio_definition is not None:
            raise ValueError("Ratio definition requires an actual source ratio")
        if self.updates_action_id == self.action_id:
            raise ValueError("An action update cannot reference itself")
        if self.action_type == "cash_dividend" and self.cash_per_share is None:
            raise ValueError("Cash dividends require cash per share")
        if self.action_type == "split" and self.ratio is None:
            raise ValueError("Splits require an explicit ratio")
        if self.action_type in {"rights", "spinoff"}:
            if (
                self.ratio is None
                and self.payment_date is None
                and self.payment_date_precision not in {"year", "period"}
            ):
                raise ValueError(
                    "Rights/spinoff require disclosed ratio or actual payment date/interval"
                )
            if self.ratio is None and (
                self.action_status != "effected" or not self.updates_action_id
            ):
                raise ValueError("Payment-only events require effected status and declaration link")
        if self.action_type == "buyback" and self.effective_date is None:
            raise ValueError("Buybacks require their transaction effective date")
        if any(
            not getattr(self, key).strip() for key in ("share_class", "basis", "locator", "excerpt")
        ):
            raise ValueError("Action definitions and evidence cannot be blank")
        return self


class BenchmarkPrice(Contract):
    benchmark_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    trading_date: date
    close: Decimal
    unit: Literal["points"] = "points"
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    index_type: Literal["price_index", "total_return_index"]
    basis: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    record_kind: Literal["source_reported"] = "source_reported"

    @model_validator(mode="after")
    def semantics(self):
        if not self.close.is_finite() or self.close <= 0:
            raise ValueError("Benchmark close must be finite and positive")
        if any(not getattr(self, key).strip() for key in ("basis", "locator", "excerpt")):
            raise ValueError("Benchmark basis and evidence cannot be blank")
        return self
