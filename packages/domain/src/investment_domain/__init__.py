"""Host-independent data contracts. No filesystem, Git or network dependencies."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DomainError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 2):
        self.code, self.message, self.exit_code = code, message, exit_code
        super().__init__(message)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Contract):
    document_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: str = Field(min_length=1)


class DailyPrice(Contract):
    security_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    volume_unit: Literal["shares", "provider-native"]
    price_basis: Literal["unadjusted", "provider-native"]
    session: Literal["regular-final"]

    @model_validator(mode="after")
    def market_constraints(self):
        values = [self.open, self.high, self.low, self.close, self.volume]
        if any(not value.is_finite() for value in values):
            raise ValueError("Price and volume must be finite")
        if min(values[:4]) <= 0 or self.volume < 0:
            raise ValueError("Prices must be positive and volume non-negative")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("OHLC ordering is invalid")
        return self


class FinancialFact(Contract):
    company_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    metric_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    period_start: date
    period_end: date
    source_value: Decimal
    source_unit: Literal["units", "thousands", "millions", "billions"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    scope: Literal["consolidated", "standalone"]
    record_kind: Literal["reported_actual"]
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    @model_validator(mode="after")
    def financial_constraints(self):
        if self.period_start > self.period_end or not self.source_value.is_finite():
            raise ValueError("Invalid financial period or value")
        return self


class ImportRequest(Contract):
    path: str
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    published_at: datetime | None = None
    title: str = "Imported evidence"
    origin_url: str | None = None
    collection_context: dict = Field(default_factory=dict)

    @field_validator("published_at")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("published_at must include a timezone")
        return value


class Issue(Contract):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    record_index: int | None = None
    retryable: bool = False


class Response(Contract):
    protocol_version: str = "1"
    operation_id: str
    status: str
    summary: str
    artifact_refs: list[str] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


SCHEMAS: dict[str, type[BaseModel]] = {
    "Evidence": Evidence,
    "DailyPrice": DailyPrice,
    "FinancialFact": FinancialFact,
    "ImportRequest": ImportRequest,
    "Issue": Issue,
    "Response": Response,
}

from .coverage import (  # noqa: E402
    AcquisitionRequest,
    CoverageRequest,
    EnsureRequest,
    ExpectationItem,
    ExpectationSet,
)

SCHEMAS.update(
    {
        "AcquisitionRequest": AcquisitionRequest,
        "CoverageRequest": CoverageRequest,
        "EnsureRequest": EnsureRequest,
        "ExpectationItem": ExpectationItem,
        "ExpectationSet": ExpectationSet,
    }
)
