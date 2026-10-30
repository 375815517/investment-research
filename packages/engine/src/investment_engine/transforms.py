"""Deterministic unit-scale transformations stored separately from source facts."""

from decimal import Decimal

from investment_domain import DomainError, NormalizeInputsRequest
from investment_repository import fingerprint

from .profiles import assess, field_value

SCALES = {
    "units": Decimal(1),
    "thousands": Decimal(1000),
    "millions": Decimal(1000000),
    "billions": Decimal(1000000000),
}
TRANSFORM_VERSION = "decimal-scale-v1"


def normalize(service, payload):
    request = NormalizeInputsRequest.model_validate(payload)
    profile = request.profile.model_dump(mode="json")
    profile["purpose"] = "quantitative_comparison"
    for group in profile["comparison_groups"]:
        group["normalize_scales"] = True
    with service.repo.read_snapshot():
        assessment = assess(service, profile)
        if assessment["status"] == "blocked":
            return dict(status="blocked", assessment=assessment, artifact_refs=[], records=[])
        records = []
        for key in assessment["audit"]["keys"]:
            if key["status"] != "satisfied":
                continue
            for row in key["rows"]:
                if "source_value" not in row or row["source_value"] is None:
                    raise DomainError("NOT_NUMERIC_INPUT", key["key_id"])
                scale = field_value(row, "scale")
                if scale not in SCALES:
                    raise DomainError("UNSUPPORTED_SCALE", str(scale))
                value = Decimal(str(row["source_value"]))
                if not value.is_finite():
                    raise DomainError("INVALID_NUMBER", key["key_id"])
                output = value * SCALES[scale] / SCALES[request.target_scale]
                records.append(
                    dict(
                        key_id=key["key_id"],
                        record_kind="derived_normalization",
                        metric_id=row.get("metric_id"),
                        unit=field_value(row, "unit"),
                        currency=row.get("currency"),
                        target_scale=request.target_scale,
                        normalized_value=str(output),
                        input=row,
                        input_sha256=fingerprint(row),
                        transform=dict(
                            method=TRANSFORM_VERSION,
                            from_scale=scale,
                            to_scale=request.target_scale,
                            multiplier=str(SCALES[scale] / SCALES[request.target_scale]),
                        ),
                    )
                )
        result = dict(
            protocol_version="1",
            request=request.model_dump(mode="json"),
            transform_version=TRANSFORM_VERSION,
            records=records,
            assessment_status=assessment["status"],
            findings=assessment["findings"],
            artifact_refs=assessment["artifact_refs"],
        )
    transformation_id = "normalization-" + fingerprint(result)[:32]
    path = f"data/outputs/research-records/transformations/{transformation_id}/run.json"
    service.repo.json(path, result)
    return dict(
        status="normalized",
        transformation_id=transformation_id,
        records=records,
        artifact_refs=sorted(set(result["artifact_refs"] + [path])),
        limitations=[
            "Scale conversion does not perform currency conversion or certify economic equivalence"
        ],
        assessment_status=assessment["status"],
    )


def replay(run):
    """Recompute a frozen scale run from its pinned source rows, without writes."""
    if run.get("transform_version") != TRANSFORM_VERSION:
        raise DomainError("TRANSFORM_VERSION_UNSUPPORTED", str(run.get("transform_version")))
    request = NormalizeInputsRequest.model_validate(run["request"])
    values = []
    for record in run["records"]:
        source = record["input"]
        if fingerprint(source) != record["input_sha256"]:
            raise DomainError("TRANSFORM_INPUT_CHANGED", record["key_id"], 4)
        source_scale = field_value(source, "scale")
        if source_scale not in SCALES:
            raise DomainError("UNSUPPORTED_SCALE", str(source_scale))
        expected = (
            Decimal(str(source["source_value"]))
            * SCALES[source_scale]
            / SCALES[request.target_scale]
        )
        if not expected.is_finite() or str(expected) != record["normalized_value"]:
            raise DomainError("TRANSFORM_REPLAY_MISMATCH", record["key_id"], 4)
        if record["target_scale"] != request.target_scale or record["transform"] != dict(
            method=TRANSFORM_VERSION,
            from_scale=source_scale,
            to_scale=request.target_scale,
            multiplier=str(SCALES[source_scale] / SCALES[request.target_scale]),
        ):
            raise DomainError("TRANSFORM_REPLAY_MISMATCH", "Transformation definition changed", 4)
        values.append(dict(key_id=record["key_id"], normalized_value=str(expected)))
    return values
