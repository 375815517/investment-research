"""Publication revision preserves source precision and historical/live boundaries."""

from datetime import datetime
import json

import pytest

from investment_domain import DomainError
from investment_engine import Service
from investment_engine.evidence_time import document_available
from investment_engine.ensure import detect
from investment_engine.temporal import revise_metadata
from investment_repository.metadata import publication_bounds


def fixture(service, monkeypatch):
    monkeypatch.setattr("investment_repository.utc_now", lambda: "2023-12-01T00:00:00+00:00")
    target, refs, _ = service.repo.import_bytes(
        b"Annual revenue source", "demo-report", ".txt", None, "Report"
    )
    evidence, _, _ = service.repo.import_bytes(
        b"Official report publication date 2024-01-02. Corrected date 2024-02-01.",
        "demo-index",
        ".txt",
        None,
        "Publication index",
    )
    return target, evidence, refs


def request(target, evidence, publication=None, **kwargs):
    return dict(
        document_id=target["document_id"],
        evidence_document_id=evidence["document_id"],
        publication=publication
        or dict(precision="date", date="2024-01-02", timezone="Asia/Hong_Kong"),
        locator="text:publication",
        excerpt="Official report publication date 2024-01-02.",
        reviewer="test-reviewer",
        notes="Synthetic publication evidence, not financial data",
        **kwargs,
    )


def cutoff(value):
    return datetime.fromisoformat(value)


def test_date_precision_upper_bound_and_original_unchanged(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, refs = fixture(service, monkeypatch)
    original = service.repo.path(refs[1]).read_bytes()
    revise_metadata(service, request(target, evidence))
    doc, ref = service.repo.effective_document(target["document_id"])
    assert doc["published_at"] is None
    assert doc["publication_precision"] == "date"
    assert doc["availability_lower_bound"] == "2024-01-01T16:00:00+00:00"
    assert doc["availability_upper_bound"] == "2024-01-02T16:00:00+00:00"
    assert "metadata-revisions/" in ref
    assert not document_available(
        doc, "historical_reconstruction", cutoff("2024-01-02T15:59:59+00:00")
    )
    assert document_available(doc, "historical_reconstruction", cutoff("2024-01-02T16:00:00+00:00"))
    assert service.repo.path(refs[1]).read_bytes() == original
    assert service.repo.document(target["document_id"])[0]["published_at"] is None


def test_later_revision_does_not_change_explicit_frozen_version(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    monkeypatch.setattr(
        "investment_repository.metadata.utc_now", lambda: "2026-01-01T00:00:00+00:00"
    )
    first = revise_metadata(service, request(target, evidence))
    frozen, frozen_path = service.repo.effective_document(
        target["document_id"], revision_id=first["revision_id"]
    )
    second_request = request(
        target,
        evidence,
        dict(precision="date", date="2024-02-01", timezone="Asia/Hong_Kong"),
        expected_revision_id=first["revision_id"],
    )
    second_request["excerpt"] = "Corrected date 2024-02-01."
    monkeypatch.setattr(
        "investment_repository.metadata.utc_now", lambda: "2026-01-02T00:00:00+00:00"
    )
    second = revise_metadata(service, second_request)
    assert second["revision_id"] != first["revision_id"]
    assert service.repo.effective_document(
        target["document_id"], revision_id=first["revision_id"]
    ) == (frozen, frozen_path)
    latest, _ = service.repo.effective_document(
        target["document_id"], "historical_reconstruction", "2024-01-10T00:00:00Z"
    )
    assert not document_available(
        latest, "historical_reconstruction", cutoff("2024-01-10T00:00:00+00:00")
    )
    assert document_available(
        frozen, "historical_reconstruction", cutoff("2024-01-10T00:00:00+00:00")
    )
    assert (
        service.repo.effective_document(target["document_id"], revision_id="original")[0][
            "availability_upper_bound"
        ]
        is None
    )


def test_live_cannot_use_later_review_even_when_evidence_proves_old_date(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    monkeypatch.setattr(
        "investment_repository.metadata.utc_now", lambda: "2026-01-01T00:00:00+00:00"
    )
    first = revise_metadata(service, request(target, evidence))
    before = "2025-12-31T23:59:59+00:00"
    live, _ = service.repo.effective_document(target["document_id"], "live_observed", before)
    assert live["metadata_revision_id"] == "original"
    assert not document_available(live, "live_observed", cutoff(before))
    pinned, _ = service.repo.effective_document(
        target["document_id"], "live_observed", before, first["revision_id"]
    )
    assert not document_available(pinned, "live_observed", cutoff(before))
    reconstruct, _ = service.repo.effective_document(
        target["document_id"], "historical_reconstruction", before
    )
    assert document_available(reconstruct, "historical_reconstruction", cutoff(before))
    after, _ = service.repo.effective_document(
        target["document_id"], "live_observed", "2026-01-02T00:00:00+00:00"
    )
    assert document_available(after, "live_observed", cutoff("2026-01-02T00:00:00+00:00"))


def test_revision_requires_current_parent_and_matching_excerpt(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    bad = request(target, evidence)
    bad["excerpt"] = "This phrase does not appear"
    with pytest.raises(DomainError, match="absent"):
        revise_metadata(service, bad)
    revise_metadata(service, request(target, evidence))
    with pytest.raises(DomainError) as exc:
        revise_metadata(service, request(target, evidence))
    assert exc.value.code == "STALE_METADATA_REVISION"


def test_revision_withdrawal_is_explicit_unknown(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    first = revise_metadata(service, request(target, evidence))
    revise_metadata(
        service,
        request(
            target, evidence, dict(precision="unknown"), expected_revision_id=first["revision_id"]
        ),
    )
    latest, _ = service.repo.effective_document(target["document_id"])
    assert latest["publication_precision"] == "unknown"
    assert not document_available(
        latest, "historical_reconstruction", cutoff("2030-01-01T00:00:00+00:00")
    )


def test_revision_and_original_integrity_checked(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    result = revise_metadata(service, request(target, evidence))
    path = service.repo.path(result["artifact_refs"][-1])
    record = json.loads(path.read_text())
    record["publication"]["date"] = "2023-01-01"
    path.write_text(json.dumps(record))
    with pytest.raises(DomainError) as exc:
        service.repo.effective_document(target["document_id"])
    assert exc.value.code == "METADATA_REVISION_INTEGRITY"


def test_interval_and_dst_bounds_preserve_local_date():
    assert publication_bounds(
        dict(
            precision="interval",
            earliest="2024-01-01T08:00:00+08:00",
            latest="2024-01-02T08:00:00+08:00",
        )
    ) == ("2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00")
    assert publication_bounds(
        dict(precision="date", date="2024-03-10", timezone="America/New_York")
    ) == ("2024-03-10T05:00:00+00:00", "2024-03-11T04:00:00+00:00")


def test_explicit_unknown_revision_fails_instead_of_falling_back(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, _, _ = fixture(service, monkeypatch)
    with pytest.raises(DomainError) as exc:
        service.repo.effective_document(target["document_id"], revision_id="missing")
    assert exc.value.code == "METADATA_REVISION_NOT_FOUND"


def test_service_coverage_uses_reviewed_date_for_old_unknown_batch(tmp_path, monkeypatch):
    from test_core import original, admit

    service = Service(tmp_path)
    price_doc = service.execute(
        "import", dict(path=str(original(tmp_path)), source_id="demo-price")
    )
    candidate = service.execute(
        "prepare", dict(document_id=price_doc["document_id"], dataset_id="daily-prices")
    )
    admit(service, candidate)
    query = dict(
        dataset_id="daily-prices",
        knowledge_mode="historical_reconstruction",
        information_cutoff="2024-01-04T00:00:00Z",
    )
    assert service.execute("coverage", query)["record_count"] == 0
    target = service.repo.document(price_doc["document_id"])[0]
    evidence, _, _ = service.repo.import_bytes(
        b"Official report publication date 2024-01-02.", "demo-index", ".txt", None, "Index"
    )
    revised = service.execute("revise_metadata", request(target, evidence))
    result = service.execute("coverage", query)
    assert result["record_count"] == 1
    assert revised["artifact_refs"][-1] in result["rows"][0]["document_metadata_refs"]
    assert (
        service.execute("coverage", dict(query, knowledge_mode="live_observed"))["record_count"]
        == 0
    )
    assert service.repo.batches()[0][1]["published_at"] is None
    assessed = service.execute(
        "assess_inputs",
        dict(
            requirements=[
                dict(
                    dataset_id="daily-prices",
                    subject_id="demo-xiaomi",
                    start="2024-01-02",
                    end="2024-01-02",
                    minimum_records=1,
                )
            ],
            purpose="historical_point_in_time",
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-04T00:00:00Z",
        ),
    )
    assert "PUBLICATION_TIME_UNKNOWN" not in {x["code"] for x in assessed["findings"]}
    assert assessed["audit"]["status"] == "complete"


def test_calendar_recheck_uses_publication_revision(tmp_path, monkeypatch):
    from test_ensure import expectation

    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    request_data = expectation(service, target["document_id"])
    query = dict(
        request_data,
        knowledge_mode="historical_reconstruction",
        information_cutoff="2024-01-04T00:00:00Z",
    )
    assert (
        service.execute("detect_gaps", query)["gaps"][0]["reason"]
        == "expectation_unavailable_at_cutoff"
    )
    revise_metadata(service, request(target, evidence))
    result = detect(service, query)
    assert result["gaps"][0]["reason"] == "missing_observation"
    assert any("metadata-revisions" in ref for ref in result["artifact_refs"])


def test_supporting_evidence_is_bound_and_tamper_blocks(tmp_path, monkeypatch):
    service = Service(tmp_path)
    target, evidence, _ = fixture(service, monkeypatch)
    supporting, _, _ = service.repo.import_bytes(
        b"Official linked report identity", "demo-index", ".txt", None, "Linked index"
    )
    result = revise_metadata(
        service, request(target, evidence, supporting_document_ids=[supporting["document_id"]])
    )
    record = service.repo.read_json(result["artifact_refs"][-1])
    assert record["supporting_documents"] == [
        dict(document_id=supporting["document_id"], sha256=supporting["sha256"])
    ]
    effective, _ = service.repo.effective_document(target["document_id"])
    assert effective["metadata_evidence_refs"] == [
        evidence["document_id"],
        supporting["document_id"],
    ]
    service.repo.path(supporting["path"]).write_bytes(b"Modified linked identity")
    with pytest.raises(DomainError):
        service.repo.effective_document(target["document_id"])
