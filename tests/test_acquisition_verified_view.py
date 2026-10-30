"""Task verification gets fresh integrity checks without rebuilding every source index."""

import pytest

from investment_domain import DomainError
from investment_engine.acquisition import run, status
from test_acquisition_tasks import FACT, REVIEW, task
from test_core import PRICE, admit, candidate


def test_status_and_post_admission_use_one_index_per_fresh_stage(tmp_path, monkeypatch):
    # Independent admitted batches amplify the previously quadratic source lookup.
    for day in ("2024-01-02", "2024-01-03", "2024-01-04"):
        service, _, batch = candidate(tmp_path, [dict(PRICE, trading_date=day)])
        admit(service, batch)
    service, _, tid, iid = task(tmp_path)
    index = service.repo._document_index
    batches = service.repo.batches
    counts = {"index": 0}
    checked_stages = []

    def counted_index():
        counts["index"] += 1
        return index()

    def checked_batches():
        assert service.repo._snapshot.get() is not None
        before = counts["index"]
        result = batches()
        checked_stages.append(counts["index"] - before)
        return result

    monkeypatch.setattr(service.repo, "_document_index", counted_index)
    monkeypatch.setattr(service.repo, "batches", checked_batches)
    result = run(service, dict(task_id=tid, submissions={iid: dict(records=[FACT], review=REVIEW)}))
    assert result["status"] == "complete"
    assert all(count <= 1 for count in checked_stages)
    counts["index"] = 0
    assert status(service, dict(task_id=tid))["status"] == "complete"
    assert counts["index"] == 1
    assert service.repo._snapshot.get() is None
    # A later top-level status must not reuse the previously verified bytes.
    document, _ = service.repo.document(result["items"][0]["document_id"])
    original = service.repo.path(document["path"])
    original.write_bytes(original.read_bytes().replace(b"100", b"101"))
    with pytest.raises(DomainError) as error:
        status(service, dict(task_id=tid))
    assert error.value.code == "EVIDENCE_CHANGED"
    assert service.repo._snapshot.get() is None
