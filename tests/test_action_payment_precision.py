import pytest
from pydantic import ValidationError
from investment_domain import CorporateAction


def action(**changes):
    row = dict(
        security_id="demo",
        action_id="cash",
        action_type="cash_dividend",
        action_status="effected",
        announcement_date="2025-04-01",
        currency="HKD",
        cash_per_share="1",
        share_class="ordinary",
        basis="Source confirms paid during 2024",
        locator="pdf:page:1",
        excerpt="Paid during 2024",
    )
    row.update(changes)
    return CorporateAction.model_validate(row)


def test_year_payment_does_not_invent_exact_date():
    value = action(
        payment_date_precision="year",
        payment_period_start="2024-01-01",
        payment_period_end="2024-12-31",
    )
    assert value.payment_date is None
    assert value.payment_date_precision == "year"
    assert action(payment_date="2024-05-01").payment_date_precision == "date"
    assert action().payment_date_precision == "unknown"


@pytest.mark.parametrize(
    "changes",
    [
        dict(
            payment_date_precision="year",
            payment_period_start="2024-01-02",
            payment_period_end="2024-12-31",
        ),
        dict(
            payment_date_precision="year",
            payment_period_start="2023-01-01",
            payment_period_end="2024-12-31",
        ),
        dict(
            payment_date_precision="year",
            payment_period_start="2024-01-01",
            payment_period_end="2024-12-31",
            payment_date="2024-12-31",
        ),
        dict(payment_date_precision="unknown", payment_date="2024-12-31"),
        dict(payment_date_precision="date"),
    ],
)
def test_payment_precision_rejects_contradictions(changes):
    with pytest.raises(ValidationError):
        action(**changes)


def test_interim_report_preserves_half_year_payment_interval():
    value = action(
        payment_date_precision="period",
        payment_period_start="2026-01-01",
        payment_period_end="2026-06-30",
    )
    assert value.payment_date is None
    with pytest.raises(ValidationError):
        action(
            payment_date_precision="period",
            payment_period_start="2026-06-30",
            payment_period_end="2026-01-01",
        )


def test_effected_distribution_accepts_evidenced_month_only_with_declaration():
    row = dict(
        action_type="spinoff",
        cash_per_share=None,
        currency=None,
        action_status="effected",
        updates_action_id="declared",
        payment_date_precision="period",
        payment_period_start="2019-02-01",
        payment_period_end="2019-02-28",
    )
    assert action(**row).ratio is None
    for changes in [
        dict(updates_action_id=None),
        dict(action_status="approved"),
        dict(payment_period_end=None),
        dict(payment_date_precision="unknown", payment_period_start=None, payment_period_end=None),
    ]:
        with pytest.raises(ValidationError):
            action(**dict(row, **changes))
