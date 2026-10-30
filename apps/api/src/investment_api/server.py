from __future__ import annotations

import argparse
import json
import mimetypes
import re

import yaml
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from investment_connectors import ConnectorService, ConnectorError
from investment_domain import DomainError, AuditInputsRequest, AssessInputsRequest
from investment_engine import Service

MAX_PREVIEW = 512 * 1024


class GapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=100)
    subject_id: str = Field(min_length=1, max_length=100)
    start: str = Field(min_length=10, max_length=10)
    end: str = Field(min_length=10, max_length=10)
    expectation_path: str = Field(min_length=1, max_length=500)
    price_basis: Literal[
        "unadjusted", "provider-native", "forward-adjusted", "backward-adjusted"
    ] = "unadjusted"
    source_id: str | None = None
    knowledge_mode: Literal[
        "retrospective_explanation", "historical_reconstruction", "live_observed"
    ] = "retrospective_explanation"
    information_cutoff: str | None = None
    as_of: str | None = None


class Acquisition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=100)
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class EnsureRequest(GapRequest):
    acquisition: Acquisition | None = None


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", max_length=200)


def safe_input_file(workspace: Path, relative: str) -> Path:
    candidate = Path(relative)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or candidate.parts[0] not in {"data", "research"}
    ):
        raise HTTPException(400, "File reference must be inside data/ or research/")
    if any(part in {"..", "."} or part.startswith(".") for part in candidate.parts):
        raise HTTPException(400, "Invalid file reference")
    path = workspace
    for part in candidate.parts:
        path = path / part
        if path.is_symlink():
            raise HTTPException(400, "Symlink file references are not supported")
    try:
        path.resolve().relative_to(workspace)
    except ValueError as exc:
        raise HTTPException(400, "File reference escapes workspace") from exc
    if not path.is_file():
        raise HTTPException(404, "Referenced file does not exist")
    return path


def validate_acquisition(value: Acquisition) -> None:
    # Network destinations and authentication are server-owned source definitions.
    denied = re.compile(
        r"url|endpoint|host|header|path|secret|password|token|auth|credential", re.I
    )
    if len(value.parameters) > 30 or any(denied.search(key) for key in value.parameters):
        raise HTTPException(400, "Only source-defined data parameters are accepted")
    if any(isinstance(v, str) and len(v) > 500 for v in value.parameters.values()):
        raise HTTPException(400, "Source parameter too long")


def create_app(workspace: Path, service: Any = None, web_root: Path | None = None) -> FastAPI:
    root = workspace.resolve()
    if not root.is_dir():
        raise ValueError("Workspace does not exist")
    connector = ConnectorService(root)
    engine = service or Service(root, connector_service=connector)
    app = FastAPI(title="投资研究输入工作台", docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def browser_boundary(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            length = request.headers.get("content-length")
            if length and (not length.isdecimal() or int(length) > 65536):
                return JSONResponse({"detail": "Request exceeds 64 KiB"}, status_code=413)
            if len(await request.body()) > 65536:
                return JSONResponse({"detail": "Request exceeds 64 KiB"}, status_code=413)
            if request.headers.get("x-research-client") != "data-ui":
                return JSONResponse(
                    {"detail": "Missing explicit local client header"}, status_code=403
                )
            origin = request.headers.get("origin")
            expected = urlsplit(str(request.base_url))
            if origin:
                actual = urlsplit(origin)
                if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
                    return JSONResponse(
                        {"detail": "Cross-origin writes are not allowed"}, status_code=403
                    )
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "JSON content type required"}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        )
        return response

    @app.exception_handler(ConnectorError)
    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        code = {2: 400, 3: 422, 4: 409, 5: 502}.get(exc.exit_code, 500)
        return JSONResponse(
            {
                "protocol_version": "1",
                "status": "error",
                "summary": exc.message,
                "issues": [{"code": exc.code, "message": exc.message}],
            },
            status_code=code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo invalid payload contents, which may contain credentials.
        return JSONResponse(
            {
                "protocol_version": "1",
                "status": "error",
                "issues": [
                    {
                        "code": "INVALID_REQUEST",
                        "message": "Request does not match the API contract",
                    }
                ],
            },
            status_code=422,
        )

    @app.get("/api/capabilities")
    def capabilities():
        result = engine.execute("capabilities", {})
        result["api_operations"] = [
            "coverage",
            "detect_gaps",
            "ensure_plan",
            "ensure_apply",
            "status",
            "audit_inputs",
            "assess_inputs",
        ]
        return result

    @app.get("/api/catalog")
    def catalog():
        entries: list[dict[str, Any]] = []
        securities = []
        sources = []
        expectations = []
        datasets = []
        audits = []
        truncated = False
        for dirname in (
            "data/inputs",
            "research/sources",
            "research/datasets",
            "research/coverage-policies",
        ):
            base = root / dirname
            for path in sorted(base.rglob("*")) if base.exists() else []:
                if not path.is_file() or path.name.startswith("."):
                    continue
                relative = path.relative_to(root).as_posix()
                try:
                    safe_input_file(root, relative)
                except HTTPException:
                    continue
                # The preview cap must not hide source, security or requirement metadata.
                if len(entries) < 2000:
                    entries.append(
                        {"path": relative, "name": path.name, "size": path.stat().st_size}
                    )
                else:
                    truncated = True
                if path.stat().st_size <= MAX_PREVIEW:
                    try:
                        value = (
                            yaml.safe_load(path.read_text())
                            if path.suffix in {".yaml", ".yml"}
                            else json.loads(path.read_text())
                        )
                        if isinstance(value, dict):
                            if dirname == "research/coverage-policies" and isinstance(
                                value.get("requirements"), list
                            ):
                                audits.append(
                                    {
                                        "path": relative,
                                        "name": path.stem,
                                        "count": len(value["requirements"]),
                                    }
                                )
                            if path.name == "dataset.yaml" and value.get("dataset_id"):
                                datasets.append(
                                    {
                                        "id": value["dataset_id"],
                                        "name": value.get("name", value["dataset_id"]),
                                        "record_grain": value.get("record_grain"),
                                        "status": value.get("status"),
                                    }
                                )
                            if path.name == "security.json" and value.get("security_id"):
                                securities.append(
                                    {
                                        "id": value["security_id"],
                                        "name": value.get("display_name", value["security_id"]),
                                        "company_id": value.get("company_id"),
                                        "confirmed": value.get("user_confirmed", False),
                                    }
                                )
                            if path.name == "source.yaml" and value.get("source_id"):
                                sources.append(
                                    {
                                        "id": value["source_id"],
                                        "name": value.get("name", value["source_id"]),
                                        "dataset_id": value.get("dataset_id"),
                                        "security_id": value.get("security_id"),
                                        "subject_id": value.get("subject_id"),
                                        "subject_type": value.get("subject_type"),
                                        "category": value.get(
                                            "source_category", value.get("document_kind")
                                        ),
                                        "limitations": value.get("known_limitations", []),
                                    }
                                )
                            if "expectation_id" in value and isinstance(value.get("items"), list):
                                expectations.append(
                                    {
                                        "path": relative,
                                        "name": f"{value['subject_id']} · {value['start']} 至 {value['end']} · {value['expectation_id']}",
                                        "dataset_id": value["dataset_id"],
                                        "subject_id": value["subject_id"],
                                        "start": value["start"],
                                        "end": value["end"],
                                    }
                                )
                    except (ValueError, UnicodeError, yaml.YAMLError):
                        pass
        return {
            "entries": entries,
            "securities": securities,
            "sources": sources,
            "expectations": expectations,
            "datasets": datasets,
            "audits": audits,
            "truncated": truncated,
        }

    @app.get("/api/coverage")
    def coverage(
        dataset_id: str = "daily-prices",
        subject_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        price_basis: str = "unadjusted",
        source_id: str | None = None,
        metric_id: str | None = None,
        document_kind: str | None = None,
        knowledge_mode: str = "retrospective_explanation",
        information_cutoff: str | None = None,
    ):
        payload = {
            key: value
            for key, value in {
                "dataset_id": dataset_id,
                "subject_id": subject_id,
                "start": start,
                "end": end,
                "price_basis": price_basis,
                "source_id": source_id,
                "metric_id": metric_id,
                "document_kind": document_kind,
                "knowledge_mode": knowledge_mode,
                "information_cutoff": information_cutoff,
            }.items()
            if value is not None
        }
        return engine.execute("coverage", payload)

    @app.post("/api/audit-inputs")
    def audit_inputs(request: AuditInputsRequest):
        return engine.execute("audit_inputs", request.model_dump(mode="json", exclude_none=True))

    @app.post("/api/assess-inputs")
    def assess_inputs(request: AssessInputsRequest):
        return engine.execute("assess_inputs", request.model_dump(mode="json", exclude_none=True))

    @app.post("/api/gaps")
    def gaps(request: GapRequest):
        safe_input_file(root, request.expectation_path)
        return engine.execute("detect_gaps", request.model_dump(exclude_none=True))

    @app.post("/api/ensure/plan")
    def plan(request: EnsureRequest):
        safe_input_file(root, request.expectation_path)
        payload = request.model_dump(exclude_none=True)
        if request.acquisition is None:
            if not request.source_id:
                raise HTTPException(422, "Select a source")
            planned = connector.execute(
                "plan",
                {
                    "source_id": request.source_id,
                    "start_date": request.start,
                    "end_date": request.end,
                },
            )
            payload["acquisition"] = {
                "source_id": request.source_id,
                "parameters": planned.get("parameters", {}),
            }
        else:
            validate_acquisition(request.acquisition)
        return engine.execute("ensure_plan", payload)

    @app.post("/api/ensure/apply")
    def apply(request: ApplyRequest):
        return engine.execute("ensure_apply", request.model_dump())

    @app.get("/api/operations/{operation_id}")
    def status(operation_id: str):
        result = engine.execute("status", {"operation_id": operation_id})
        # Raw checkpoint requests may include local paths or sensitive acquisition parameters.
        saved = result.get("operation", {})
        return {
            "protocol_version": result.get("protocol_version", "1"),
            "status": "ok",
            "operation_status": result.get("operation_status"),
            "operation": saved.get("operation"),
            "started_at": saved.get("started_at"),
            "finished_at": saved.get("finished_at"),
            "result": saved.get("result"),
            "error": saved.get("error"),
        }

    @app.get("/api/files")
    def file(path: str, download: bool = False):
        local = safe_input_file(root, path)
        if download:
            return FileResponse(local, media_type="application/octet-stream", filename=local.name)
        if local.stat().st_size > MAX_PREVIEW:
            return {
                "path": path,
                "size": local.stat().st_size,
                "preview": None,
                "reason": "File exceeds preview size; download the original",
            }
        try:
            content = local.read_text(encoding="utf-8")
        except UnicodeError:
            content = None
        return {
            "path": path,
            "size": local.stat().st_size,
            "preview": content,
            "media_type": mimetypes.guess_type(local.name)[0],
        }

    static = web_root or root / "apps/web"
    if static.is_dir() and (static / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local research input data workspace")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--host", choices=["127.0.0.1", "::1", "localhost"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(create_app(args.workspace), host=args.host, port=args.port)
    return 0
