"""Versioned financial and operating source observations with explicit dimensions."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import Contract

Unit = Literal[
    "currency",
    "currency_per_share",
    "shares",
    "units",
    "people",
    "users",
    "accounts",
    "subscriptions",
    "devices",
    "vehicles",
    "percent",
    "ratio",
    "multiple",
]
Scale = Literal["units", "thousands", "millions", "billions"]
MeasureKind = Literal["stock", "flow", "ratio", "period_measure"]
PeriodType = Literal["instant", "annual", "half_year", "quarter", "year_to_date", "month"]
Dimension = Literal["segment", "product", "region", "share_class", "population", "channel"]
SCALE_FACTORS = {
    "units": Decimal(1),
    "thousands": Decimal(1000),
    "millions": Decimal(1000000),
    "billions": Decimal(1000000000),
}


class SourceObservation(Contract):
    schema_version: Literal["2"] = "2"
    company_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    metric_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    metric_version: str = Field(default="1", min_length=1)
    source_value: Decimal | None
    value_status: Literal["reported", "not_disclosed", "not_applicable"] = "reported"
    missing_reason: str | None = None
    unit: Unit
    scale: Scale = "units"
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    measure_kind: MeasureKind
    period_type: PeriodType
    period_start: date | None = None
    period_end: date
    scope: Literal["consolidated", "standalone", "segment", "product"] = "consolidated"
    dimensions: dict[Dimension, str] = Field(default_factory=dict)
    basis: str = Field(min_length=1)
    accounting_standard: str = Field(min_length=1)
    adjustment_basis: Literal["reported", "adjusted"] = "reported"
    restatement: Literal["original", "restated", "unknown"] = "original"
    record_kind: Literal["source_reported"] = "source_reported"
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)

    @field_validator("metric_version", "basis", "accounting_standard", "locator", "excerpt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Observation definitions and evidence cannot be blank")
        return value

    @field_validator("dimensions")
    @classmethod
    def dimensions_not_blank(cls, value):
        if any(not item.strip() for item in value.values()):
            raise ValueError("Dimension values cannot be blank")
        return value

    @model_validator(mode="after")
    def semantics(self):
        if self.value_status == "reported":
            if (
                self.source_value is None
                or not self.source_value.is_finite()
                or self.missing_reason
            ):
                raise ValueError("Reported observation requires finite value and no missing reason")
        elif (
            self.source_value is not None
            or not self.missing_reason
            or not self.missing_reason.strip()
        ):
            raise ValueError("Missing observations require null and evidence-backed reason")
        monetary = self.unit in {"currency", "currency_per_share"}
        if monetary != (self.currency is not None):
            raise ValueError("Currency is required only for monetary measurements")
        if (
            self.unit in {"currency_per_share", "percent", "ratio", "multiple"}
            and self.scale != "units"
        ):
            raise ValueError("Per-share, ratio and multiple measurements cannot have count scales")
        if (
            self.unit
            in {
                "shares",
                "units",
                "people",
                "users",
                "accounts",
                "subscriptions",
                "devices",
                "vehicles",
            }
            and self.source_value is not None
            and self.source_value < 0
        ):
            raise ValueError("Physical counts cannot be negative")
        if self.period_type == "instant":
            if self.period_start is not None or self.measure_kind == "flow":
                raise ValueError("Instant observations have no period_start and cannot be flows")
        elif self.period_start is None or self.period_start > self.period_end:
            raise ValueError("Period observations require an ordered explicit period")
        if self.measure_kind == "stock" and self.period_type != "instant":
            raise ValueError("Stocks require an instant; interval statistics use period_measure")
        if self.scope in {"segment", "product"} and self.scope not in self.dimensions:
            raise ValueError("Segment/product scope requires its named dimension")
        return self


class FinancialObservation(SourceObservation):
    """Financial statement measures; old FinancialFact remains separately readable."""


class OperatingObservation(SourceObservation):
    """Reported operating statistics; not inferred indicators or forecasts."""


class MetricDefinition(Contract):
    metric_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    version: str = Field(default="1", min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    dataset_id: Literal["financial-observations", "operating-observations"]
    unit: Unit
    measure_kind: MeasureKind
    allowed_period_types: list[PeriodType] = Field(min_length=1)
    allowed_dimensions: list[Dimension] = Field(default_factory=list)
    required_dimensions: list[Dimension] = Field(default_factory=list)
    allowed_scales: list[Scale] = Field(default=["units", "thousands", "millions", "billions"])
    allow_negative: bool = True
    comparability_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def definition_consistency(self):
        if not set(self.required_dimensions) <= set(self.allowed_dimensions):
            raise ValueError("Required dimensions must be allowed")
        if self.measure_kind == "stock" and self.allowed_period_types != ["instant"]:
            raise ValueError("Stock definitions must declare instant observations")
        if self.unit in {
            "currency_per_share",
            "percent",
            "ratio",
            "multiple",
        } and self.allowed_scales != ["units"]:
            raise ValueError("Ratio/per-share definitions use units scale")
        if not self.allowed_scales:
            raise ValueError("Metric must allow at least one scale")
        return self

    def check_observation(self, observation: SourceObservation) -> None:
        """Validate a source record against a registered semantic definition."""
        if observation.metric_id != self.metric_id or observation.metric_version != self.version:
            raise ValueError("Metric identity/version does not match registered definition")
        if observation.unit != self.unit or observation.measure_kind != self.measure_kind:
            raise ValueError("Observation unit or measure kind differs from registered metric")
        if (
            observation.period_type not in self.allowed_period_types
            or observation.scale not in self.allowed_scales
        ):
            raise ValueError("Observation period or scale differs from registered metric")
        present = set(observation.dimensions)
        if not set(self.required_dimensions) <= present or not present <= set(
            self.allowed_dimensions
        ):
            raise ValueError("Observation dimensions differ from registered metric")
        if (
            not self.allow_negative
            and observation.source_value is not None
            and observation.source_value < 0
        ):
            raise ValueError("Metric does not allow negative values")
