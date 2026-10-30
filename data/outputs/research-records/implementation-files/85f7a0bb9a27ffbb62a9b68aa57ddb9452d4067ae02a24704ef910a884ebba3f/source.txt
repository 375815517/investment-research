"""Purpose-specific checks of admitted inputs, not investment quality scores."""

from typing import Literal

from pydantic import model_validator

from .observations import AuditInputsRequest


class AssessInputsRequest(AuditInputsRequest):
    purpose: Literal[
        "source_description", "historical_point_in_time", "quantitative_comparison"
    ] = "source_description"

    @model_validator(mode="after")
    def historical_purpose(self):
        if (
            self.purpose == "historical_point_in_time"
            and self.knowledge_mode == "retrospective_explanation"
        ):
            raise ValueError("Historical purpose requires a cutoff-filtered knowledge mode")
        return self
