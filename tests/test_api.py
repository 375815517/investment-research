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
