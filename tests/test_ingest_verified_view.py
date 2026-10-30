"""Admission caching must not weaken integrity or cross operation boundaries."""

from contextlib import contextmanager

import pytest

from investment_domain import DomainError
from test_core import PRICE, admit, candidate


def test_verified_view_requires_lock_and_blocks_writes(tmp_path):
    service, doc, _ = candidate(tmp_path)
    repo = service.repo
    with pytest.raises(DomainError) as error:
        with repo.verified_read_view():
            pass
    assert error.value.code == "LOCK_REQUIRED"
    with repo.lock():
        with repo.verified_read_view():
            original, _ = repo.document(doc["document_id"])
            original["sha256"] = "polluted"
            assert repo.document(doc["document_id"])[0]["sha256"] != "polluted"
            with pytest.raises(DomainError) as error:
                repo.json("data/forbidden.json", {})
            assert error.value.code == "READ_ONLY_SNAPSHOT"
        repo.json("data/allowed.json", {})
    assert repo._snapshot.get() is None
    assert not repo._lock_owned.get()


def test_plan_apply_each_build_one_index_and_take_one_lock(tmp_path, monkeypatch):
    service, _, first = candidate(tmp_path)
    admit(service, first)
    # Additional batches/documents make duplicate reads observable.
    service, _, second = candidate(tmp_path, [dict(PRICE, trading_date="2024-01-03")])
    repo = service.repo
    counts = dict(index=0, lock=0)
    index, lock = repo._document_index, repo.lock

    def counted_index():
        counts["index"] += 1
        return index()

    @contextmanager
    def counted_lock():
        counts["lock"] += 1
        with lock():
            yield

    monkeypatch.setattr(repo, "_document_index", counted_index)
    monkeypatch.setattr(repo, "lock", counted_lock)
    plan = service.execute("ingest_plan", {"candidate_id": second["candidate_id"]})
    assert counts == dict(index=1, lock=1)
    counts.update(index=0, lock=0)
    assert service.execute("ingest_apply", {"plan_id": plan["plan_id"]})["status"] == "registered"
    assert counts == dict(index=1, lock=1)
    assert repo._snapshot.get() is None
    assert service.execute("coverage", {})["record_count"] == 2


def test_apply_rechecks_original_changed_after_plan(tmp_path):
    service, doc, batch = candidate(tmp_path)
    plan = service.execute("ingest_plan", {"candidate_id": batch["candidate_id"]})
    path = service.repo.path(doc["document"]["path"])
    data = path.read_bytes()
    path.write_bytes(data.replace(b"1000", b"1001"))  # same-size change
    with pytest.raises(DomainError) as error:
        service.execute("ingest_apply", {"plan_id": plan["plan_id"]})
    assert error.value.code == "EVIDENCE_CHANGED"
    assert service.repo._snapshot.get() is None


def test_apply_rechecks_existing_batch_original_and_cleans_failed_view(tmp_path):
    service, doc, first = candidate(tmp_path)
    admit(service, first)
    service, _, second = candidate(tmp_path, [dict(PRICE, trading_date="2024-01-03")])
    plan = service.execute("ingest_plan", {"candidate_id": second["candidate_id"]})
    path = service.repo.path(doc["document"]["path"])
    data = path.read_bytes()
    path.write_bytes(data.replace(b"1000", b"1001"))
    with pytest.raises(DomainError) as error:
        service.execute("ingest_apply", {"plan_id": plan["plan_id"]})
    assert error.value.code == "EVIDENCE_CHANGED"
    assert service.repo._snapshot.get() is None
    path.write_bytes(data)
    assert service.execute("ingest_apply", {"plan_id": plan["plan_id"]})["status"] == "registered"


def test_intervening_admission_still_invalidates_plan(tmp_path):
    service, _, first = candidate(tmp_path)
    old_plan = service.execute("ingest_plan", {"candidate_id": first["candidate_id"]})
    service, _, second = candidate(tmp_path, [dict(PRICE, trading_date="2024-01-03")])
    admit(service, second)
    with pytest.raises(DomainError) as error:
        service.execute("ingest_apply", {"plan_id": old_plan["plan_id"]})
    assert error.value.code == "STALE_PLAN"
    admit(service, first)
    assert service.execute("coverage", {})["record_count"] == 2


def test_cached_batch_results_are_isolated_and_revalidated_next_view(tmp_path):
    service, _, batch = candidate(tmp_path)
    admit(service, batch)
    with service.repo.read_snapshot():
        result = service.repo.batches()
        rel, manifest = result[0]
        manifest["rows"][0]["close"] = "polluted"
        assert service.repo.batches()[0][1]["rows"][0]["close"] == "11"
    raw = service.repo.path(rel).read_text()
    service.repo.path(rel).write_text(raw.replace('"close": "11"', '"close": "12"'))
    with pytest.raises(DomainError) as error:
        with service.repo.read_snapshot():
            service.repo.batches()
    assert error.value.code == "BATCH_INTEGRITY"
