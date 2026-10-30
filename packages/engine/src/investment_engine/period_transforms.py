"""Pure, versioned period arithmetic. No source writes or CLI registration."""

from calendar import monthrange
from datetime import timedelta
from decimal import Decimal

from investment_domain import DomainError
from investment_domain.period_transforms import PeriodTransformRequest
from investment_repository import fingerprint

VERSION = "period-arithmetic-v1"
COMPATIBILITY_FIELDS = (
    "company_id",
    "metric_id",
    "metric_version",
    "unit",
    "scale",
    "currency",
    "measure_kind",
    "scope",
    "dimensions",
    "basis",
    "accounting_standard",
    "adjustment_basis",
    "restatement",
)


def transform_period(payload):
    """Use a caller-resolved metric definition and preserve both input versions."""
    request = PeriodTransformRequest.model_validate(payload)
    earlier, later = request.earlier.observation, request.later.observation
    for field in COMPATIBILITY_FIELDS:
        if getattr(earlier, field) != getattr(later, field):
            raise DomainError("PERIOD_BASIS_MISMATCH", field)
    if earlier.period_end >= later.period_end:
        raise DomainError("PERIOD_ORDER_INVALID", "Two distinct increasing endpoints required")
    if earlier.restatement == "unknown":
        raise DomainError("PERIOD_REVISION_UNKNOWN", "Restatement comparability is unknown")
    if earlier.unit in {"currency_per_share", "percent", "ratio", "multiple"}:
        raise DomainError("PERIOD_NONADDITIVE", "Per-share and ratio values cannot be transformed")
    assert earlier.source_value is not None and later.source_value is not None
    if request.method == "cumulative_to_quarter":
        if earlier.measure_kind != "flow":
            raise DomainError(
                "PERIOD_NONADDITIVE", "Only cumulative additive flows can be differenced"
            )
        if earlier.period_start != later.period_start or earlier.period_start is None:
            raise DomainError(
                "CUMULATIVE_START_MISMATCH", "Cumulative flows require the same start"
            )
        if earlier.period_start.day != 1:
            raise DomainError(
                "QUARTER_ALIGNMENT_INVALID", "Cumulative interval must start on month boundary"
            )
        start = earlier.period_end + timedelta(days=1)
        months = (
            (later.period_end.year - start.year) * 12 + later.period_end.month - start.month + 1
        )
        if (
            start.day != 1
            or months != 3
            or later.period_end.day != monthrange(later.period_end.year, later.period_end.month)[1]
        ):
            raise DomainError(
                "QUARTER_ALIGNMENT_INVALID", "Difference must cover three complete months"
            )
        value = later.source_value - earlier.source_value
        if value < 0 and (
            not request.definition.allow_negative
            or earlier.unit
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
        ):
            raise DomainError(
                "NEGATIVE_DERIVED_COUNT", "Difference violates metric nonnegative rule"
            )
        kind, period_type = "flow", "quarter"
        limitation = (
            "Difference of two comparable cumulative reports; not a separately reported quarter"
        )
    else:
        if (
            earlier.measure_kind != "stock"
            or earlier.period_type != "instant"
            or later.period_type != "instant"
        ):
            raise DomainError("PERIOD_NOT_STOCK", "Endpoint average requires two instant stocks")
        start = earlier.period_end
        value = (earlier.source_value + later.source_value) / Decimal(2)
        kind, period_type = "period_measure", "endpoint_interval"
        limitation = (
            "Arithmetic mean of two endpoints only; not a time-weighted or reported period average"
        )
    body = dict(
        record_kind="derived_period_transform",
        transform_version=VERSION,
        method=request.method,
        company_id=earlier.company_id,
        source_metric_id=earlier.metric_id,
        source_metric_version=earlier.metric_version,
        measure_kind=kind,
        period_type=period_type,
        period_start=start.isoformat(),
        period_end=later.period_end.isoformat(),
        value=str(value),
        unit=earlier.unit,
        scale=earlier.scale,
        currency=earlier.currency,
        scope=earlier.scope,
        dimensions=earlier.dimensions,
        basis=earlier.basis,
        definition=request.definition.model_dump(mode="json"),
        definition_sha256=fingerprint(request.definition.model_dump(mode="json")),
        inputs=[
            dict(
                role=role,
                input=item.model_dump(mode="json"),
                input_sha256=fingerprint(item.model_dump(mode="json")),
            )
            for role, item in [("earlier", request.earlier), ("later", request.later)]
        ],
        limitations=[
            limitation,
            "Caller must resolve and validate source evidence and registered definition; this pure function does not fetch or authenticate documents",
        ],
    )
    return dict(derived_id="period-" + fingerprint(body), **body)
