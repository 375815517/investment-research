from datetime import date
import importlib.util
from pathlib import Path

from test_core import PRICE, admit, candidate


def test_closure_excludes_placeholder_preserves_original_and_historical_knowledge(tmp_path):
    service, doc, batch = candidate(tmp_path, [dict(PRICE, volume="0")])
    admit(service, batch)
    before = service.execute("coverage", {})
    assert before["record_count"] == 1  # zero volume alone is not proof of closure
    service.repo.json(
        "data/inputs/markets/trading-status/demo-xiaomi/2024/confirmed/status.json",
        {
            "record_id": "demo-closure",
            "security_id": "demo-xiaomi",
            "trading_date": "2024-01-02",
            "market_status": "closed",
            "reason": "Synthetic exchange closure notice for fixture",
            "evidence_document_ids": [doc["document_id"]],
            "published_at": "2024-01-05T00:00:00Z",
            "observed_at": "2024-01-06T00:00:00Z",
            "registered_at": "2024-01-06T00:00:00Z",
        },
    )
    result = service.execute("coverage", {})
    assert result["record_count"] == 0
    assert result["excluded"][0]["reason"] == "confirmed_market_closed"
    assert service.repo.batches()[0][1]["record_count"] == 1
    assert (
        service.execute(
            "coverage",
            {
                "knowledge_mode": "historical_reconstruction",
                "information_cutoff": "2024-01-04T00:00:00Z",
            },
        )["record_count"]
        == 1
    )


def test_backfill_partitions_at_source_boundaries():
    spec = importlib.util.spec_from_file_location(
        "backfill", Path(__file__).parents[1] / "scripts/backfill_price_history.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parts = list(module.windows(date(2018, 7, 9), date(2026, 10, 29)))
    assert parts[0][0] == date(2018, 7, 9) and parts[-1][1] == date(2026, 10, 29)
    assert all((b - a).days < 300 for a, b in parts)
    assert all((parts[i + 1][0] - parts[i][1]).days == 1 for i in range(len(parts) - 1))
