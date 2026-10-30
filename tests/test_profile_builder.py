"""Declared data requirements must not shrink to the observations already present."""

import importlib.util
import json
from pathlib import Path

import pytest

from investment_domain import DomainError

spec = importlib.util.spec_from_file_location(
    "profile_builder", Path(__file__).parents[1] / "scripts/build_input_profiles.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def profile_workspace(tmp_path):
    metric = tmp_path / "research/metrics/revenue/v1.json"
    metric.parent.mkdir(parents=True)
    original = Path(__file__).parents[1] / "research/metrics/revenue/v1.json"
    metric.write_bytes(original.read_bytes())
    security = tmp_path / "data/inputs/markets/securities/company-hk/v1/security.json"
    security.parent.mkdir(parents=True)
    security.write_text(
        json.dumps({"company_id": "company", "security_id": "company-hk", "user_confirmed": True})
    )
    definition = {
        "version": "1",
        "companies": [
            {
                "company_id": "company",
                "confirmed_security_id": "company-hk",
                "financial_currency": "CNY",
                "accounting_standard": "IFRS",
                "source_id_template": "company-{year}-annual",
                "profiles": [
                    {
                        "name": "annual-core",
                        "years": [2024, 2025],
                        "fields": [{"metric_id": "revenue"}],
                    }
                ],
            }
        ],
    }
    return tmp_path, definition


def test_builder_declares_both_periods_without_any_acquired_rows(profile_workspace):
    root, definition = profile_workspace
    paths = module.build(root, definition)
    value = json.loads((root / paths[0]).read_text())
    assert [key["selectors"]["period_end"] for key in value["expected_keys"]] == [
        "2024-12-31",
        "2025-12-31",
    ]
    assert all(key["required"] for key in value["expected_keys"])
    assert value["expected_keys"][0]["source_id"] == "company-2024-annual"
    assert module.build(root, definition) == paths


def test_builder_rejects_silent_requirement_revision(profile_workspace):
    root, definition = profile_workspace
    module.build(root, definition)
    definition["companies"][0]["profiles"][0]["years"] = [2025]
    with pytest.raises(DomainError, match="v1.json"):
        module.build(root, definition)


def test_builder_requires_confirmed_company_and_supported_period(profile_workspace):
    root, definition = profile_workspace
    definition["companies"][0]["confirmed_security_id"] = "unknown"
    with pytest.raises(ValueError, match="confirmed"):
        module.build(root, definition)
    definition["companies"][0]["confirmed_security_id"] = "company-hk"
    definition["companies"][0]["profiles"][0]["fields"][0]["period_type"] = "quarter"
    with pytest.raises(ValueError, match="explicit"):
        module.build(root, definition)


def test_period_scope_is_explicit_and_can_span_official_sources(profile_workspace):
    root, definition = profile_workspace
    profile = definition["companies"][0]["profiles"][0]
    profile["source_id_template"] = None
    profile["accounting_standard"] = "IAS34"
    profile["fields"] = [
        {
            "metric_id": "revenue",
            "field_id": "q1-revenue",
            "years": [2025],
            "period_type": "quarter",
            "period_start_month_day": "01-01",
            "period_end_month_day": "03-31",
        },
        {
            "metric_id": "revenue",
            "field_id": "q4-revenue",
            "years": [2024],
            "period_type": "quarter",
            "period_start_month_day": "10-01",
            "period_end_month_day": "12-31",
            "accounting_standard": "IFRS",
        },
    ]
    path = module.build(root, definition)[0]
    keys = json.loads((root / path).read_text())["expected_keys"]
    assert [(k["key_id"], k["selectors"]["accounting_standard"]) for k in keys] == [
        ("q4-revenue-2024", "IFRS"),
        ("q1-revenue-2025", "IAS34"),
    ]
    assert all("source_id" not in k and k["max_matches"] == 1 for k in keys)
    assert keys[0]["selectors"]["period_start"] == "2024-10-01"


def test_field_scope_cannot_silently_drop_out_of_profile_years(profile_workspace):
    root, definition = profile_workspace
    definition["companies"][0]["profiles"][0]["fields"][0]["years"] = [2026]
    with pytest.raises(ValueError, match="subset"):
        module.build(root, definition)
