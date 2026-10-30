"""Portable discovery and acquisition workflows, not merely happy-path download counts."""

import json
import shutil
from email.message import Message
from urllib.error import HTTPError
from urllib.request import Request

import pytest
import yaml

from investment_connectors import ConnectorError, HttpFetcher, SourceDefinition
from investment_connectors.http import _SafeRedirect
from investment_connectors.providers import discover_page, render_url
from investment_domain import DomainError
from investment_engine import Service
from investment_engine.acquisition import BASE, discover, plan, run, status
from test_connectors import Opener, Response


FACT = dict(
    company_id="demo",
    metric_id="revenue",
    period_start="2024-01-01",
    period_end="2024-12-31",
    source_value="100",
    source_unit="millions",
    currency="CNY",
    scope="consolidated",
    record_kind="reported_actual",
    locator="line:1",
    excerpt="Revenue 100 million",
)
REVIEW = dict(
    reviewer="independent-test-reviewer",
    decision="approved",
    notes="Read source amount, unit and reporting period",
)


def config(root, **changes):
    provider = dict(
        provider_id="reports",
        url="https://example.invalid/list/{page}",
        connector_id="http-document-v1",
        dataset_id="financial-facts",
        allowed_hosts=["example.invalid"],
        allowed_parameters=["page"],
        archive_permissions="allowed",
        pagination=True,
        max_pages=5,
    )
    provider.update(changes)
    p = root / "research/source-providers/reports"
    p.mkdir(parents=True)
    (p / "provider.yaml").write_text(yaml.safe_dump(provider))
    p = root / "research/source-bindings/demo-reports"
    p.mkdir(parents=True)
    (p / "binding.yaml").write_text(
        yaml.safe_dump(dict(binding_id="demo-reports", provider_id="reports", subject_id="demo"))
    )


class FakeConnector:
    def __init__(self, root, fail_page=None):
        self.root = root
        self.calls = []
        self.fail_page = fail_page

    def execute(self, operation, payload):
        self.calls.append((operation, payload))
        if operation == "discover":
            page = payload["parameters"]["page"]
            if page == self.fail_page:
                raise ConnectorError(
                    "SOURCE_NETWORK_ERROR", "offline", retryable=True, retry_after_seconds=0
                )
            file = self.root / f"listing-{page}.html"
            file.write_text(f"<html>Listing {page}</html>")
            return dict(
                delivery=dict(path=str(file)),
                origin_url=f"https://example.invalid/list/{page}",
                entries=[
                    dict(
                        url=f"https://example.invalid/report-{page}.pdf",
                        title=f"Annual report {page}",
                        context="2024",
                    )
                ],
                next_parameters=dict(page=page + 1) if page < 2 else None,
            )
        assert operation == "collect_item"
        file = self.root / "report.txt"
        file.write_text(FACT["excerpt"])
        return dict(delivery=dict(path=str(file)), origin_url=payload["url"])


def task(root):
    config(root)
    connector = FakeConnector(root)
    service = Service(root, connector)
    found = discover(service, dict(binding_id="demo-reports", parameters=dict(page=1)))
    planned = plan(service, dict(discovery_id=found["discovery_id"], dataset_id="financial-facts"))
    return service, connector, planned["task_id"], found["entries"][0]["item_id"]


def test_binding_changes_object_without_copying_provider(tmp_path):
    config(tmp_path)
    source = SourceDefinition.load(tmp_path, "demo-reports")
    assert source.subject_id == "demo" and source.source_id == "demo-reports"
    assert source.allowed_redirect_hosts == ("example.invalid",)
    assert render_url(
        "https://example.invalid/{year}/d{yymmdd}.htm", dict(year=2024, date="2024-03-02"), {}
    ) == ("https://example.invalid/2024/d240302.htm", {})


def test_real_html_pagination_and_duplicate_links(tmp_path):
    config(tmp_path)
    html = b'<html><h2>2024</h2><a href="/r.pdf"></a><a href="/r.pdf">Annual report</a><a href="https://other.invalid/r.pdf">foreign</a><a class="next page-numbers" href="/list/2">Next &raquo;</a></html>'
    fetched = discover_page(
        tmp_path,
        HttpFetcher(opener=Opener(Response(html, "text/html"))),
        dict(binding_id="demo-reports", parameters=dict(page=1)),
    )
    assert len(fetched["entries"]) == 1
    assert fetched["entries"][0]["title"] == "Annual report"
    assert fetched["entries"][0]["context"] == "2024"
    assert fetched["next_parameters"] == dict(page=2)


def test_template_page_does_not_claim_empty_history(tmp_path):
    config(tmp_path)
    with pytest.raises(ConnectorError) as error:
        discover_page(
            tmp_path,
            HttpFetcher(
                opener=Opener(Response(b"<html>Please enter a symbol</html>", "text/html"))
            ),
            dict(binding_id="demo-reports", parameters=dict(page=1)),
        )
    assert error.value.code == "SOURCE_DISCOVERY_EMPTY"


def test_page_failure_has_durable_cursor_and_resumes(tmp_path):
    config(tmp_path)
    connector = FakeConnector(tmp_path, fail_page=2)
    service = Service(tmp_path, connector)
    first = discover(service, dict(binding_id="demo-reports", parameters=dict(page=1), max_pages=3))
    assert first["status"] == "partial" and first["next_parameters"] == dict(page=2)
    shutil.rmtree(tmp_path / ".research-local")
    connector.fail_page = None
    second = discover(
        Service(tmp_path, connector),
        dict(binding_id="demo-reports", resume_discovery_id=first["discovery_id"], max_pages=3),
    )
    assert len(second["entries"]) == 2 and second["next_parameters"] is None
    assert [call[1]["parameters"]["page"] for call in connector.calls] == [1, 2, 2]


def test_clone_restores_candidate_and_review_without_redownload(tmp_path):
    service, connector, tid, iid = task(tmp_path)
    assert run(service, dict(task_id=tid))["items"][0]["stage"] == "awaiting_extraction"
    result = run(service, dict(task_id=tid, submissions={iid: dict(records=[FACT])}))
    assert result["items"][0]["stage"] == "awaiting_review"
    shutil.rmtree(tmp_path / ".research-local")
    restored = Service(tmp_path, connector)
    result = run(restored, dict(task_id=tid, submissions={iid: dict(review=REVIEW)}))
    assert result["status"] == "complete"
    assert len([x for x in connector.calls if x[0] == "collect_item"]) == 1
    assert run(restored, dict(task_id=tid))["status"] == "complete"
    assert len(restored.repo.batches()) == 1


def test_approval_survives_admission_failure_and_reclone(tmp_path, monkeypatch):
    service, connector, tid, iid = task(tmp_path)

    def fail(payload):
        raise DomainError("TEMPORARY_ADMISSION_FAILURE", "simulate failure after review")

    monkeypatch.setattr(service, "_ingest_apply", fail)
    result = run(service, dict(task_id=tid, submissions={iid: dict(records=[FACT], review=REVIEW)}))
    assert result["status"] == "blocked" and result["items"][0]["review_refs"]
    shutil.rmtree(tmp_path / ".research-local")
    assert run(Service(tmp_path, connector), dict(task_id=tid))["status"] == "complete"


def test_completed_task_checks_original_integrity(tmp_path):
    service, _, tid, iid = task(tmp_path)
    result = run(service, dict(task_id=tid, submissions={iid: dict(records=[FACT], review=REVIEW)}))
    assert result["status"] == "complete"
    document, _ = service.repo.document(result["items"][0]["document_id"])
    service.repo.path(document["path"]).write_text("changed")
    with pytest.raises(DomainError):
        status(service, dict(task_id=tid))


def test_cross_object_candidates_are_rejected(tmp_path):
    service, _, tid, iid = task(tmp_path)
    result = run(
        service,
        dict(
            task_id=tid,
            submissions={iid: dict(records=[dict(FACT, company_id="other")], review=REVIEW)},
        ),
    )
    assert result["items"][0]["issue"]["code"] == "SUBJECT_MISMATCH"
    assert service.repo.batches() == []


def test_changed_provider_requires_new_discovery(tmp_path):
    service, _, tid, _ = task(tmp_path)
    path = tmp_path / "research/source-providers/reports/provider.yaml"
    data = yaml.safe_load(path.read_text())
    data["url"] = "https://example.invalid/other/{page}"
    path.write_text(yaml.safe_dump(data))
    assert status(service, dict(task_id=tid))["status"] == "pending"
    result = run(service, dict(task_id=tid))
    assert result["items"][0]["issue"]["code"] == "SOURCE_CONFIG_CHANGED"


def test_manifest_does_not_allow_injected_url(tmp_path):
    service, _, tid, _ = task(tmp_path)
    path = tmp_path / BASE / tid / "plan.json"
    data = json.loads(path.read_text())
    data["items"][0]["url"] = "https://other.invalid/x.pdf"
    path.write_text(json.dumps(data))
    with pytest.raises(DomainError) as error:
        run(service, dict(task_id=tid))
    assert error.value.code == "TASK_CHANGED"


def test_provider_redirect_scope_is_preserved():
    request = Request("https://example.invalid/a")
    setattr(request, "_research_allowed_hosts", ("example.invalid",))
    with pytest.raises(ConnectorError) as error:
        _SafeRedirect().redirect_request(
            request, None, 302, "Moved", Message(), "https://other.invalid/a"
        )
    assert error.value.code == "SOURCE_REDIRECT_DENIED"
    moved = _SafeRedirect().redirect_request(
        request, None, 302, "Moved", Message(), "https://example.invalid/b"
    )
    assert getattr(moved, "_research_allowed_hosts") == ("example.invalid",)


def test_retry_after_is_available_for_persisted_scheduling(tmp_path):
    source = SourceDefinition(
        source_id="sample",
        url="https://example.invalid/a",
        archive_permissions="allowed",
        max_attempts=1,
    )
    headers = Message()
    headers["Retry-After"] = "120"
    fetcher = HttpFetcher(opener=Opener(HTTPError(source.url, 429, "slow", headers, None)))
    with pytest.raises(ConnectorError) as error:
        fetcher.fetch(source, {}, tmp_path)
    assert error.value.retryable and error.value.retry_after_seconds == 120


def test_shared_provider_cooldown_survives_local_cache_removal(tmp_path):
    config(tmp_path)

    class RateLimited(FakeConnector):
        def execute(self, operation, payload):
            self.calls.append((operation, payload))
            raise ConnectorError(
                "SOURCE_RATE_LIMITED", "slow", retryable=True, retry_after_seconds=120
            )

    connector = RateLimited(tmp_path)
    service = Service(tmp_path, connector)
    result = discover(service, dict(binding_id="demo-reports", parameters=dict(page=1)))
    assert result["status"] == "blocked"
    shutil.rmtree(tmp_path / ".research-local", ignore_errors=True)
    retried = discover(
        Service(tmp_path, connector), dict(binding_id="demo-reports", parameters=dict(page=2))
    )
    assert retried["issues"][0]["code"] == "SOURCE_RETRY_PENDING"
    assert len(connector.calls) == 1


def test_persisted_review_tampering_is_rejected(tmp_path, monkeypatch):
    service, connector, tid, iid = task(tmp_path)

    def fail(payload):
        raise DomainError("TEMPORARY_ADMISSION_FAILURE", "simulate failure after review")

    monkeypatch.setattr(service, "_ingest_apply", fail)
    result = run(service, dict(task_id=tid, submissions={iid: dict(records=[FACT], review=REVIEW)}))
    ref = result["items"][0]["review_refs"][0]
    path = service.repo.path(ref)
    review = json.loads(path.read_text())
    review["reviewer"] = "changed"
    path.write_text(json.dumps(review))
    shutil.rmtree(tmp_path / ".research-local")
    result = run(Service(tmp_path, connector), dict(task_id=tid))
    assert result["items"][0]["issue"]["code"] == "REVIEW_CHANGED"
    assert service.repo.batches() == []


def test_date_window_is_bounded_and_does_not_claim_calendar_coverage(tmp_path):
    config(
        tmp_path,
        url="https://example.invalid/{year}/{month}/{day}/d{yyyymmdd}.pdf",
        allowed_parameters=["date"],
        discovery_mode="date_window",
        window_days=2,
    )
    response = discover_page(
        tmp_path,
        HttpFetcher(opener=Opener()),
        dict(binding_id="demo-reports", parameters=dict(start="2024-02-28", end="2024-03-02")),
    )
    assert response["delivery"] is None
    assert response["entries"][1]["url"] == "https://example.invalid/2024/02/29/d20240229.pdf"
    assert response["next_parameters"] == dict(start="2024-03-01", end="2024-03-02")
    from investment_connectors import ConnectorService

    result = discover(
        Service(tmp_path, ConnectorService(tmp_path, fetcher=HttpFetcher(opener=Opener()))),
        dict(
            binding_id="demo-reports",
            parameters=dict(start="2024-02-28", end="2024-03-02"),
            max_pages=2,
        ),
    )
    assert len(result["entries"]) == 4 and result["next_parameters"] is None
    assert result["scope"] == "configured_date_requests_not_calendar_or_source_coverage"


def test_explicit_archive_reuse_has_no_network_fetch(tmp_path):
    service, connector, tid, iid = task(tmp_path)
    # Prior successful archive at the exact discovered URL can be explicitly reused.
    raw = tmp_path / "prior.txt"
    raw.write_text(FACT["excerpt"])
    service._import(
        dict(
            path=str(raw),
            source_id="earlier-binding",
            origin_url="https://example.invalid/report-1.pdf",
        )
    )
    result = run(service, dict(task_id=tid, reuse_archived=True))
    assert result["items"][0]["retrieval_mode"] == "explicit_archived_version_reuse"
    assert not [call for call in connector.calls if call[0] == "collect_item"]
    assert result["items"][0]["stage"] == "awaiting_extraction"


def test_form_post_preserves_bound_scope_and_heading_context(tmp_path):
    from urllib.parse import parse_qs

    from investment_connectors.providers import Links

    class Capture:
        def open(self, request, timeout):
            assert request.get_method() == "POST"
            assert request.full_url == "https://example.invalid/search?lang=en"
            assert parse_qs(request.data.decode()) == {"stockId": ["7609"], "title": ["DIVIDEND"]}
            return Response(b"<html>Official records</html>", "text/html")

    source = SourceDefinition(
        source_id="fixture",
        url="https://example.invalid/search?lang=en",
        connector_id="http-html-v1",
        dataset_id="document-facts",
        archive_permissions="allowed",
        request_method="POST",
        allowed_parameters=("stockId", "title"),
        fixed_parameters={"stockId": "7609"},
    )
    fetcher = HttpFetcher(opener=Capture())
    fetcher.fetch(source, {"title": "DIVIDEND"}, tmp_path)
    with pytest.raises(ConnectorError, match="cannot be overridden"):
        fetcher.fetch(source, {"stockId": "other"}, tmp_path)
    links = Links()
    links.feed(
        '<h2>2025</h2><h3>Q1</h3><a href="a.pdf" title="2025-Q1.pdf">Announcement</a><h2>2024</h2><h3>Q4</h3><a href="b.pdf">Announcement</a>'
    )
    assert links.links[0]["context"] == "2025 | Q1"
    assert links.links[0]["source_title"] == "2025-Q1.pdf"
    assert links.links[1]["context"] == "2024 | Q4"


def test_shared_original_generic_extraction_but_fixed_parser_stays_typed(tmp_path):
    config(tmp_path)
    service = Service(tmp_path, FakeConnector(tmp_path))
    raw = tmp_path / "original.txt"
    raw.write_text("Evidence")
    doc = service._import(dict(path=str(raw), source_id="first-binding"))["document_id"]
    prepared = service._prepare(
        dict(
            document_id=doc,
            dataset_id="corporate-actions",
            parser_source_id="demo-reports",
            records=[{"security_id": "demo", "excerpt": "Evidence"}],
        )
    )
    candidate = service._candidate(prepared["candidate_id"])
    assert candidate["document_source_id"] == "first-binding"
    assert candidate["parser_source_id"] == "demo-reports"
    p = tmp_path / "research/source-providers/reports/provider.yaml"
    source = yaml.safe_load(p.read_text())
    source.update(connector_id="http-csv-v1", dataset_id="daily-prices")
    p.write_text(yaml.safe_dump(source))
    with pytest.raises(DomainError) as error:
        service._prepare(
            dict(
                document_id=doc,
                dataset_id="corporate-actions",
                parser_source_id="demo-reports",
                records=[{"security_id": "demo", "excerpt": "Evidence"}],
            )
        )
    assert error.value.code == "SOURCE_DATASET_MISMATCH"


def test_non_relevant_discovery_item_is_explicitly_skipped_and_portable(tmp_path):
    service, connector, tid, iid = task(tmp_path)
    result = run(
        service,
        dict(
            task_id=tid,
            submissions={iid: {"skip_reason": "AGM poll result is not a financial statement"}},
        ),
    )
    assert result["status"] == "completed_with_skips"
    assert not [call for call in connector.calls if call[0] == "collect_item"]
    shutil.rmtree(tmp_path / ".research-local")
    restored = status(Service(tmp_path, connector), dict(task_id=tid))
    assert restored["items"][0]["skip_reason"].startswith("AGM")
    assert restored["status"] != "complete"
    with pytest.raises(DomainError):
        run(service, dict(task_id=tid, submissions={iid: {"records": [FACT]}}))


def test_verified_item_cannot_be_skipped(tmp_path):
    service, _, tid, iid = task(tmp_path)
    completed = run(
        service, dict(task_id=tid, submissions={iid: {"records": [FACT], "review": REVIEW}})
    )
    assert completed["status"] == "complete"
    with pytest.raises(DomainError, match="unapproved"):
        run(service, dict(task_id=tid, submissions={iid: {"skip_reason": "hide already ingested"}}))
    assert status(service, dict(task_id=tid))["status"] == "complete"
