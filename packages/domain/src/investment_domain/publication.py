"""Reviewed publication assertions without fabricated timestamp precision."""

from datetime import date as Date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from . import Contract


class PublicationAssertion(Contract):
    precision: Literal["instant", "date", "interval", "unknown"]
    published_at: datetime | None = None
    date: Date | None = None
    timezone: str | None = None
    earliest: datetime | None = None
    latest: datetime | None = None

    @field_validator("published_at", "earliest", "latest")
    @classmethod
    def aware(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Publication timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def consistent_precision(self):
        populated = {
            key
            for key in ("published_at", "date", "timezone", "earliest", "latest")
            if getattr(self, key) is not None
        }
        expected = {
            "instant": {"published_at"},
            "date": {"date", "timezone"},
            "interval": {"earliest", "latest"},
            "unknown": set(),
        }[self.precision]
        if populated != expected:
            raise ValueError("Publication values must match their declared precision")
        if self.timezone:
            try:
                ZoneInfo(self.timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Publication timezone must be a valid IANA zone") from exc
        if self.earliest and self.latest and self.latest < self.earliest:
            raise ValueError("Publication interval is reversed")
        return self


class DocumentMetadataRevisionRequest(Contract):
    document_id: str = Field(min_length=1)
    expected_revision_id: str | None = None
    publication: PublicationAssertion
    evidence_document_id: str = Field(min_length=1)
    supporting_document_ids: list[str] = Field(default_factory=list, max_length=100)
    locator: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    notes: str = ""

    @field_validator("supporting_document_ids")
    @classmethod
    def unique_support(cls, value):
        if any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError("Supporting document IDs must be nonblank and unique")
        return value

    @field_validator("document_id", "evidence_document_id", "locator", "excerpt", "reviewer")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Metadata revision evidence and reviewer cannot be blank")
        return value


DocumentMetadataRevision = DocumentMetadataRevisionRequest
