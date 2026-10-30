"""The explicit CLI probe must not claim data completion or native discovery."""

import json
import subprocess
from typing import Any
from pathlib import Path

import pytest

from investment_ai.probe import SKILLS, invoke, probe


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("entry")
    for skill in SKILLS:
        folder = tmp_path / "ai/skills" / skill
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {skill}\n---\nInstruction\n")
    return tmp_path


def test_probe_preserves_unresolved_data_and_never_claims_discovery(workspace, monkeypatch):
    calls = []

    def command(args, **kwargs):
        calls.append((args, kwargs))
        payload: dict[str, Any] = {"protocol_version": "1", "status": "ok", "issues": []}
        code = 0
        if "detect-gaps" in args:
            payload.update(status="blocked", issues=[{"code": "unknown_expectation"}])
            code = 3
        return subprocess.CompletedProcess(args, code, json.dumps(payload), "")

    monkeypatch.setattr(subprocess, "run", command)
    result = probe(workspace, {"dataset_id": "daily-prices", "subject_id": "demo"})
    assert result["invocation"] == "verified"
    assert result["data_readiness"] == "blocked"
    assert result["native_discovery"] == "not_tested"
    report = json.loads((workspace / result["report_path"]).read_text())
    assert report["steps"][1]["exit_code"] == 3
    assert report["semantic_accuracy"] == "not_tested"
    assert report["host_identity"] == "not_attested"
    assert len(report["skills"]) == 3
    assert len(calls) == 2
    assert all("ensure-apply" not in args for args, _ in calls)
    assert not (workspace / "data").exists()
    assert not (workspace / ".agents").exists()


def test_contract_error_does_not_create_success_evidence(workspace, monkeypatch):
    def command(args, **kwargs):
        error = "detect-gaps" in args
        value = {"protocol_version": "1", "status": "error" if error else "ok"}
        return subprocess.CompletedProcess(args, 2 if error else 0, json.dumps(value), "")

    monkeypatch.setattr(subprocess, "run", command)
    with pytest.raises(ValueError, match="Gap query failed"):
        probe(workspace, {})
    assert not (workspace / ".research-local").exists()


def test_unsupported_protocol_rejected(workspace, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(
            args, 0, '{"protocol_version":"2","status":"ok"}', ""
        ),
    )
    with pytest.raises(ValueError, match="protocol"):
        invoke(workspace, ["capabilities"])


def test_secret_or_execution_fields_rejected_before_cli(workspace, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("CLI must not be called")

    monkeypatch.setattr(subprocess, "run", unexpected)
    with pytest.raises(ValueError, match="only accepts"):
        probe(workspace, {"acquisition": {"secret": "not-a-real-secret"}})


def test_non_json_cli_result_rejected(workspace, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(args, 0, "progress before JSON", ""),
    )
    with pytest.raises(ValueError, match="JSON object"):
        invoke(workspace, ["capabilities"])
