"""Semantic boundaries for reusable source observations and exact input profiles."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_domain import (
    BenchmarkPrice,
    ComparisonGroup,
    CorporateAction,
    DocumentMetadataRevisionRequest,
    ExpectedKey,
    FinancialFact,
    FinancialObservation,
    InputRequirementProfile,
    MetricDefinition,
    OperatingObservation,
    PublicationAssertion,
    SCHEMAS,
)


def observation(**changes):
    value = dict(
        company_id="sample",
        metric_id="revenue",
        source_value="1000",
        unit="currency",
        scale="thousands",
        currency="CNY",
        measure_kind="flow",
        period_type="annual",
        period_start="2024-01-01",
        period_end="2024-12-31",
        scope="consolidated",
        dimensions={},
        basis="IFRS consolidated revenue",
        accounting_standard="IFRS",
        locator="pdf:page:10",
        excerpt="Revenue 1,000",
    )
    value.update(changes)
    return value


def exact_key(**changes):
    value = dict(
        key_id="revenue-2024",
        dataset_id="financial-observations",
        subject_id="sample",
        source_id="issuer",
        selectors=dict(
            metric_id="revenue",
            period_start="2024-01-01",
            period_end="2024-12-31",
            period_type="annual",
            measure_kind="flow",
            scope="consolidated",
            unit="currency",
            currency="CNY",
            dimensions={},
        ),
    )
    value.update(changes)
    return value


def test_revenue_stock_eps_and_operating_units_are_separate():
    assert FinancialObservation.model_validate(observation()).scale == "thousands"
    stock = FinancialObservation.model_validate(
        observation(
            metric_id="cash-and-cash-equivalents",
            measure_kind="stock",
            period_type="instant",
            period_start=None,
        )
    )
    assert stock.period_start is None
    eps = FinancialObservation.model_validate(
        observation(
            metric_id="basic-eps",
            measure_kind="ratio",
            unit="currency_per_share",
            scale="units",
        )
    )
    assert eps.currency == "CNY"
    users = OperatingObservation.model_validate(
        observation(
            metric_id="monthly-active-users",
            measure_kind="period_measure",
            unit="users",
            currency=None,
            period_type="month",
            period_start="2024-12-01",
        )
    )
    assert users.currency is None


@pytest.mark.parametrize(
    "change",
    [
        {"unit": "users"},
        {"currency": None},
        {"source_value": "NaN"},
        {"unit": "currency_per_share"},
        {"measure_kind": "stock"},
        {"period_start": "2025-01-01"},
        {"period_type": "instant"},
        {"scope": "segment"},
        {"dimensions": {"segment": " "}},
        {"value_status": "not_disclosed"},
        {"source_value": None},
        {"basis": " "},
        {"record_kind": "ai_inference"},
    ],
)
def test_invalid_financial_semantics_are_rejected(change):
    with pytest.raises(ValidationError):
        FinancialObservation.model_validate(observation(**change))


def test_missing_value_is_neither_zero_nor_unexplained():
    record = FinancialObservation.model_validate(
        observation(
            source_value=None,
            value_status="not_disclosed",
            missing_reason="Source explicitly omits amount",
        )
    )
    assert record.source_value is None
    with pytest.raises(ValidationError):
        FinancialObservation.model_validate(
            observation(source_value=None, value_status="not_disclosed")
        )


def test_metric_dictionary_validates_value_semantics():
    root = Path(__file__).parents[1]
    definition = MetricDefinition.model_validate_json(
        (root / "research/metrics/revenue/v1.json").read_text()
    )
    definition.check_observation(FinancialObservation.model_validate(observation()))
    with pytest.raises(ValueError, match="unit or measure"):
        definition.check_observation(
            FinancialObservation.model_validate(
                observation(
                    unit="users",
                    currency=None,
                )
            )
        )
    with pytest.raises(ValueError, match="identity/version"):
        definition.check_observation(
            FinancialObservation.model_validate(observation(metric_version="2"))
        )
    for path in (root / "research/metrics").glob("*/v*.json"):
        MetricDefinition.model_validate(json.loads(path.read_text()))


def test_exact_key_requires_period_and_business_dimensions():
    ExpectedKey.model_validate(exact_key())
    for missing in ("period_start", "period_end", "currency", "dimensions", "scope"):
        item = exact_key()
        item["selectors"].pop(missing)
        with pytest.raises(ValidationError):
            ExpectedKey.model_validate(item)


def test_profile_disallows_duplicate_keys_and_dangling_groups():
    first = exact_key()
    second = exact_key(key_id="another")
    InputRequirementProfile.model_validate(
        dict(
            profile_id="example",
            expected_keys=[first, second],
            comparison_groups=[dict(group_id="group", key_ids=["revenue-2024", "another"])],
        )
    )
    with pytest.raises(ValidationError, match="unique"):
        InputRequirementProfile.model_validate(
            dict(profile_id="example", expected_keys=[first, first])
        )
    with pytest.raises(ValidationError, match="undefined"):
        InputRequirementProfile.model_validate(
            dict(
                profile_id="example",
                expected_keys=[first],
                comparison_groups=[dict(group_id="group", key_ids=["revenue-2024", "absent"])],
            )
        )
    with pytest.raises(ValidationError):
        ComparisonGroup(group_id="group", key_ids=["first", "second"], join_on=[])


@pytest.mark.parametrize(
    "publication",
    [
        {"precision": "date", "date": "2024-03-01", "timezone": "Asia/Hong_Kong"},
        {"precision": "instant", "published_at": "2024-03-01T12:00:00+08:00"},
        {
            "precision": "interval",
            "earliest": "2024-03-01T00:00:00Z",
            "latest": "2024-03-02T00:00:00Z",
        },
        {"precision": "unknown"},
    ],
)
def test_publication_precision_preserved(publication):
    value = PublicationAssertion.model_validate(publication)
    assert value.precision == publication["precision"]


@pytest.mark.parametrize(
    "publication",
    [
        {"precision": "date", "date": "2024-03-01"},
        {"precision": "date", "date": "2024-03-01", "timezone": "fiction/not-a-zone"},
        {"precision": "instant", "published_at": "2024-03-01T12:00:00"},
        {"precision": "unknown", "published_at": "2024-03-01T12:00:00Z"},
        {
            "precision": "interval",
            "earliest": "2024-03-02T00:00:00Z",
            "latest": "2024-03-01T00:00:00Z",
        },
    ],
)
def test_publication_precision_cannot_be_invented(publication):
    with pytest.raises(ValidationError):
        PublicationAssertion.model_validate(publication)


def test_metadata_revision_requires_evidence_and_reviewer():
    with pytest.raises(ValidationError):
        DocumentMetadataRevisionRequest(
            document_id="doc",
            publication={"precision": "unknown"},
            evidence_document_id="evidence",
            locator="page1",
            excerpt="time",
            reviewer=" ",
        )


def test_old_financial_fact_still_readable():
    old = dict(
        company_id="sample",
        metric_id="revenue",
        period_start="2024-01-01",
        period_end="2024-12-31",
        source_value="1000",
        source_unit="thousands",
        currency="CNY",
        scope="consolidated",
        record_kind="reported_actual",
        locator="page1",
        excerpt="revenue",
    )
    assert FinancialFact.model_validate(old).record_kind == "reported_actual"
    assert SCHEMAS["FinancialObservation"] is FinancialObservation


def test_benchmark_is_points_and_not_stock_quote():
    benchmark = dict(
        benchmark_id="hsi",
        trading_date="2024-01-02",
        close="16000",
        index_type="price_index",
        basis="official close",
        locator="table:hsi",
        excerpt="16000",
    )
    assert BenchmarkPrice.model_validate(benchmark).unit == "points"
    with pytest.raises(ValidationError):
        BenchmarkPrice.model_validate(dict(benchmark, unit="HKD"))


def test_corporate_action_requires_usable_terms():
    action = dict(
        security_id="sample",
        action_id="dividend-2024",
        action_type="cash_dividend",
        action_status="proposed",
        announcement_date="2024-03-01",
        ex_date="2024-05-01",
        currency="HKD",
        cash_per_share="1",
        share_class="B",
        basis="cash per B share",
        locator="page1",
        excerpt="HKD1",
    )
    assert CorporateAction.model_validate(action).action_status == "proposed"
    with pytest.raises(ValidationError):
        CorporateAction.model_validate({k: v for k, v in action.items() if k != "action_status"})
    assert CorporateAction.model_validate(dict(action, ex_date=None)).ex_date is None
    with pytest.raises(ValidationError):
        CorporateAction.model_validate(dict(action, cash_per_share=None))
    with pytest.raises(ValidationError):
        CorporateAction.model_validate(dict(action, ratio="2"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("period_end", "2024-02-30"),
        ("period_start", "tomorrow"),
        ("period_end", "20241231"),
        ("period_start", "2025-01-01"),
    ],
)
def test_exact_key_dates_are_valid_iso_and_ordered(field, value):
    key = exact_key()
    key["selectors"][field] = value
    with pytest.raises(ValidationError):
        ExpectedKey.model_validate(key)


def test_observed_instant_selector_requires_timezone():
    key = dict(
        key_id="market",
        dataset_id="market-observations",
        subject_id="sample",
        selectors=dict(
            metric_id="volume",
            session="full_day",
            share_class="B",
            unit="shares",
            observed_at="2024-01-01T12:00:00",
        ),
    )
    with pytest.raises(ValidationError):
        ExpectedKey.model_validate(key)


def test_corporate_requirement_requires_explicit_status():
    key = dict(
        key_id="action",
        dataset_id="corporate-actions",
        subject_id="sample",
        selectors={"action_id": "dividend-2024", "action_type": "cash_dividend"},
    )
    with pytest.raises(ValidationError):
        ExpectedKey.model_validate(key)
    key["selectors"]["action_status"] = "effected"
    assert ExpectedKey.model_validate(key).selectors["action_status"] == "effected"


def test_payment_event_can_preserve_unknown_ex_date_and_ratio():
    payload = dict(
        security_id="sample",
        action_id="payment",
        action_type="spinoff",
        action_status="effected",
        updates_action_id="declaration",
        announcement_date="2024-02-01",
        payment_date="2024-02-01",
        share_class="ordinary",
        basis="Payment confirmed; terms in declaration",
        locator="page1",
        excerpt="Paid",
    )
    assert CorporateAction.model_validate(payload).ex_date is None
    for update in [
        dict(updates_action_id="payment"),
        dict(updates_action_id=None),
        dict(payment_date=None),
        dict(action_status="proposed"),
    ]:
        with pytest.raises(ValidationError):
            CorporateAction.model_validate(dict(payload, **update))
