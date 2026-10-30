"""Transport tests isolate all data mutation behind the application service."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

cli = importlib.import_module("investment_cli.main")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "pyproject.toml").write_text("[tool.investment-research]\nschema-version = 1\n")
    return root


def test_workspace_precedence_and_nested_discovery(workspace, tmp_path, monkeypatch):
    nested = workspace / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    monkeypatch.delenv("RESEARCH_WORKSPACE", raising=False)
    assert cli.find_workspace(None) == workspace
    monkeypatch.setenv("RESEARCH_WORKSPACE", str(tmp_path / "wrong"))
    assert cli.find_workspace(str(workspace)) == workspace
    with pytest.raises(cli.RequestError):
        cli.find_workspace(None)


def test_json_request_dispatch_from_other_directory(workspace, tmp_path, monkeypatch, capsys):
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"candidate_id": "candidate-1"}))
    monkeypatch.chdir(tmp_path)
    calls = []

    def invoke(root, operation, payload, host=False):
        calls.append((root, operation, payload))
        return {"status": "ok", "operation_id": "op-1"}

    monkeypatch.setattr(cli, "invoke", invoke)
    assert (
        cli.main(
            ["--workspace", str(workspace), "data", "validate", "--request", str(request), "--json"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["operation_id"] == "op-1"
    assert calls == [(workspace, "validate", {"candidate_id": "candidate-1"})]


def test_failed_requests_return_one_json_without_service_call(workspace, monkeypatch, capsys):
    monkeypatch.setattr(cli, "invoke", lambda *a, **k: pytest.fail("must not call service"))
    assert cli.main(["--json", "--workspace", str(workspace), "data", "ingest"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["issues"][0]["code"] == "invalid_request"


def test_request_cannot_override_workspace(workspace, tmp_path, capsys):
    request = tmp_path / "bad.json"
    request.write_text('{"workspace": "/other"}')
    assert (
        cli.main(
            ["data", "import", "--request", str(request), "--workspace", str(workspace), "--json"]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["issues"][0]["code"] == "invalid_request"


def test_apply_and_host_are_thin_calls(workspace, monkeypatch, capsys):
    calls = []

    def invoke(root, operation, payload, host=False):
        calls.append((operation, payload, host))
        return {"status": "noop"}

    monkeypatch.setattr(cli, "invoke", invoke)
    common = ["--workspace", str(workspace), "--json"]
    assert cli.main(common + ["data", "ingest", "--apply", "--plan-id", "p1"]) == 0
    assert cli.main(common + ["host", "verify", "--host", "codex"]) == 0
    assert calls == [
        ("ingest_apply", {"plan_id": "p1"}, False),
        ("verify", {"host": "codex"}, True),
    ]
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_status_query_success_distinct_from_task_failure(workspace, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "invoke", lambda *a, **k: {"status": "ok", "operation_status": "failed"}
    )
    assert cli.main(["operation", "status", "op-1", "--workspace", str(workspace), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["operation_status"] == "failed"


def test_internal_errors_do_not_disclose_exception_secrets(workspace, monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise RuntimeError("api-key-secret-value")

    monkeypatch.setattr(cli, "invoke", broken)
    assert cli.main(["capabilities", "--workspace", str(workspace), "--json"]) == 1
    output = capsys.readouterr().out
    assert "api-key-secret-value" not in output
    assert json.loads(output)["issues"][0]["code"] == "internal_error"


@pytest.mark.parametrize("contents", ["[]", "null", '"text"', "{broken"])
def test_non_object_and_malformed_requests(workspace, tmp_path, monkeypatch, capsys, contents):
    request = tmp_path / "request.json"
    request.write_text(contents)
    monkeypatch.setattr(cli, "invoke", lambda *a, **k: pytest.fail("must not invoke service"))
    assert (
        cli.main(
            ["data", "import", "--request", str(request), "--workspace", str(workspace), "--json"]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["issues"][0]["code"] == "invalid_request"
