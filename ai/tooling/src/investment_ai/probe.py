"""Read-only CLI evidence for explicit Skill invocation, never native discovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .manager import HostManager, encoded

SKILLS = ("data-planning", "data-acquisition", "data-review")
ALLOWED_REQUEST_FIELDS = {
    "dataset_id",
    "subject_id",
    "start",
    "end",
    "expectation_path",
    "source_id",
    "price_basis",
    "metric_id",
    "document_kind",
    "knowledge_mode",
    "information_cutoff",
    "as_of",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def invoke(workspace: Path, args: list[str], request: dict[str, Any] | None = None) -> dict:
    command = [
        sys.executable,
        "-m",
        "investment_cli",
        "--workspace",
        str(workspace),
        *args,
        "--json",
    ]
    if request is not None:
        command.extend(["--request", "-"])
    process = subprocess.run(
        command,
        input=json.dumps(request) if request is not None else None,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("CLI did not return a JSON object") from exc
    if not isinstance(result, dict) or str(result.get("protocol_version")) != "1":
        raise ValueError("CLI protocol is missing or unsupported")
    return {
        "command": ["research", *args, "--json"],
        "exit_code": process.returncode,
        "status": result.get("status"),
        "response_sha256": sha(process.stdout.encode()),
        "issues": result.get("issues", []),
        "result": result,
    }


def probe(workspace: Path, request: dict[str, Any], operation: str = "detect-gaps") -> dict:
    if operation not in {"detect-gaps", "coverage"}:
        raise ValueError("Probe only supports read-only detect-gaps or coverage")
    if set(request) - ALLOWED_REQUEST_FIELDS:
        raise ValueError("Probe only accepts data-gap query fields; no execution or secret fields")
    manager = HostManager(workspace)
    skills = []
    for name in SKILLS:
        relative = f"ai/skills/{name}/SKILL.md"
        content = manager.read(relative)
        if content is None:
            raise ValueError(f"Canonical Skill missing: {name}")
        skills.append({"skill_id": name, "path": relative, "sha256": sha(content)})
    capability = invoke(manager.root, ["capabilities"])
    if capability["exit_code"] != 0:
        raise ValueError("CLI capability discovery failed")
    # Actual command execution is the compatibility check, not a guessed capabilities layout.
    gaps = invoke(manager.root, ["data", operation], request)
    if gaps["exit_code"] not in {0, 3} or gaps["status"] in {None, "error", "failed"}:
        raise ValueError("Gap query failed; no successful invocation evidence recorded")
    report = {
        "protocol_version": "1",
        "verification_id": uuid.uuid4().hex,
        "recorded_at": datetime.now(UTC).isoformat(),
        "mode": "explicit_read_and_cli",
        "native_discovery": "not_tested",
        "host_identity": "not_attested",
        "semantic_accuracy": "not_tested",
        "skills": skills,
        "request_sha256": sha(encoded(request)),
        "invocation": "verified",
        "data_readiness": gaps["status"],
        "completeness": "not_assessed" if operation == "coverage" else "see_gap_result",
        "steps": [capability, gaps],
    }
    relative = f".research-local/ai-verification/{report['verification_id']}.json"
    manager.write(relative, encoded(report))
    return {
        "protocol_version": "1",
        "status": "ok",
        "invocation": "verified",
        "native_discovery": "not_tested",
        "data_readiness": gaps["status"],
        "completeness": "not_assessed" if operation == "coverage" else "see_gap_result",
        "report_path": relative,
        "report_sha256": sha(encoded(report)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--operation", choices=["detect-gaps", "coverage"], default="detect-gaps")
    args = parser.parse_args()
    try:
        request = json.loads(args.request.read_text())
        if not isinstance(request, dict):
            raise ValueError("Request must be an object")
        result = probe(args.workspace, request, args.operation)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
