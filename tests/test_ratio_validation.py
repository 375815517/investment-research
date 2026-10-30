"""Prevent mismatched turnover observations being presented as a ratio."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "ratio_validation", Path(__file__).parents[1] / "scripts/verify_short_sale_ratio.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Service:
    def __init__(self, change=None, extra=False):
        base = dict(
            security_id="sample",
            observed_date="2024-01-02",
            share_class="B",
            currency="HKD",
            unit="currency",
            session="full_day",
            value_status="reported",
            document_refs=["same-report"],
        )
        self.rows = [
            dict(base, metric_id="short_sale_turnover", source_value="25"),
            dict(base, metric_id="turnover", source_value="100"),
        ]
        self.rows[1].update(change or {})
        if extra:
            self.rows.append(dict(self.rows[1]))

    def execute(self, operation, payload):
        return dict(rows=self.rows, artifact_refs=["batch"])


def test_matching_report_ratio_is_labelled_derived():
    result = module.calculate(Service(), "sample", "source", "2024-01-02")
    assert result["percent"] == "25.00"
    assert result["record_kind"] == "derived_validation"


@pytest.mark.parametrize(
    "change",
    [
        {"share_class": "A"},
        {"currency": "CNY"},
        {"observed_date": "2024-01-03"},
        {"document_refs": ["different-report"]},
        {"source_value": "0"},
        {"source_value": "20"},
        {"session": "intraday"},
    ],
)
def test_incompatible_or_invalid_denominator_is_rejected(change):
    with pytest.raises(ValueError):
        module.calculate(Service(change), "sample", "source", "2024-01-02")


def test_ambiguous_denominator_is_rejected():
    with pytest.raises(ValueError):
        module.calculate(Service(extra=True), "sample", "source", "2024-01-02")
