"""Transport boundaries: API cannot choose a workspace or arbitrary network URL."""

import json

import pytest
from fastapi.testclient import TestClient

from investment_api import create_app

HEADERS = {"X-Research-Client": "data-ui"}


class Engine:
    def __init__(self):
        self.calls = []

    def execute(self, operation, payload):
        self.calls.append((operation, payload))
        return {"status": "complete", "rows": [], "plan_id": "plan-test"}


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "research/datasets/calendar.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "expectation_id": "test-calendar",
                "dataset_id": "daily-prices",
                "subject_id": "xiaomi-hk",
                "start": "2026-10-26",
                "end": "2026-10-29",
                "items": [],
            }
        )
    )
    engine = Engine()
    return TestClient(create_app(tmp_path, engine)), engine, tmp_path


def request_body():
    return {
        "dataset_id": "daily-prices",
        "subject_id": "xiaomi-hk",
        "start": "2026-10-26",
        "end": "2026-10-29",
        "expectation_path": "research/datasets/calendar.json",
        "price_basis": "provider-native",
    }


def test_read_routes_and_expectations(setup):
    client, engine, _ = setup
    assert client.get("/api/coverage?price_basis=provider-native").status_code == 200
    assert engine.calls[-1] == (
        "coverage",
        {
            "dataset_id": "daily-prices",
            "price_basis": "provider-native",
            "knowledge_mode": "retrospective_explanation",
        },
    )
    catalog = client.get("/api/catalog").json()
    assert catalog["expectations"][0]["start"] == "2026-10-26"
    assert client.get("/api/files", params={"path": "research/datasets/calendar.json"}).json()[
        "preview"
    ]


def test_gap_and_plan_use_same_engine(setup):
    client, engine, _ = setup
    payload = request_body()
    assert client.post("/api/gaps", json=payload, headers=HEADERS).status_code == 200
    assert engine.calls[-1][0] == "detect_gaps"
    assert engine.calls[-1][1]["price_basis"] == "provider-native"
    payload["acquisition"] = {"source_id": "approved-source", "parameters": {"symbol": "1810.HK"}}
    assert client.post("/api/ensure/plan", json=payload, headers=HEADERS).status_code == 200
    assert engine.calls[-1][0] == "ensure_plan"
    assert (
        client.post("/api/ensure/apply", json={"plan_id": "plan-test"}, headers=HEADERS).status_code
        == 200
    )
    assert engine.calls[-1] == ("ensure_apply", {"plan_id": "plan-test"})


def test_browser_and_operation_boundary(setup):
    client, engine, _ = setup
    assert client.post("/api/gaps", json=request_body()).status_code == 403
    assert (
        client.post(
            "/api/gaps", json=request_body(), headers={**HEADERS, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/import", json={}, headers=HEADERS).status_code == 404
    assert client.get("/api/catalog", headers={"host": "evil.example"}).status_code == 400
    assert not engine.calls


@pytest.mark.parametrize(
    "path", ["../secret", "/etc/passwd", ".env", "data/../secret", "ai/rules/common.md"]
)
def test_file_boundary(setup, path):
    client, _, _ = setup
    assert client.get("/api/files", params={"path": path}).status_code == 400


def test_symlink_and_payload_boundary(setup):
    client, engine, root = setup
    (root / "data").mkdir()
    (root / "data/secret").symlink_to("/etc/passwd")
    assert client.get("/api/files", params={"path": "data/secret"}).status_code == 400
    payload = request_body() | {"workspace": "/tmp/elsewhere"}
    assert client.post("/api/gaps", json=payload, headers=HEADERS).status_code == 422
    payload = request_body() | {
        "acquisition": {"source_id": "x", "parameters": {"url": "https://evil.example"}}
    }
    assert client.post("/api/ensure/plan", json=payload, headers=HEADERS).status_code == 400
    assert (
        client.post(
            "/api/gaps",
            content="x" * 70000,
            headers={**HEADERS, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert not engine.calls


@pytest.mark.parametrize("dataset", ["document-facts", "market-observations"])
def test_multi_source_query_is_transported_without_computation(setup, dataset):
    client, engine, _ = setup
    query = {
        "dataset_id": dataset,
        "subject_id": "xiaomi",
        "source_id": "company-disclosure",
        "metric_id": "market-cap",
        "document_kind": "company-announcement",
        "start": "2026-01-01",
        "end": "2026-10-30",
    }
    assert client.get("/api/coverage", params=query).status_code == 200
    assert engine.calls[-1][0] == "coverage"
    for key, value in query.items():
        assert engine.calls[-1][1][key] == value


def test_catalog_exposes_explicit_source_subject_and_category(setup):
    client, _, root = setup
    source = root / "research/sources/policy/source.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(
        "source_id: policy\nname: 政府政策\ndataset_id: document-facts\nsubject_id: china\nsubject_type: jurisdiction\nsource_category: policy\n"
    )
    result = client.get("/api/catalog").json()
    assert result["sources"][0]["subject_id"] == "china"
    assert result["sources"][0]["category"] == "policy"


def test_audit_contract_delegates_and_bounds_requirements(setup):
    client, engine, _ = setup
    requirement = {
        "dataset_id": "document-facts",
        "subject_id": "xiaomi",
        "start": "2026-01-01",
        "end": "2026-10-30",
        "minimum_records": 1,
    }
    response = client.post(
        "/api/audit-inputs", json={"requirements": [requirement]}, headers=HEADERS
    )
    assert response.status_code == 200
    assert engine.calls[-1][0] == "audit_inputs"
    assert engine.calls[-1][1]["requirements"][0]["dataset_id"] == "document-facts"
    assert (
        client.post(
            "/api/audit-inputs", json={"requirements": [requirement] * 101}, headers=HEADERS
        ).status_code
        == 422
    )


def test_assessment_contract_delegates_and_rejects_invalid_purpose(setup):
    client, engine, _ = setup
    requirement = {
        "dataset_id": "market-observations",
        "subject_id": "xiaomi-hk",
        "start": "2026-01-01",
        "end": "2026-10-30",
        "metric_id": "pe_provider",
    }
    payload = {"requirements": [requirement], "purpose": "quantitative_comparison"}
    response = client.post("/api/assess-inputs", json=payload, headers=HEADERS)
    assert response.status_code == 200
    operation, transported = engine.calls[-1]
    assert operation == "assess_inputs"
    assert transported["purpose"] == "quantitative_comparison"
    assert transported["requirements"][0]["metric_id"] == "pe_provider"
    count = len(engine.calls)
    for change in (
        {"purpose": "guaranteed_returns"},
        {"purpose": "historical_point_in_time"},
        {"requirements": [requirement] * 101},
        {"workspace": "/tmp/elsewhere"},
    ):
        assert (
            client.post("/api/assess-inputs", json=payload | change, headers=HEADERS).status_code
            == 422
        )
    assert len(engine.calls) == count


def test_historical_assessment_preserves_cutoff_and_browser_boundary(setup):
    client, engine, _ = setup
    payload = {
        "requirements": [
            {
                "dataset_id": "document-facts",
                "subject_id": "xiaomi",
                "start": "2025-01-01",
                "end": "2025-12-31",
            }
        ],
        "purpose": "historical_point_in_time",
        "knowledge_mode": "historical_reconstruction",
        "information_cutoff": "2025-12-31T23:59:59Z",
    }
    assert client.post("/api/assess-inputs", json=payload).status_code == 403
    response = client.post("/api/assess-inputs", json=payload, headers=HEADERS)
    assert response.status_code == 200
    assert engine.calls[-1][1]["information_cutoff"] == payload["information_cutoff"]
    assert engine.calls[-1][1]["knowledge_mode"] == "historical_reconstruction"


def test_catalog_preview_limit_does_not_hide_configuration(setup):
    client, _, root = setup
    archive = root / "data/inputs/archive"
    archive.mkdir(parents=True)
    for number in range(2001):
        (archive / f"{number:04}.txt").write_text("archived source")
    security = root / "data/inputs/securities/xiaomi-hk/security.json"
    security.parent.mkdir(parents=True)
    security.write_text(json.dumps({"security_id": "xiaomi-hk", "user_confirmed": True}))
    source = root / "research/sources/source/source.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("source_id: source\nname: Test source\n")
    policy = root / "research/coverage-policies/test.json"
    policy.parent.mkdir(parents=True)
    policy.write_text(json.dumps({"requirements": [{"dataset_id": "daily-prices"}]}))
    dataset = root / "research/datasets/prices/dataset.yaml"
    dataset.parent.mkdir(parents=True)
    dataset.write_text("dataset_id: daily-prices\n")
    result = client.get("/api/catalog").json()
    assert result["truncated"] is True
    assert len(result["entries"]) == 2000
    assert result["securities"][0]["id"] == "xiaomi-hk"
    assert result["sources"][0]["id"] == "source"
    assert result["audits"][0]["path"] == "research/coverage-policies/test.json"
    assert result["datasets"][0]["id"] == "daily-prices"
    assert result["expectations"][0]["path"] == "research/datasets/calendar.json"


def profile_payload():
    return {
        "profile_id": "sample",
        "purpose": "quantitative_comparison",
        "expected_keys": [
            {
                "key_id": "revenue-2024",
                "dataset_id": "financial-facts",
                "subject_id": "company",
                "selectors": {
                    "metric_id": "revenue",
                    "period_start": "2024-01-01",
                    "period_end": "2024-12-31",
                    "scope": "consolidated",
                    "currency": "CNY",
                },
            }
        ],
    }


def test_profile_path_uses_domain_contract_and_preserves_business_result(setup):
    client, engine, root = setup
    path = root / "research/input-profiles/sample/v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(profile_payload()))
    catalog = client.get("/api/catalog").json()
    assert catalog["profiles"] == [
        {
            "path": "research/input-profiles/sample/v1.json",
            "id": "sample",
            "name": "sample · v1",
            "count": 1,
        }
    ]
    payload = {"profile_path": "research/input-profiles/sample/v1.json"}
    for route, operation in [
        ("profile-audit", "profile_audit"),
        ("profile-assess", "profile_assess"),
    ]:
        assert client.post("/api/" + route, json=payload, headers=HEADERS).status_code == 200
        assert engine.calls[-1][0] == operation
        assert engine.calls[-1][1]["expected_keys"][0]["selectors"]["currency"] == "CNY"
        assert "profile_path" not in engine.calls[-1][1]
    for route, extra in [
        ("normalize-inputs", {"target_scale": "units"}),
        ("freeze-inputs", {"label": "run"}),
    ]:
        assert (
            client.post("/api/" + route, json=payload | extra, headers=HEADERS).status_code == 200
        )
        assert engine.calls[-1][1]["profile"]["profile_id"] == "sample"


def test_profile_path_boundary_and_historical_cutoff(setup):
    client, engine, root = setup
    path = root / "research/input-profiles/sample/v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(profile_payload()))
    for rel in [
        "data/secret.json",
        "research/datasets/calendar.json",
        "research/input-profiles/../../secret.json",
    ]:
        assert (
            client.post(
                "/api/profile-audit", json={"profile_path": rel}, headers=HEADERS
            ).status_code
            == 400
        )
    assert not engine.calls
    request = {
        "profile_path": "research/input-profiles/sample/v1.json",
        "knowledge_mode": "historical_reconstruction",
    }
    assert client.post("/api/profile-assess", json=request, headers=HEADERS).status_code == 422
    assert not engine.calls
    request["information_cutoff"] = "2025-04-01T00:00:00+08:00"
    assert client.post("/api/profile-assess", json=request, headers=HEADERS).status_code == 200
    assert engine.calls[-1][1]["information_cutoff"] == request["information_cutoff"]


def test_profile_path_supports_large_registered_profile_without_large_http_body(setup):
    client, engine, root = setup
    path = root / "research/input-profiles/sample/v1.json"
    path.parent.mkdir(parents=True)
    payload = profile_payload()
    template = payload["expected_keys"][0]
    payload["expected_keys"] = [dict(template, key_id=f"key-{index}") for index in range(2600)]
    path.write_text(json.dumps(payload))
    assert path.stat().st_size > 512 * 1024
    assert client.get("/api/catalog").json()["profiles"][0]["count"] == 2600
    assert (
        client.post(
            "/api/profile-audit",
            json={"profile_path": "research/input-profiles/sample/v1.json"},
            headers=HEADERS,
        ).status_code
        == 200
    )
    assert len(engine.calls[-1][1]["expected_keys"]) == 2600


def test_new_workflow_routes_are_bounded_and_do_not_expose_generic_execute(setup):
    client, engine, _ = setup
    for route, payload, operation in [
        (
            "source-discover",
            {"binding_id": "issuer", "parameters": {"year": 2024}},
            "source_discover",
        ),
        (
            "acquisition-plan",
            {"discovery_id": "discovery-one", "dataset_id": "financial-observations"},
            "acquisition_plan",
        ),
        ("acquisition-run", {"task_id": "task-one", "max_items": 1}, "acquisition_run"),
        ("acquisition-status", {"task_id": "task-one"}, "acquisition_status"),
        ("verify-bundle", {"bundle_id": "bundle-one"}, "verify_bundle"),
    ]:
        assert client.post("/api/" + route, json=payload, headers=HEADERS).status_code == 200
        assert engine.calls[-1][0] == operation
    count = len(engine.calls)
    for payload in [
        {"binding_id": "issuer", "parameters": {"url": "https://other.example"}},
        {"binding_id": "issuer", "parameters": {"auth_token": "sensitive"}},
    ]:
        assert client.post("/api/source-discover", json=payload, headers=HEADERS).status_code == 400
    assert (
        client.post(
            "/api/source-discover", json={"binding_id": "issuer", "max_pages": 21}, headers=HEADERS
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/acquisition-run", json={"task_id": "../../secret"}, headers=HEADERS
        ).status_code
        == 422
    )
    assert (
        client.post("/api/execute", json={"operation": "import"}, headers=HEADERS).status_code
        == 404
    )
    assert len(engine.calls) == count


def test_metadata_revision_transports_precision_without_guessing_time(setup):
    client, engine, _ = setup
    payload = {
        "document_id": "doc-one",
        "publication": {"precision": "date", "date": "2025-03-20", "timezone": "Asia/Hong_Kong"},
        "evidence_document_id": "doc-proof",
        "locator": "text:date",
        "excerpt": "2025-03-20",
        "reviewer": "reviewer",
        "notes": "Matched the announcement date",
    }
    assert client.post("/api/revise-metadata", json=payload, headers=HEADERS).status_code == 200
    assert engine.calls[-1][0] == "revise_metadata"
    assert engine.calls[-1][1]["publication"] == payload["publication"]
    count = len(engine.calls)
    payload["publication"]["published_at"] = "2025-03-20T00:00:00+08:00"
    assert client.post("/api/revise-metadata", json=payload, headers=HEADERS).status_code == 422
    assert len(engine.calls) == count


def test_profile_api_matches_shared_service_for_missing_required_input(tmp_path):
    from investment_engine import Service

    profile = profile_payload()
    client = TestClient(create_app(tmp_path))
    response = client.post("/api/profile-assess", json=profile, headers=HEADERS)
    assert response.status_code == 200
    result = response.json()
    direct = Service(tmp_path).execute("profile_assess", profile)
    assert result["status"] == direct["status"] == "blocked"
    assert result["audit"]["missing_key_ids"] == ["revenue-2024"]
    assert result["audit"]["keys"] == direct["audit"]["keys"]


def test_task_submission_exposes_supported_revisions_and_explicit_skips(setup):
    client, engine, _ = setup
    payload = {
        "task_id": "task-one",
        "max_items": 20,
        "submissions": {
            "skip-one": {"skip_reason": "Duplicate source item; retained in earlier archive"},
            "revision-one": {
                "records": [],
                "supersedes": ["record-old"],
                "parser_version": "reviewed-v2",
            },
        },
    }
    assert client.post("/api/acquisition-run", json=payload, headers=HEADERS).status_code == 200
    assert engine.calls[-1][1]["submissions"] == payload["submissions"]
    assert (
        client.post(
            "/api/acquisition-run", json={**payload, "max_items": 21}, headers=HEADERS
        ).status_code
        == 422
    )
