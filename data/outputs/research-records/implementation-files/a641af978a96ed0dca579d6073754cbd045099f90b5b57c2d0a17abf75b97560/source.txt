"""Evidence-backed expectations and bounded acquisition requests."""

from datetime import date as Date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import Contract


class ExpectationItem(Contract):
    date: Date
    expected: bool
    due_at: datetime
    reason: str = Field(min_length=1)
    metric_ids: list[str] = Field(default_factory=list)
    period_start: Date | None = None
    scope: Literal["consolidated", "standalone"] | None = None
    currency: str | None = None
    report_document_id: str | None = None

    @field_validator("due_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("due_at must include timezone")
        return value


class ExpectationSet(Contract):
    expectation_id: str
    dataset_id: Literal["daily-prices", "financial-facts"]
    subject_id: str
    start: Date
    end: Date
    published_at: datetime
    observed_at: datetime
    registered_at: datetime
    evidence_document_ids: list[str] = Field(min_length=1)
    items: list[ExpectationItem]

    @field_validator("published_at", "observed_at", "registered_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Expectation timestamps must include timezone")
        return value

    @model_validator(mode="after")
    def consistency(self):
        if self.end < self.start:
            raise ValueError("Reversed expectation interval")
        keys = [(x.date, x.period_start, x.scope, x.currency) for x in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate expectation keys")
        for item in self.items:
            if not self.start <= item.date <= self.end:
                raise ValueError("Expectation outside declared interval")
            if self.dataset_id == "financial-facts" and item.expected:
                if (
                    not item.metric_ids
                    or not item.period_start
                    or not item.scope
                    or not item.currency
                ):
                    raise ValueError(
                        "Financial expectation requires period, scope, currency and metrics"
                    )
                if item.period_start > item.date:
                    raise ValueError("Reversed financial period")
        return self


class CoverageRequest(Contract):
    dataset_id: Literal["daily-prices", "financial-facts"]
    subject_id: str
    start: Date
    end: Date
    expectation_path: str
    source_id: str | None = None
    price_basis: Literal["unadjusted", "provider-native"] = "unadjusted"
    knowledge_mode: Literal[
        "retrospective_explanation", "historical_reconstruction", "live_observed"
    ] = "retrospective_explanation"
    information_cutoff: datetime | None = None
    as_of: datetime | None = None

    @field_validator("information_cutoff", "as_of")
    @classmethod
    def aware(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Timestamp must include timezone")
        return value

    @model_validator(mode="after")
    def consistency(self):
        if self.end < self.start or (self.end - self.start).days > 3660:
            raise ValueError("Coverage interval must be ordered and at most 3661 days")
        if self.knowledge_mode != "retrospective_explanation" and not self.information_cutoff:
            raise ValueError("Historical queries require information_cutoff")
        return self


class AcquisitionRequest(Contract):
    source_id: str
    parameters: dict = Field(default_factory=dict)


class EnsureRequest(CoverageRequest):
    acquisition: AcquisitionRequest | None = None
