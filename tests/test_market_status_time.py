"""A closure assertion cannot make its later supporting evidence historically visible."""

from datetime import datetime, timezone

import pytest

from investment_engine.market_status import visible_closures
from investment_repository import Repository
from test_core import PRICE, admit, candidate


def closure(repo, document_id, observed="2024-01-03T00:00:00Z"):
    repo.json(
        "data/inputs/markets/trading-status/demo-xiaomi/2024/confirmed/status.json",
        dict(
            record_id="demo-closure",
            security_id="demo-xiaomi",
            trading_date="2024-01-02",
            market_status="closed",
            reason="Synthetic closure evidence",
            evidence_document_ids=[document_id],
            published_at="2024-01-03T00:00:00Z",
            observed_at=observed,
            registered_at=observed,
        ),
    )


@pytest.mark.parametrize("published", [None, "2024-02-01T00:00:00Z"])
def test_future_or_unknown_closure_evidence_cannot_remove_historical_price(tmp_path, published):
    service, _, batch = candidate(tmp_path, [dict(PRICE, volume="0")])
    admit(service, batch)
    path = tmp_path / "notice.txt"
    path.write_text("Source closure notice, distinct from price observations")
    notice = service.execute(
        "import", dict(path=str(path), source_id="demo-exchange", published_at=published)
    )
    closure(service.repo, notice["document_id"])
    result = service.execute(
        "coverage",
        dict(
            dataset_id="daily-prices",
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-04T00:00:00Z",
        ),
    )
    assert result["record_count"] == 1
    assert service.execute("coverage", {})["record_count"] == 0


def test_live_closure_requires_evidence_observed_by_cutoff(tmp_path):
    repo = Repository(tmp_path)
    doc, _, _ = repo.import_bytes(
        b"Closure announcement", "demo-exchange", ".txt", "2024-01-03T00:00:00Z", "Notice"
    )
    closure(repo, doc["document_id"])
    cutoff = datetime(2024, 1, 4, tzinfo=timezone.utc)
    # The closure itself claims an earlier observation, but its archived evidence was
    # only collected now. Historical reconstruction and live availability differ.
    assert visible_closures(repo, "historical_reconstruction", cutoff)
    assert not visible_closures(repo, "live_observed", cutoff)
    assert visible_closures(repo, "live_observed", datetime(2099, 1, 1, tzinfo=timezone.utc))


def test_date_precision_closure_uses_evidence_bound_and_live_registration(tmp_path):
    from investment_engine import Service

    service = Service(tmp_path)
    notice = tmp_path / "closure-date.txt"
    notice.write_text("Exchange announced full-day closure on 2024-01-02")
    imported = service.execute("import", dict(path=str(notice), source_id="demo-exchange"))
    identifier = imported["document_id"]
    service.repo.json(
        "data/inputs/markets/trading-status/demo-xiaomi/2024/confirmed/status.json",
        dict(
            record_id="date-only-closure",
            security_id="demo-xiaomi",
            trading_date="2024-01-02",
            market_status="closed",
            reason="Official whole-day notice; exact publication instant unknown",
            evidence_document_ids=[identifier],
            published_at=None,
            observed_at="2024-01-03T00:00:00Z",
            registered_at="2024-01-03T00:00:00Z",
        ),
    )
    after = datetime.fromisoformat("2024-01-02T16:00:00+00:00")
    # A null record timestamp alone cannot establish historical availability.
    assert not visible_closures(service.repo, "historical_reconstruction", after)
    service.execute(
        "revise_metadata",
        dict(
            document_id=identifier,
            publication=dict(precision="date", date="2024-01-02", timezone="Asia/Hong_Kong"),
            evidence_document_id=identifier,
            locator="text:line:1",
            excerpt=notice.read_text(),
            reviewer="test-reviewer",
        ),
    )
    before = datetime.fromisoformat("2024-01-02T15:59:59+00:00")
    assert not visible_closures(service.repo, "historical_reconstruction", before)
    assert visible_closures(service.repo, "historical_reconstruction", after)
    assert not visible_closures(service.repo, "live_observed", after)
    assert visible_closures(
        service.repo, "live_observed", datetime(2099, 1, 1, tzinfo=timezone.utc)
    )


def test_null_closure_time_requires_every_supporting_document_available(tmp_path):
    repo = Repository(tmp_path)
    early, _, _ = repo.import_bytes(
        b"Early notice", "demo-exchange", ".txt", "2024-01-02T00:00:00Z", "Early"
    )
    unknown, _, _ = repo.import_bytes(b"Unknown notice", "demo-exchange", ".txt", None, "Unknown")
    repo.json(
        "data/inputs/markets/trading-status/demo-xiaomi/2024/confirmed/status.json",
        dict(
            record_id="multi-evidence-closure",
            security_id="demo-xiaomi",
            trading_date="2024-01-02",
            market_status="closed",
            reason="Both documents must be visible",
            evidence_document_ids=[early["document_id"], unknown["document_id"]],
            published_at=None,
            observed_at="2024-01-03T00:00:00Z",
            registered_at="2024-01-03T00:00:00Z",
        ),
    )
    assert not visible_closures(
        repo, "historical_reconstruction", datetime(2024, 1, 4, tzinfo=timezone.utc)
    )
