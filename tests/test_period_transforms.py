"""Period arithmetic cannot infer additivity from a metric's name alone."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from investment_domain import DomainError
from investment_engine.period_transforms import transform_period


def request(method="cumulative_to_quarter"):
    stock = method == "endpoint_average"
    definition = dict(
        metric_id="cash" if stock else "revenue",
        name="Test metric",
        description="Test",
        dataset_id="financial-observations",
        unit="currency",
        measure_kind="stock" if stock else "flow",
        allowed_period_types=["instant"] if stock else ["half_year", "year_to_date"],
        comparability_notes="Same population and accounting basis",
        allow_negative=True,
    )
    base = dict(
        company_id="xiaomi",
        metric_id=definition["metric_id"],
        source_value="100",
        unit="currency",
        currency="CNY",
        scale="millions",
        measure_kind=definition["measure_kind"],
        period_type="instant" if stock else "half_year",
        period_start=None if stock else "2025-01-01",
        period_end="2025-06-30",
        basis="IFRS consolidated",
        accounting_standard="IFRS",
        locator="page:1",
        excerpt="Reported source figure",
    )

    def wrap(observation, version):
        return dict(
            observation=observation,
            source_id="issuer",
            input_version=version,
            document_id="doc-" + version * 64,
            document_sha256=version * 64,
        )

    later = dict(
        base,
        period_end="2025-09-30",
        source_value="160",
        period_type="instant" if stock else "year_to_date",
    )
    return dict(
        method=method, definition=definition, earlier=wrap(base, "a"), later=wrap(later, "b")
    )


def test_cumulative_quarter_and_identity_preserve_versions():
    payload = request()
    result = transform_period(payload)
    assert result["value"] == "60"
    assert (result["period_start"], result["period_end"]) == ("2025-07-01", "2025-09-30")
    assert result["record_kind"] == "derived_period_transform"
    assert result["inputs"][0]["input"]["input_version"] == "a"
    assert result == transform_period(deepcopy(payload))
    payload["later"]["metadata_revision_id"] = "corrected-time-v2"
    assert transform_period(payload)["derived_id"] != result["derived_id"]


def test_endpoint_average_is_not_reported_or_time_weighted():
    result = transform_period(request("endpoint_average"))
    assert result["value"] == "130"
    assert result["measure_kind"] == "period_measure"
    assert "not a time-weighted" in result["limitations"][0]


@pytest.mark.parametrize(
    "field,value",
    [
        ("basis", "different population"),
        ("currency", "HKD"),
        ("scale", "thousands"),
        ("company_id", "tencent"),
        ("scope", "standalone"),
        ("restatement", "restated"),
        ("accounting_standard", "US GAAP"),
    ],
)
def test_mixed_semantics_are_blocked(field, value):
    payload = request()
    payload["later"]["observation"][field] = value
    with pytest.raises(DomainError, match=field):
        transform_period(payload)


@pytest.mark.parametrize(
    "change,code",
    [
        ({"period_start": "2025-04-01"}, "CUMULATIVE_START_MISMATCH"),
        ({"period_end": "2025-12-31"}, "QUARTER_ALIGNMENT_INVALID"),
        ({"period_end": "2025-06-30"}, "PERIOD_ORDER_INVALID"),
        ({"period_end": "2025-09-29"}, "QUARTER_ALIGNMENT_INVALID"),
    ],
)
def test_bad_periods_cannot_be_silently_subtracted(change, code):
    payload = request()
    payload["later"]["observation"].update(change)
    with pytest.raises(DomainError) as exc:
        transform_period(payload)
    assert exc.value.code == code


@pytest.mark.parametrize(
    "metric,unit,kind",
    [
        ("monthly-active-users", "users", "period_measure"),
        ("weighted-average-basic-shares", "shares", "period_measure"),
        ("basic-eps", "currency_per_share", "ratio"),
    ],
)
def test_mau_weighted_average_shares_and_eps_are_not_additive(metric, unit, kind):
    payload = request()
    payload["definition"].update(
        metric_id=metric, unit=unit, measure_kind=kind, allowed_scales=["units"]
    )
    for role in ["earlier", "later"]:
        payload[role]["observation"].update(
            metric_id=metric,
            unit=unit,
            measure_kind=kind,
            scale="units",
            currency="CNY" if unit == "currency_per_share" else None,
        )
    with pytest.raises(DomainError) as exc:
        transform_period(payload)
    assert exc.value.code == "PERIOD_NONADDITIVE"


def test_unreported_and_forged_metric_definition_blocked():
    payload = request()
    payload["later"]["observation"].update(
        source_value=None, value_status="not_disclosed", missing_reason="Not reported"
    )
    with pytest.raises(ValidationError):
        transform_period(payload)
    payload = request()
    payload["definition"]["measure_kind"] = "period_measure"
    with pytest.raises(ValidationError):
        transform_period(payload)


def test_negative_currency_flow_permitted_but_negative_count_blocked():
    payload = request()
    payload["later"]["observation"]["source_value"] = "80"
    assert transform_period(payload)["value"] == "-20"
    payload["definition"].update(unit="vehicles", allow_negative=False)
    for role in ["earlier", "later"]:
        payload[role]["observation"].update(unit="vehicles", currency=None)
    with pytest.raises(DomainError) as exc:
        transform_period(payload)
    assert exc.value.code == "NEGATIVE_DERIVED_COUNT"


def test_average_cannot_consume_flow_or_period_measure():
    payload = request()
    payload["method"] = "endpoint_average"
    with pytest.raises(DomainError) as exc:
        transform_period(payload)
    assert exc.value.code == "PERIOD_NOT_STOCK"


def test_population_dimensions_must_match():
    payload = request()
    payload["definition"]["allowed_dimensions"] = ["population"]
    payload["earlier"]["observation"]["dimensions"] = {"population": "all"}
    payload["later"]["observation"]["dimensions"] = {"population": "domestic"}
    with pytest.raises(DomainError) as exc:
        transform_period(payload)
    assert exc.value.code == "PERIOD_BASIS_MISMATCH"
