"""Acceptance tests for evidence-bound completeness and bounded acquisition."""

import json

import pytest

from investment_domain import DomainError
from investment_engine import Service
from test_core import PRICE, admit, candidate, original


def expectation(service, doc_id, *, financial=False, items=None):
    item = dict(
        date="2024-01-02",
        expected=True,
        due_at="2024-01-02T08:30:00Z",
        reason="evidenced close plus delivery delay",
    )
    if financial:
        item.update(
            metric_ids=["revenue"], period_start="2023-01-01", scope="consolidated", currency="CNY"
        )
    value = dict(
        expectation_id="demo-calendar-v1",
        dataset_id="financial-facts" if financial else "daily-prices",
        subject_id="demo-xiaomi",
        start="2024-01-02",
        end="2024-01-02",
        published_at="2023-12-01T00:00:00Z",
        observed_at="2023-12-02T00:00:00Z",
        registered_at="2023-12-02T00:00:00Z",
        evidence_document_ids=[doc_id],
        items=items if items is not None else [item],
    )
    ref = "data/inputs/markets/calendars/demo/2024/v1/expectations.json"
    service.repo.json(ref, value)
    return dict(
        dataset_id=value["dataset_id"],
        subject_id=value["subject_id"],
        start=value["start"],
        end=value["end"],
        expectation_path=ref,
    )


def test_due_calendar_and_missing_day_unknown(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    before = service.execute("detect_gaps", dict(request, as_of="2024-01-02T08:00:00Z"))
    assert before["status"] == "complete" and before["excluded"][0]["reason"] == "not_due"
    after = service.execute("detect_gaps", dict(request, as_of="2024-01-02T09:00:00Z"))
    assert after["gaps"][0]["reason"] == "missing_observation"
    expanded = service.execute("detect_gaps", dict(request, end="2024-01-03"))
    assert expanded["gaps"][0]["reason"] == "unknown_expectation"


def test_holiday_and_suspension_are_explicit(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(
        service,
        doc["document_id"],
        items=[
            dict(
                date="2024-01-02",
                expected=False,
                due_at="2024-01-02T08:30:00Z",
                reason="documented suspension",
            )
        ],
    )
    result = service.execute("detect_gaps", request)
    assert result["status"] == "complete" and result["coverage"]["expected_count"] == 0
    assert result["excluded"][0]["reason"] == "not_expected"


def test_missing_calendar_is_not_guessed(tmp_path):
    service = Service(tmp_path)
    result = service.execute(
        "detect_gaps",
        dict(
            dataset_id="daily-prices",
            subject_id="x",
            start="2024-01-02",
            end="2024-01-02",
            expectation_path="data/inputs/missing.json",
        ),
    )
    assert result["status"] == "blocked" and result["gaps"][0]["reason"] == "unknown_expectation"


def test_evidence_tampering_blocks_detection(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    service.repo.path(doc["document"]["path"]).write_text("changed")
    with pytest.raises(DomainError, match="doc-") as exc:
        service.execute("detect_gaps", request)
    assert exc.value.code == "EVIDENCE_CHANGED"


def test_live_past_cannot_be_fixed_by_current_acquisition(tmp_path, monkeypatch):
    # Isolate missing observations from unavailable calendar evidence: this fixture's
    # supporting document really was observed before the queried historical cutoff.
    monkeypatch.setattr("investment_repository.utc_now", lambda: "2024-01-03T00:00:00Z")
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    result = service.execute(
        "detect_gaps",
        dict(request, knowledge_mode="live_observed", information_cutoff="2024-01-04T00:00:00Z"),
    )
    assert result["gaps"][0]["reason"] == "historically_unavailable"
    assert result["gaps"][0]["retryable"] is False
    # A later version of the expectation itself cannot explain an earlier cutoff.
    result = service.execute(
        "detect_gaps",
        dict(
            request,
            knowledge_mode="historical_reconstruction",
            information_cutoff="2023-11-01T00:00:00Z",
        ),
    )
    assert result["gaps"][0]["reason"] == "expectation_unavailable_at_cutoff"


class CSVConnector:
    def __init__(self, path, empty=False):
        self.path, self.calls = path, 0

    def execute(self, operation, payload):
        assert operation == "collect"
        self.calls += 1
        return dict(
            import_request=dict(
                path=str(self.path), source_id="demo-source", published_at="2024-01-03T00:00:00Z"
            ),
            delivery={},
        )


def test_ensure_fills_and_rechecks_and_replays(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    connector = CSVConnector(original(tmp_path))
    service.connector_service = connector
    plan = service.execute(
        "ensure_plan", dict(request, acquisition=dict(source_id="demo-source", parameters={}))
    )
    result = service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))
    assert result["status"] == "complete"
    assert result["after"]["coverage"] == dict(expected_count=1, present_count=1)
    assert service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))["replayed"]
    assert connector.calls == 1


def test_ensure_skips_when_other_ingestion_filled_gap(tmp_path):
    service, doc, batch = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    connector = CSVConnector(original(tmp_path))
    service.connector_service = connector
    plan = service.execute("ensure_plan", dict(request, acquisition=dict(source_id="demo-source")))
    admit(service, batch)
    assert service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))["status"] == "complete"
    assert connector.calls == 0


def test_ensure_stale_expectation(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    plan = service.execute("ensure_plan", dict(request, acquisition=dict(source_id="demo-source")))
    p = service.repo.path(request["expectation_path"])
    value = json.loads(p.read_text())
    value["expectation_id"] = "mutated"
    p.write_text(json.dumps(value))
    with pytest.raises(DomainError) as exc:
        service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))
    assert exc.value.code == "PLAN_STALE"


def test_empty_acquisition_is_not_complete(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    path = tmp_path / "empty.csv"
    path.write_text(",".join(PRICE) + "\n")
    service.connector_service = CSVConnector(path)
    plan = service.execute("ensure_plan", dict(request, acquisition=dict(source_id="demo-source")))
    result = service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))
    assert result["status"] == "blocked"
    assert result["after"]["gaps"][0]["reason"] == "missing_observation"
    assert result["issues"][0]["code"] == "EMPTY_BATCH"


def test_financial_report_missing_vs_processing(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"], financial=True)
    result = service.execute("detect_gaps", request)
    assert result["gaps"][0]["reason"] == "disclosure_not_found"
    p = service.repo.path(request["expectation_path"])
    value = json.loads(p.read_text())
    value["items"][0]["report_document_id"] = doc["document_id"]
    p.write_text(json.dumps(value))
    result = service.execute("detect_gaps", request)
    assert result["status"] == "review_required"
    assert result["gaps"][0]["missing_metrics"] == ["revenue"]


def test_native_prices_require_explicit_query_basis(tmp_path):
    service, doc, batch = candidate(
        tmp_path, [dict(PRICE, price_basis="provider-native", volume_unit="provider-native")]
    )
    admit(service, batch)
    request = expectation(service, doc["document_id"])
    assert service.execute("detect_gaps", request)["status"] == "partial"
    assert (
        service.execute("detect_gaps", dict(request, price_basis="provider-native"))["status"]
        == "complete"
    )


def test_source_configuration_change_stales_plan(tmp_path):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    p = service.repo.path("research/sources/demo-source/source.yaml")
    p.parent.mkdir(parents=True)
    p.write_text("version: 1")
    plan = service.execute("ensure_plan", dict(request, acquisition=dict(source_id="demo-source")))
    p.write_text("version: 2")
    with pytest.raises(DomainError) as exc:
        service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))
    assert exc.value.code == "PLAN_STALE"


def test_archived_json_parser_is_injected_and_bound(tmp_path):
    class Parser:
        def execute(self, operation, payload):
            assert operation == "parse"
            assert json.loads(__import__("pathlib").Path(payload["document_path"]).read_text()) == {
                "source": "fixture"
            }
            return dict(
                parser_id="demo-json-v1", records=[dict(PRICE, price_basis="provider-native")]
            )

    path = tmp_path / "source.json"
    path.write_text('{"source":"fixture"}')
    service = Service(tmp_path, connector_service=Parser())
    doc = service.execute("import", dict(path=str(path), source_id="demo-source"))
    batch = service.execute(
        "prepare", dict(document_id=doc["document_id"], dataset_id="daily-prices")
    )
    admit(service, batch)
    assert service.execute("coverage", dict(price_basis="provider-native"))["record_count"] == 1
    assert service.execute("coverage", {})["record_count"] == 0


@pytest.mark.parametrize(
    "locator,excerpt,expected",
    [
        ("pdf:page:2", "Revenue 100 million", "review_required"),
        ("pdf:page:1", "Revenue 100 million", "quarantined"),
        ("page 2", "Revenue 100 million", "quarantined"),
        ("pdf:page:2", "Revenue 999 million", "quarantined"),
    ],
)
def test_pdf_excerpt_must_match_specific_physical_page(tmp_path, locator, excerpt, expected):
    class Extractor:
        def execute(self, operation, payload):
            assert operation == "extract_pdf_page"
            return dict(text="Revenue\n100  million" if payload["page"] == 2 else "Cover page")

    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF fixture verified by injected extractor")
    service = Service(tmp_path, connector_service=Extractor())
    doc = service.execute("import", dict(path=str(path), source_id="demo-source"))
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
        locator=locator,
        excerpt=excerpt,
    )
    batch = service.execute(
        "prepare", dict(document_id=doc["document_id"], dataset_id="financial-facts", records=[row])
    )
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"] == expected
    )


@pytest.mark.parametrize("change", ["batch", "expectation", "source"])
def test_replayed_ensure_rechecks_current_state(tmp_path, change):
    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    source = service.repo.path("research/sources/demo-source/source.yaml")
    source.parent.mkdir(parents=True)
    source.write_text("version: 1")
    service.connector_service = CSVConnector(original(tmp_path))
    plan = service.execute("ensure_plan", dict(request, acquisition=dict(source_id="demo-source")))
    assert service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))["status"] == "complete"
    if change == "batch":
        next(tmp_path.glob("data/inputs/markets/prices/**/batch.json")).unlink()
    elif change == "source":
        source.write_text("version: 2")
    else:
        p = service.repo.path(request["expectation_path"])
        value = json.loads(p.read_text())
        value["expectation_id"] = "changed"
        p.write_text(json.dumps(value))
    with pytest.raises(DomainError) as exc:
        service.execute("ensure_apply", dict(plan_id=plan["plan_id"]))
    assert exc.value.code == "PLAN_STALE"


def test_concurrent_ensure_uses_one_acquisition(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    service, doc, _ = candidate(tmp_path)
    request = expectation(service, doc["document_id"])
    entered, release = Event(), Event()

    class WaitingConnector(CSVConnector):
        def execute(self, operation, payload):
            entered.set()
            assert release.wait(timeout=5)
            return super().execute(operation, payload)

    connector = WaitingConnector(original(tmp_path))
    service.connector_service = connector
    plan = service.execute("ensure_plan", dict(request, acquisition=dict(source_id="demo-source")))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.execute, "ensure_apply", dict(plan_id=plan["plan_id"]))
        assert entered.wait(timeout=5)
        second = pool.submit(service.execute, "ensure_apply", dict(plan_id=plan["plan_id"]))
        release.set()
        results = [first.result(timeout=5), second.result(timeout=5)]
    assert connector.calls == 1
    assert all(result["status"] == "complete" for result in results)
    assert sum(bool(result.get("replayed")) for result in results) == 1
