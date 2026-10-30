"""CLI transport: parse a request, invoke a service, render a result."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, NoReturn


class RequestError(Exception):
    def __init__(self, message: str, code: str = "invalid_request", exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise RequestError(message)


def common(parser: argparse.ArgumentParser) -> None:
    # SUPPRESS prevents a child's defaults from erasing parent options.
    parser.add_argument("--workspace", default=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)


def request_options(parser: argparse.ArgumentParser) -> None:
    common(parser)
    parser.add_argument("--request", help="JSON object file, or '-' for stdin")


def build_parser() -> Parser:
    parser = Parser(prog="research", description="Research data and host operations")
    common(parser)
    parser.add_argument("--version", action="store_true")
    commands = parser.add_subparsers(dest="command")
    for name in ("doctor", "capabilities"):
        common(commands.add_parser(name))
    schema = commands.add_parser("schema")
    common(schema)
    schema.add_argument("contract", nargs="?")

    data = commands.add_parser("data")
    common(data)
    operations = data.add_subparsers(dest="action", required=True)
    fields = {
        "import": ("path", "source_id", "published_at", "title"),
        "prepare": ("document_id", "dataset_id", "parser_version"),
        "collect": ("source_id", "published_at"),
        "validate": ("candidate_id",),
        "review": ("candidate_id", "reviewer", "decision", "notes"),
        "coverage": (
            "dataset_id",
            "subject_id",
            "start",
            "end",
            "information_cutoff",
            "knowledge_mode",
        ),
        "detect-gaps": (
            "dataset_id",
            "subject_id",
            "start",
            "end",
            "expectation_path",
            "source_id",
            "knowledge_mode",
            "information_cutoff",
            "as_of",
        ),
        "ensure-plan": (
            "dataset_id",
            "subject_id",
            "start",
            "end",
            "expectation_path",
            "source_id",
            "knowledge_mode",
            "information_cutoff",
            "as_of",
        ),
        "ensure-apply": ("plan_id",),
        "ingest": ("candidate_id", "plan_id"),
        "index": (),
    }
    for name, names in fields.items():
        child = operations.add_parser(name)
        request_options(child)
        for field in names:
            child.add_argument("--" + field.replace("_", "-"))
        if name == "ingest":
            modes = child.add_mutually_exclusive_group(required=True)
            modes.add_argument("--dry-run", action="store_true")
            modes.add_argument("--apply", action="store_true")
        if name == "index":
            child.add_argument("--rebuild", action="store_true")

    source = commands.add_parser("source")
    common(source)
    source_actions = source.add_subparsers(dest="action", required=True)
    source_check = source_actions.add_parser("check")
    request_options(source_check)
    source_check.add_argument("--source-id")

    operation = commands.add_parser("operation")
    common(operation)
    actions = operation.add_subparsers(dest="action", required=True)
    for name in ("status", "resume"):
        child = actions.add_parser(name)
        request_options(child)
        child.add_argument("operation_id", nargs="?")

    host = commands.add_parser("host")
    common(host)
    host_operations = host.add_subparsers(dest="action", required=True)
    for name in ("inspect", "plan", "apply", "verify", "sync", "repair", "uninstall"):
        child = host_operations.add_parser(name)
        request_options(child)
        child.add_argument("--host", choices=("codex", "codebuddy"))
        child.add_argument("--plan-id")
        child.add_argument("--save", action="store_true", default=None)
    return parser


def is_workspace(path: Path) -> bool:
    config = path / "pyproject.toml"
    if config.is_file():
        try:
            with config.open("rb") as stream:
                value = tomllib.load(stream)
            if "investment-research" in value.get("tool", {}):
                return True
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return (path / "AGENTS.md").is_file() and (
        path / "docs/architecture/input-data-baseline.md"
    ).is_file()


def find_workspace(explicit: str | None) -> Path:
    selected = explicit or os.environ.get("RESEARCH_WORKSPACE")
    if selected:
        path = Path(selected).expanduser().resolve()
        if not is_workspace(path):
            raise RequestError(f"Not a research workspace: {path}", "workspace_not_found")
        return path
    here = Path.cwd().resolve()
    for path in (here, *here.parents):
        if is_workspace(path):
            return path
    raise RequestError("Use --workspace to select a research repository", "workspace_not_found")


def payload_from(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    filename = getattr(args, "request", None)
    if filename:
        try:
            raw = sys.stdin.read() if filename == "-" else Path(filename).read_text()
            parsed = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RequestError("Cannot read a valid JSON request object") from exc
        if not isinstance(parsed, dict):
            raise RequestError("Request must be a JSON object")
        payload.update(parsed)
    ignored = {
        "workspace",
        "json",
        "version",
        "command",
        "action",
        "request",
        "dry_run",
        "apply",
        "rebuild",
        "contract",
    }
    for key, value in vars(args).items():
        if key not in ignored and value is not None:
            payload[key] = value
    # Workspace is execution context, never an overridable request field.
    if "workspace" in payload:
        raise RequestError("Select the workspace using --workspace, not request JSON")
    return payload


def invoke(workspace: Path, operation: str, payload: dict[str, Any], host: bool = False) -> dict:
    if host:
        from investment_ai import HostManager

        return HostManager(workspace).execute(operation, payload)
    from investment_connectors import ConnectorService
    from investment_engine import Service

    return Service(workspace, connector_service=ConnectorService(workspace)).execute(
        operation, payload
    )


def package_version() -> str:
    try:
        return version("investment-cli")
    except PackageNotFoundError:
        return "0.1.0+source"


def dispatch(args: argparse.Namespace) -> dict:
    if args.version:
        return {"protocol_version": "1", "status": "ok", "version": package_version()}
    if args.command is None:
        raise RequestError("Choose a command; use --help for available operations")
    workspace = find_workspace(getattr(args, "workspace", None))
    if args.command == "doctor":
        capability = invoke(workspace, "capabilities", {})
        return {
            "protocol_version": "1",
            "status": "ok",
            "summary": "Workspace and application service are available; network not checked",
            "workspace": str(workspace),
            "tool_version": package_version(),
            "checks": {"workspace": "verified", "network": "not_checked"},
            "capabilities": capability,
            "issues": [],
            "artifact_refs": [],
            "next_actions": [],
        }
    if args.command == "schema":
        return invoke(workspace, "schema", {"contract": args.contract} if args.contract else {})
    if args.command == "capabilities":
        return invoke(workspace, "capabilities", {})
    payload = payload_from(args)
    if args.command == "host":
        return invoke(workspace, args.action, payload, host=True)
    action = args.action.replace("-", "_")
    if args.command == "source":
        action = "source_check"
    if args.command == "data" and action == "ingest":
        action = "ingest_plan" if args.dry_run else "ingest_apply"
    return invoke(workspace, action, payload)


def result_exit_code(result: dict) -> int:
    status = result.get("status", "")
    if status in {
        "needs_review",
        "review_required",
        "blocked",
        "partial",
        "quarantined",
        "invalid",
    }:
        return 3
    if status in {"conflict", "stale_plan"}:
        return 4
    if status in {"failed", "error"}:
        return 1
    return 0


def render(result: dict, machine: bool) -> None:
    if machine:
        print(json.dumps(result, ensure_ascii=False, default=str))
        return
    print(result.get("summary") or f"Status: {result.get('status', 'unknown')}")
    # Human output remains complete, rather than hiding IDs needed for the next command.
    detail = {key: value for key, value in result.items() if key != "summary"}
    print(json.dumps(detail, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    machine = "--json" in arguments
    try:
        args = build_parser().parse_args(arguments)
        machine = getattr(args, "json", False)
        result = dispatch(args)
        render(result, machine)
        return result_exit_code(result)
    except KeyboardInterrupt:
        error = RequestError(
            "Operation interrupted; inspect its status before resuming", "interrupted", 130
        )
    except Exception as exc:
        if all(hasattr(exc, name) for name in ("code", "message", "exit_code")):
            error = RequestError(
                str(getattr(exc, "message")),
                str(getattr(exc, "code")),
                int(getattr(exc, "exit_code")),
            )
        else:
            # Do not leak credentials, source response bodies or arbitrary exception text.
            error = RequestError(
                "Unexpected internal failure; inspect operation records", "internal_error", 1
            )
    result = {
        "protocol_version": "1",
        "status": "error",
        "summary": error.message,
        "artifact_refs": [],
        "issues": [{"code": error.code, "message": error.message}],
        "next_actions": [],
    }
    render(result, machine)
    return error.exit_code
