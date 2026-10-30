"""Contracts for deterministic period transforms; not application operations."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import Contract
from .measurements import MetricDefinition, SourceObservation


class VersionedPeriodInput(Contract):
    observation: SourceObservation
    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    input_version: str = Field(min_length=1)
    document_id: str = Field(pattern=r"^doc-[a-f0-9]{64}$")
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata_revision_id: str = Field(default="original", min_length=1)

    @field_validator("input_version", "metadata_revision_id")
    @classmethod
    def explicit_version(cls, value):
        if not value.strip():
            raise ValueError("Input and metadata versions must be explicit")
        return value


class PeriodTransformRequest(Contract):
    method: Literal["cumulative_to_quarter", "endpoint_average"]
    definition: MetricDefinition
    earlier: VersionedPeriodInput
    later: VersionedPeriodInput

    @model_validator(mode="after")
    def registered_semantics(self):
        # The caller resolves this definition from its versioned metric registry.
        for item in (self.earlier, self.later):
            self.definition.check_observation(item.observation)
            if item.observation.value_status != "reported":
                raise ValueError("Period transforms require two reported numeric inputs")
        return self
