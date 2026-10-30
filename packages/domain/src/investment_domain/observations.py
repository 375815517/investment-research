"""Finite, reviewed source assertions; no calculated factors or inferred sentiment."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator
from . import Contract

Slug = str


class DocumentFact(Contract):
    fact_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    document_kind: Literal[
        "policy", "news_report", "industry_report", "competition_statement", "company_statement"
    ]
    subject_type: Literal["company", "industry", "jurisdiction", "event"]
    subject_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    event_date: date
    effective_from: date | None = None
    effective_to: date | None = None
    assertion_type: Literal["source_assertion"]
    statement: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def dates(self):
        if self.effective_to and (
            not self.effective_from or self.effective_to < self.effective_from
        ):
            raise ValueError("Effective end requires an ordered effective interval")
        if not self.statement.strip() or not self.excerpt.strip():
            raise ValueError("Statement and excerpt cannot be blank")
        return self


class RatioDenominator(Contract):
    definition: str = Field(min_length=1)
    period_start: date
    period_end: date
    market: str = Field(min_length=1)
    share_class: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid(self):
        if self.period_end < self.period_start:
            raise ValueError("Denominator period is reversed")
        if any(
            not getattr(self, name).strip()
            for name in ("definition", "market", "share_class", "document_id", "locator")
        ):
            raise ValueError("Denominator definition and evidence cannot be blank")
        return self


class MarketObservation(Contract):
    security_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    observed_at: datetime | None = None
    observed_date: date | None = None
    metric_id: Literal[
        "issued_shares",
        "free_float_shares",
        "free_float_ratio",
        "market_cap",
        "pe_ttm",
        "pe_static",
        "pe_provider",
        "turnover",
        "volume",
        "short_sale_turnover",
        "short_sale_volume",
        "short_sale_ratio",
        "reported_short_position",
        "reported_short_position_value",
        "reported_short_position_ratio",
        "long_position_ratio",
    ]
    source_value: Decimal | None
    value_status: Literal["reported", "not_disclosed"]
    missing_reason: str | None = None
    unit: Literal["percent", "ratio", "shares", "currency", "multiple", "provider-native"]
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    basis: str = Field(min_length=1)
    session: Literal["full_day", "intraday", "point_in_time", "reporting_period"]
    share_class: str = Field(min_length=1)
    denominator_ref: RatioDenominator | None = None
    record_kind: Literal["source_reported"]
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc) if value else None

    @model_validator(mode="after")
    def semantics(self):
        if (self.observed_at is None) == (self.observed_date is None):
            raise ValueError(
                "Provide exactly one source observation date or timezone-aware instant"
            )
        if any(
            not getattr(self, field).strip()
            for field in ("basis", "share_class", "locator", "excerpt")
        ):
            raise ValueError("Market basis and evidence cannot be blank")
        if self.value_status == "not_disclosed":
            if (
                self.source_value is not None
                or not self.missing_reason
                or not self.missing_reason.strip()
            ):
                raise ValueError("Missing values require null and an evidence-backed reason")
        elif (
            self.source_value is None
            or not self.source_value.is_finite()
            or self.missing_reason is not None
        ):
            raise ValueError("Reported values require finite source value and no missing reason")
        ratios = {
            "free_float_ratio",
            "short_sale_ratio",
            "reported_short_position_ratio",
            "long_position_ratio",
        }
        amounts = {"market_cap", "turnover", "short_sale_turnover", "reported_short_position_value"}
        multiples = {"pe_ttm", "pe_static", "pe_provider"}
        if self.metric_id in ratios:
            if self.unit not in ("ratio", "percent") or (
                self.source_value is not None and self.denominator_ref is None
            ):
                raise ValueError(
                    "Reported ratios require ratio/percent units and denominator evidence"
                )
            if self.source_value is not None and not 0 <= self.source_value <= (
                100 if self.unit == "percent" else 1
            ):
                raise ValueError("Ratio is outside its declared unit range")
        elif self.metric_id in amounts:
            if self.unit != "currency" or self.currency is None:
                raise ValueError("Monetary observations require currency units and currency code")
        elif self.metric_id in multiples:
            if self.unit != "multiple":
                raise ValueError("PE requires multiple units")
        elif self.unit != "shares" and not (
            self.metric_id == "volume" and self.unit == "provider-native"
        ):
            raise ValueError(
                "Share counts require shares; only volume permits explicit native units"
            )
        if (
            self.metric_id not in multiples
            and self.source_value is not None
            and self.source_value < 0
        ):
            raise ValueError("Counts, amounts and ratios cannot be negative")
        if self.metric_id not in amounts and self.currency is not None:
            raise ValueError("Non-monetary values must not claim a currency dimension")
        if self.metric_id not in ratios and self.denominator_ref is not None:
            raise ValueError("Only ratio observations use denominator_ref")
        return self


class InputRequirement(Contract):
    dataset_id: Literal["daily-prices", "financial-facts", "document-facts", "market-observations"]
    subject_id: str
    start: date
    end: date
    source_id: str | None = None
    metric_id: str | None = None
    document_kind: str | None = None
    minimum_records: int = Field(default=1, ge=1, le=100000)
    price_basis: Literal["unadjusted", "provider-native"] = "unadjusted"

    @model_validator(mode="after")
    def interval(self):
        if self.end < self.start:
            raise ValueError("Requirement dates must be ordered")
        return self


class AuditInputsRequest(Contract):
    requirements: list[InputRequirement] = Field(min_length=1, max_length=100)
    knowledge_mode: Literal[
        "retrospective_explanation", "historical_reconstruction", "live_observed"
    ] = "retrospective_explanation"
    information_cutoff: datetime | None = None

    @field_validator("information_cutoff")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("information_cutoff requires timezone")
        return value

    @model_validator(mode="after")
    def cutoff(self):
        if self.knowledge_mode != "retrospective_explanation" and self.information_cutoff is None:
            raise ValueError("Historical audit requires information_cutoff")
        return self
