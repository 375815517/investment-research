import csv
import io

import pytest

from investment_domain import DomainError
from investment_engine import Service


PRICE = dict(
    security_id="demo-xiaomi",
    trading_date="2024-01-02",
    open="10",
    high="12",
    low="9",
    close="11",
    volume="1000",
    currency="HKD",
    volume_unit="shares",
    price_basis="unadjusted",
    session="regular-final",
)


def original(tmp_path, records=None):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(PRICE))
    w.writeheader()
    w.writerows(records or [PRICE])
    p = tmp_path / "delivery.csv"
    p.write_text(out.getvalue())
    return p


def candidate(tmp_path, records=None):
    service = Service(tmp_path)
    document = service.execute(
        "import",
        dict(
            path=str(original(tmp_path, records)),
            source_id="demo-source",
            published_at="2024-01-03T00:00:00+00:00",
        ),
    )
    batch = service.execute(
        "prepare", dict(document_id=document["document_id"], dataset_id="daily-prices")
    )
    return service, document, batch


def admit(service, batch):
    plan = service.execute("ingest_plan", dict(candidate_id=batch["candidate_id"]))
    return service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))


def test_duplicate_original_distinct_collection(tmp_path):
    service, doc, _ = candidate(tmp_path)
    repeat = service.execute(
        "import", dict(path=str(tmp_path / "delivery.csv"), source_id="demo-other")
    )
    assert repeat["status"] == "unchanged"
    assert repeat["document_id"] == doc["document_id"]
    assert len(list(tmp_path.glob("data/inputs/source-files/**/original.csv"))) == 1
    assert len(list(tmp_path.glob("data/inputs/collection-records/**/collection.json"))) == 2


def test_complete_batch_and_idempotent_apply(tmp_path):
    service, _, batch = candidate(tmp_path)
    plan = service.execute("ingest_plan", dict(candidate_id=batch["candidate_id"]))
    first = service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))
    second = service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))
    assert first["status"] == "registered" and second["status"] == "unchanged"
    result = service.execute("coverage", {})
    assert result["record_count"] == 1
    assert all((tmp_path / ref).exists() for ref in first["artifact_refs"])
    service.execute("index", {})
    (tmp_path / ".research-local/index.json").unlink()
    assert service.execute("index", {})["batches"] == 1


def test_bad_ohlc_blocks_not_original(tmp_path):
    service, doc, batch = candidate(tmp_path, [dict(PRICE, high="8")])
    report = service.execute("validate", dict(candidate_id=batch["candidate_id"]))
    assert report["status"] == "quarantined"
    with pytest.raises(DomainError, match="Candidate failed"):
        admit(service, batch)
    assert service.repo.document(doc["document_id"])
    assert service.execute("coverage", {})["record_count"] == 0


def test_cutoff_modes(tmp_path):
    service, _, batch = candidate(tmp_path)
    admit(service, batch)
    assert (
        service.execute(
            "coverage",
            dict(
                knowledge_mode="historical_reconstruction",
                information_cutoff="2024-01-02T12:00:00Z",
            ),
        )["record_count"]
        == 0
    )
    assert (
        service.execute(
            "coverage",
            dict(
                knowledge_mode="historical_reconstruction",
                information_cutoff="2024-01-04T12:00:00Z",
            ),
        )["record_count"]
        == 1
    )
    assert (
        service.execute(
            "coverage",
            dict(knowledge_mode="live_observed", information_cutoff="2024-01-04T12:00:00Z"),
        )["record_count"]
        == 0
    )
    assert (
        service.execute("coverage", dict(knowledge_mode="retrospective_explanation"))[
            "record_count"
        ]
        == 1
    )


def test_financial_review_bound_to_candidate(tmp_path):
    p = tmp_path / "report.txt"
    p.write_text("Revenue 100 million CNY for 2024.")
    service = Service(tmp_path)
    doc = service.execute("import", dict(path=str(p), source_id="demo-report"))
    row = dict(
        company_id="demo-xiaomi",
        metric_id="revenue",
        period_start="2024-01-01",
        period_end="2024-12-31",
        source_value="100",
        source_unit="millions",
        currency="CNY",
        scope="consolidated",
        record_kind="reported_actual",
        locator="line:1",
        excerpt=p.read_text(),
    )
    batch = service.execute(
        "prepare", dict(document_id=doc["document_id"], dataset_id="financial-facts", records=[row])
    )
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "review_required"
    )
    with pytest.raises(DomainError, match="review"):
        admit(service, batch)
    service.execute(
        "review",
        dict(
            candidate_id=batch["candidate_id"],
            reviewer="test-human",
            decision="approved",
            notes="Checked line 1 and scope against fixture",
        ),
    )
    plan = service.execute("ingest_plan", dict(candidate_id=batch["candidate_id"]))
    path = ".research-local/candidates/" + batch["candidate_id"] + ".json"
    edited = service.repo.read_json(path)
    edited["records"][0]["source_value"] = "200"
    service.repo.json(path, edited, immutable=False)
    with pytest.raises(DomainError, match="Candidate changed"):
        service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))


def test_crash_before_manifest_resume(tmp_path, monkeypatch):
    service, _, batch = candidate(tmp_path)
    plan = service.execute("ingest_plan", dict(candidate_id=batch["candidate_id"]))
    real = service.repo.json

    def fail_manifest(relative, value, **kwargs):
        if relative.endswith("/batch.json"):
            raise OSError("simulated interrupted write")
        return real(relative, value, **kwargs)

    monkeypatch.setattr(service.repo, "json", fail_manifest)
    with pytest.raises(DomainError):
        service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))
    assert service.execute("coverage", {})["record_count"] == 0
    monkeypatch.setattr(service.repo, "json", real)
    assert service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))["status"] == "registered"


def test_evidence_tamper_detected(tmp_path):
    service, doc, batch = candidate(tmp_path)
    (tmp_path / doc["document"]["path"]).write_text("changed")
    with pytest.raises(DomainError, match="doc-"):
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))


def test_unknown_subject_not_auto_confirmed(tmp_path):
    service, _, batch = candidate(tmp_path, [dict(PRICE, security_id="xiaomi-hk")])
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "quarantined"
    )


def test_paths_and_version_protection(tmp_path):
    service = Service(tmp_path)
    with pytest.raises(DomainError):
        service.repo.write("../escape.json", b"x")
    (tmp_path / "linked").symlink_to(tmp_path / "actual")
    with pytest.raises(DomainError):
        service.repo.write("linked/x", b"x")
    service.repo.write("data/one.json", b"a")
    with pytest.raises(DomainError):
        service.repo.write("data/one.json", b"b")


def test_multisecurity_one_original(tmp_path):
    service, _, batch = candidate(tmp_path, [PRICE, dict(PRICE, security_id="demo-peer")])
    admit(service, batch)
    assert len(list(tmp_path.glob("data/inputs/source-files/**/original.csv"))) == 1
    assert len(service.repo.batches()) == 2
    assert service.execute("coverage", dict(subject_id="demo-peer"))["record_count"] == 1


def test_status_resume_completed(tmp_path):
    service, _, batch = candidate(tmp_path)
    status = service.execute("status", dict(operation_id=batch["operation_id"]))
    assert status["status"] == "ok" and status["operation_status"] == "completed"
    assert (
        service.execute("resume", dict(operation_id=batch["operation_id"]))["status"] == "unchanged"
    )


def test_price_override_rejected(tmp_path):
    service, doc, _ = candidate(tmp_path)
    with pytest.raises(DomainError, match="archived source"):
        service.execute(
            "prepare",
            dict(
                document_id=doc["document_id"],
                dataset_id="daily-prices",
                records=[dict(PRICE, close="999")],
            ),
        )


def test_manifest_cannot_disagree_with_csv(tmp_path):
    service, _, batch = candidate(tmp_path)
    admit(service, batch)
    rel, manifest = service.repo.batches()[0]
    manifest["rows"][0]["close"] = "999"
    service.repo.json(rel, manifest, immutable=False)
    with pytest.raises(DomainError, match="Manifest records differ"):
        service.execute("coverage", {})


def test_failed_operation_resume_has_one_response_envelope(tmp_path):
    service, _, batch = candidate(tmp_path)
    with pytest.raises(DomainError):
        service.execute("ingest_apply", dict(plan_id="missing-plan"))
    failed = [
        p
        for p in (tmp_path / ".research-local/operations").glob("*.json")
        if service.repo.read_json(p.relative_to(tmp_path).as_posix())["status"] == "failed"
    ][0]
    checkpoint = service.repo.read_json(failed.relative_to(tmp_path).as_posix())
    checkpoint["operation"] = "validate"
    checkpoint["payload"] = dict(candidate_id=batch["candidate_id"])
    service.repo.json(failed.relative_to(tmp_path).as_posix(), checkpoint, immutable=False)
    response = service.execute("resume", dict(operation_id=failed.stem))
    assert response["status"] == "eligible" and response["protocol_version"] == "1"


def test_failed_connector_has_durable_receipt(tmp_path):
    class Broken:
        def execute(self, operation, payload):
            raise DomainError("SOURCE_UNAVAILABLE", "temporary", 5)

    service = Service(tmp_path, connector_service=Broken())
    with pytest.raises(DomainError):
        service.execute("collect", dict(source_id="demo-source", parameters={"token": "hidden"}))
    receipt = next(tmp_path.glob("data/inputs/collection-records/**/collection.json"))
    assert '"failed"' in receipt.read_text()
    assert "hidden" not in receipt.read_text()


def test_same_source_revision_requires_explicit_link(tmp_path):
    service, _, batch = candidate(tmp_path)
    admit(service, batch)
    old_id = service.repo.batches()[0][1]["batch_id"]
    newer = original(tmp_path, [dict(PRICE, close="10")])
    doc = service.execute(
        "import",
        dict(path=str(newer), source_id="demo-source", published_at="2024-01-05T00:00:00Z"),
    )
    prepared = service.execute(
        "prepare", dict(document_id=doc["document_id"], dataset_id="daily-prices")
    )
    with pytest.raises(DomainError, match="supersedes"):
        admit(service, prepared)
    prepared = service.execute(
        "prepare",
        dict(document_id=doc["document_id"], dataset_id="daily-prices", supersedes=[old_id]),
    )
    admit(service, prepared)
    assert service.execute("coverage", {})["record_count"] == 1
    old_view = service.execute(
        "coverage",
        dict(knowledge_mode="historical_reconstruction", information_cutoff="2024-01-04T00:00:00Z"),
    )
    assert old_view["rows"][0]["close"] == "11"


def test_multibatch_interruption_resumes_registered_subset(tmp_path, monkeypatch):
    service, _, batch = candidate(tmp_path, [PRICE, dict(PRICE, security_id="demo-peer")])
    plan = service.execute("ingest_plan", dict(candidate_id=batch["candidate_id"]))
    real = service.repo.json
    count = 0

    def fail_second_manifest(relative, value, **kwargs):
        nonlocal count
        if relative.endswith("/batch.json"):
            count += 1
            if count == 2:
                raise OSError("second batch interrupted")
        return real(relative, value, **kwargs)

    monkeypatch.setattr(service.repo, "json", fail_second_manifest)
    with pytest.raises(DomainError):
        service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))
    assert service.execute("coverage", {})["record_count"] == 1
    monkeypatch.setattr(service.repo, "json", real)
    service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))
    assert service.execute("coverage", {})["record_count"] == 2


def test_chained_revisions_only_check_active_versions(tmp_path):
    service, _, first = candidate(tmp_path)
    admit(service, first)
    prior_id = service.repo.batches()[0][1]["batch_id"]
    for day, close in [(5, "10"), (6, "9")]:
        source_file = original(tmp_path, [dict(PRICE, close=close)])
        doc = service.execute(
            "import",
            dict(
                path=str(source_file),
                source_id="demo-source",
                published_at=f"2024-01-{day:02d}T00:00:00Z",
            ),
        )
        batch = service.execute(
            "prepare",
            dict(document_id=doc["document_id"], dataset_id="daily-prices", supersedes=[prior_id]),
        )
        result = admit(service, batch)
        current = service.execute("coverage", {})
        assert current["record_count"] == 1
        assert current["rows"][0]["close"] == close
        prior_id = next(
            service.repo.read_json(ref)["batch_id"]
            for ref in result["artifact_refs"]
            if ref.endswith("/batch.json")
        )
    assert len(service.repo.batches()) == 3
    assert (
        service.execute(
            "coverage",
            dict(
                knowledge_mode="historical_reconstruction",
                information_cutoff="2024-01-04T00:00:00Z",
            ),
        )["rows"][0]["close"]
        == "11"
    )
    assert (
        service.execute(
            "coverage",
            dict(
                knowledge_mode="historical_reconstruction",
                information_cutoff="2024-01-05T12:00:00Z",
            ),
        )["rows"][0]["close"]
        == "10"
    )


def test_rolling_window_deduplicates_same_source_and_retains_provenance(tmp_path):
    service, _, first = candidate(tmp_path)
    admit(service, first)
    source_file = original(tmp_path, [PRICE, dict(PRICE, trading_date="2024-01-03")])
    doc = service.execute(
        "import",
        dict(path=str(source_file), source_id="demo-source", published_at="2024-01-04T00:00:00Z"),
    )
    second = service.execute(
        "prepare", dict(document_id=doc["document_id"], dataset_id="daily-prices")
    )
    admit(service, second)
    result = service.execute("coverage", {})
    assert result["record_count"] == 2
    jan2 = next(row for row in result["rows"] if row["trading_date"] == "2024-01-02")
    assert len(jan2["batch_refs"]) == 2
    assert len(jan2["document_refs"]) == 2
    assert all((tmp_path / ref).exists() for ref in jan2["batch_refs"])
