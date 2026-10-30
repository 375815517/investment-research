"""Small, explicit HTTP CSV connector using the inherited proxy and TLS trust.

Configuration contains environment-variable names, never credential values.
Remote bytes remain untrusted until application-level validation succeeds.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import yaml

from .observations import OBSERVATION_PARSERS, PARSER_ERRORS, extract_html_text

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
_PARAMETER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
_ENV = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SENSITIVE = re.compile(r"token|secret|password|key|authorization|credential", re.I)


class ConnectorError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.exit_code = 5 if code.startswith("SOURCE_") else 2


def _url_check(url: str) -> None:
    if not isinstance(url, str):
        raise ConnectorError("CONFIG_INVALID", "Source URL must be a string.")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConnectorError("CONFIG_INVALID", "Source URL must use http or https.")
    if parsed.username or parsed.password or parsed.fragment:
        raise ConnectorError(
            "CONFIG_INVALID", "Source URL cannot contain credentials or fragments."
        )
    if any(_SENSITIVE.search(k) for k, _ in urllib.parse.parse_qsl(parsed.query)):
        raise ConnectorError(
            "CONFIG_INVALID", "Secrets in source URLs are not supported; use auth_env."
        )


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    url: str
    name: str = ""
    connector_id: str = "http-csv-v1"
    dataset_id: str = "daily-prices"
    allowed_parameters: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = (
        "security_id",
        "trading_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "currency",
    )
    timeout_seconds: float = 15
    max_bytes: int = 10_000_000
    max_attempts: int = 2
    retry_delay_seconds: float = 0.25
    auth_env: str | None = None
    archive_permissions: str = "unknown"
    known_limitations: tuple[str, ...] = ()
    usage_basis: str = ""
    source_symbol: str = ""
    security_id: str = ""
    currency: str = ""
    subject_id: str = ""
    subject_type: str = ""
    document_kind: str = ""
    source_category: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not _ID.fullmatch(self.source_id):
            raise ConnectorError("CONFIG_INVALID", "Invalid source_id.")
        _url_check(self.url)
        for value in (self.timeout_seconds, self.retry_delay_seconds):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ConnectorError("CONFIG_INVALID", "Numeric bounds must be finite numbers.")
        for value in (self.max_bytes, self.max_attempts):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConnectorError("CONFIG_INVALID", "Byte and attempt limits must be integers.")
        if self.connector_id not in {
            "http-csv-v1",
            "yahoo-chart-v1",
            "http-document-v1",
            "tencent-kline-v1",
            "http-html-v1",
            *OBSERVATION_PARSERS,
        }:
            raise ConnectorError(
                "CONNECTOR_UNSUPPORTED",
                "Unknown connector; use a registered CSV, chart or document connector.",
            )
        supported_datasets = {
            "http-csv-v1": {"daily-prices"},
            "yahoo-chart-v1": {"daily-prices"},
            "tencent-kline-v1": {"daily-prices"},
            "http-document-v1": {"financial-facts", "document-facts", "market-observations"},
            "http-html-v1": {"document-facts", "market-observations"},
            **{key: {"market-observations"} for key in OBSERVATION_PARSERS},
        }
        if self.dataset_id not in supported_datasets[self.connector_id]:
            raise ConnectorError("DATASET_UNSUPPORTED", "Dataset is incompatible with connector.")
        if not 0 < self.timeout_seconds <= 60 or not 0 < self.max_bytes <= 50_000_000:
            raise ConnectorError("CONFIG_INVALID", "Timeout or response-size bound is invalid.")
        if not 1 <= self.max_attempts <= 3 or not 0 <= self.retry_delay_seconds <= 5:
            raise ConnectorError("CONFIG_INVALID", "Retry bounds are invalid.")
        if self.auth_env and not _ENV.fullmatch(self.auth_env):
            raise ConnectorError("CONFIG_INVALID", "auth_env must name an environment variable.")
        if self.auth_env and urllib.parse.urlsplit(self.url).scheme != "https":
            raise ConnectorError("CONFIG_INVALID", "Credential-bearing requests require HTTPS.")
        if self.archive_permissions not in {"allowed", "research-only", "unknown", "restricted"}:
            raise ConnectorError("CONFIG_INVALID", "Invalid archive_permissions value.")
        if self.archive_permissions == "research-only" and not self.usage_basis.strip():
            raise ConnectorError(
                "CONFIG_INVALID", "Research-only acquisition requires usage_basis."
            )
        for name in self.allowed_parameters:
            if (
                not isinstance(name, str)
                or not _PARAMETER.fullmatch(name)
                or _SENSITIVE.search(name)
            ):
                raise ConnectorError("CONFIG_INVALID", "Invalid or sensitive parameter name.")

    @classmethod
    def load(cls, workspace: Path, source_id: str) -> SourceDefinition:
        if not _ID.fullmatch(source_id) or ".." in source_id:
            raise ConnectorError("CONFIG_INVALID", "Invalid source_id.")
        root = workspace.resolve()
        path = root / "research" / "sources" / source_id / "source.yaml"
        if not path.resolve().is_relative_to(root):
            raise ConnectorError("CONFIG_INVALID", "Source definition escapes the workspace.")
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConnectorError(
                "SOURCE_DEFINITION_MISSING", "Source definition is missing or invalid YAML."
            ) from exc
        if not isinstance(data, dict) or data.get("source_id") != source_id:
            raise ConnectorError("CONFIG_INVALID", "Source definition must match its source_id.")
        for name in ("allowed_parameters", "required_columns", "known_limitations"):
            if name in data:
                if not isinstance(data[name], list) or not all(
                    isinstance(x, str) for x in data[name]
                ):
                    raise ConnectorError("CONFIG_INVALID", f"{name} must be a string list.")
                data[name] = tuple(data[name])
        try:
            return cls(**data)
        except (TypeError, ValueError) as exc:
            raise ConnectorError(
                "CONFIG_INVALID", "Source definition fields or types are invalid."
            ) from exc

    def readiness(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "definition": "valid",
            "implementation": "installed",
            "authentication": "not_required"
            if not self.auth_env
            else ("configured" if os.environ.get(self.auth_env) else "missing"),
            "network": "not_checked",
            "parser": self.connector_id,
            "archive_permissions": self.archive_permissions,
            "usage_basis": self.usage_basis,
            "dataset_id": self.dataset_id,
            "limitations": list(self.known_limitations),
        }


@dataclass(frozen=True)
class FetchResult:
    path: str
    source_id: str
    sha256: str
    size_bytes: int
    content_type: str
    fetched_at: str
    attempts: int
    rows: int
    request: dict[str, Any] = field(default_factory=dict)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        _url_check(newurl)
        previous = urllib.parse.urlsplit(req.full_url)
        target = urllib.parse.urlsplit(newurl)
        if previous.scheme == "https" and target.scheme != "https":
            raise ConnectorError("SOURCE_REDIRECT_DENIED", "HTTPS downgrade redirect was rejected.")
        if req.has_header("Authorization") and (previous.hostname, previous.port) != (
            target.hostname,
            target.port,
        ):
            raise ConnectorError(
                "SOURCE_REDIRECT_DENIED",
                "Credential forwarding to a different origin was rejected.",
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpFetcher:
    def __init__(self, *, opener: Any = None, sleep: Callable[[float], None] = time.sleep):
        # Standard opener retains HTTP(S)_PROXY and normal certificate validation.
        self.opener = opener or urllib.request.build_opener(_SafeRedirect())
        self.sleep = sleep

    def fetch(
        self, source: SourceDefinition, parameters: dict[str, Any], target_dir: Path
    ) -> FetchResult:
        if source.archive_permissions not in {"allowed", "research-only"}:
            raise ConnectorError(
                "SOURCE_ARCHIVE_BLOCKED", "Source archival permission must be explicitly allowed."
            )
        if set(parameters) - set(source.allowed_parameters):
            raise ConnectorError(
                "CONFIG_INVALID", "Request contains parameters not declared by the source."
            )
        if any(not isinstance(v, (str, int, float)) for v in parameters.values()):
            raise ConnectorError(
                "CONFIG_INVALID", "Request parameters must be scalar strings or numbers."
            )
        headers = {
            "Accept": "application/pdf, application/json, text/csv, application/csv, text/plain",
            "User-Agent": "investment-research/0.1",
        }
        if source.auth_env:
            credential = os.environ.get(source.auth_env)
            if not credential:
                raise ConnectorError(
                    "SOURCE_AUTH_MISSING", "Source credential binding is not configured."
                )
            headers["Authorization"] = "Bearer " + credential
        query_parameters = dict(parameters)
        base_url = source.url
        if "{symbol}" in base_url:
            symbol = str(query_parameters.pop("symbol", ""))
            if not re.fullmatch(r"[A-Za-z0-9.^=_-]{1,40}", symbol):
                raise ConnectorError("CONFIG_INVALID", "A valid source symbol is required.")
            base_url = base_url.replace("{symbol}", urllib.parse.quote(symbol, safe=""))
        query = urllib.parse.urlencode(query_parameters)
        url = base_url + (("&" if "?" in base_url else "?") + query if query else "")
        data: bytes | None = None
        content_type = ""
        for attempt in range(1, source.max_attempts + 1):
            try:
                request = urllib.request.Request(url, headers=headers)
                with self.opener.open(request, timeout=source.timeout_seconds) as response:
                    content_type = response.headers.get_content_type()
                    if content_type in {"text/html", "application/xhtml+xml"} and (
                        source.connector_id
                        not in {
                            "tencent-kline-v1",
                            "http-html-v1",
                            "hkex-short-turnover-v1",
                            "stockanalysis-statistics-v1",
                            "stockanalysis-ratios-v1",
                        }
                    ):
                        raise ConnectorError(
                            "SOURCE_CONTENT_INVALID", "Expected CSV, received an HTML response."
                        )
                    data = response.read(source.max_bytes + 1)
                    if len(data) > source.max_bytes:
                        raise ConnectorError(
                            "SOURCE_SIZE_LIMIT", "Response exceeded the configured byte limit."
                        )
                break
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {408, 429, 500, 502, 503, 504}
                if not retryable or attempt == source.max_attempts:
                    raise ConnectorError(
                        "SOURCE_HTTP_ERROR",
                        f"Source returned HTTP {exc.code}.",
                        retryable=retryable,
                    ) from None
                wait = source.retry_delay_seconds
                retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
                if retry_after.isdigit():
                    requested_wait = int(retry_after)
                    if requested_wait > 5:
                        raise ConnectorError(
                            "SOURCE_RATE_LIMITED",
                            "Source requested a longer retry interval; retry later.",
                            retryable=True,
                        ) from None
                    wait = max(wait, requested_wait)
                self.sleep(wait)
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == source.max_attempts:
                    raise ConnectorError(
                        "SOURCE_NETWORK_ERROR",
                        "Source request failed; URL and credentials are omitted.",
                        retryable=True,
                    ) from None
                self.sleep(source.retry_delay_seconds)
        assert data is not None
        observed_at = datetime.now(UTC).isoformat()
        if source.connector_id == "yahoo-chart-v1":
            parsed = parse_yahoo_chart(
                data, str(parameters.get("symbol", "")), "source-preview", observed_at=observed_at
            )
            rows = len(parsed["records"])
            extension = "json"
        elif source.connector_id in OBSERVATION_PARSERS:
            try:
                records = OBSERVATION_PARSERS[source.connector_id](
                    data, source.source_symbol, source.security_id, observed_at=observed_at
                )
            except PARSER_ERRORS:
                raise ConnectorError(
                    "SOURCE_CONTENT_INVALID", "Source observation schema is invalid."
                ) from None
            rows = len(records)
            extension = "csv" if source.connector_id == "sfc-short-positions-v1" else "html"
        elif source.connector_id == "http-html-v1":
            if not data.lstrip().lower().startswith(
                (b"<!doctype html", b"<html")
            ) or not extract_html_text(data):
                raise ConnectorError("SOURCE_CONTENT_INVALID", "Expected nonempty HTML document.")
            rows, extension = 0, "html"
        elif source.connector_id == "http-document-v1":
            if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
                raise ConnectorError("SOURCE_CONTENT_INVALID", "Expected a complete PDF document.")
            rows, extension = 0, "pdf"
        elif source.connector_id == "tencent-kline-v1":
            parsed = parse_tencent_kline(
                data, str(parameters.get("param", "")).split(",")[0], observed_at=observed_at
            )
            rows, extension = len(parsed["observations"]), "json"
        else:
            try:
                text = data.decode("utf-8-sig")
                if text.lstrip().lower().startswith(("<!doctype", "<html", "{", "[")):
                    raise ValueError("unexpected format")
                reader = csv.DictReader(io.StringIO(text))
                if not reader.fieldnames or not set(source.required_columns).issubset(
                    reader.fieldnames
                ):
                    raise ValueError("missing columns")
                records = list(reader)
                if not records or any(
                    None in row or any(v is None for v in row.values()) for row in records
                ):
                    raise ValueError("empty or malformed records")
                rows = len(records)
                extension = "csv"
            except (UnicodeError, csv.Error, ValueError):
                raise ConnectorError(
                    "SOURCE_CONTENT_INVALID",
                    "Response is not a nonempty CSV matching declared columns.",
                ) from None
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"response-{uuid.uuid4().hex}.{extension}"
        path.write_bytes(data)
        return FetchResult(
            path=str(path),
            source_id=source.source_id,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type=content_type,
            fetched_at=observed_at,
            attempts=attempt,
            rows=rows,
            request={"source_id": source.source_id, "parameter_names": sorted(parameters)},
        )


def parse_yahoo_chart(
    data: bytes, expected_symbol: str, security_id: str, *, observed_at: str
) -> dict[str, Any]:
    """Extract source-native quote values, never relabel as verified unadjusted."""
    if not _ID.fullmatch(security_id) or ".." in security_id:
        raise ConnectorError("CONFIG_INVALID", "Invalid security_id.")
    try:
        chart = json.loads(data)["chart"]
        if chart.get("error") or len(chart["result"]) != 1:
            raise ValueError("provider error")
        result = chart["result"][0]
        meta = result["meta"]
        if meta["symbol"] != expected_symbol or meta.get("dataGranularity") != "1d":
            raise ValueError("symbol or frequency mismatch")
        currency = meta["currency"]
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency")
        tz = ZoneInfo(meta["exchangeTimezoneName"])
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        keys = ("open", "high", "low", "close", "volume")
        if any(len(quote[key]) != len(timestamps) for key in keys):
            raise ValueError("array lengths")
        records = []
        missing_dates = []
        today = _observation_time(observed_at).astimezone(tz).date()
        for i, timestamp in enumerate(timestamps):
            trading_date = datetime.fromtimestamp(timestamp, tz).date()
            if trading_date >= today or any(quote[key][i] is None for key in keys):
                missing_dates.append(trading_date.isoformat())
                continue
            records.append(
                {
                    "security_id": security_id,
                    "trading_date": trading_date.isoformat(),
                    **{key: str(quote[key][i]) for key in keys},
                    "currency": currency,
                    "volume_unit": "shares",
                    "price_basis": "provider-native",
                    "session": "regular-final",
                }
            )
        if not records:
            raise ValueError("no completed non-null historical rows")
        return {
            "records": records,
            "missing_or_provisional_dates": missing_dates,
            "symbol": meta["symbol"],
            "currency": currency,
            "exchange": meta.get("exchangeName"),
            "timezone": meta["exchangeTimezoneName"],
            "provider_events": result.get("events", {}),
            "limitations": [
                "Quote values are provider-native; historical split-adjustment basis is not verified.",
                "Returned dates are not a verified exchange calendar or proof of complete coverage.",
                "Provider events are not independently verified corporate-action coverage.",
            ],
        }
    except (KeyError, TypeError, ValueError, IndexError, UnicodeError):
        raise ConnectorError(
            "SOURCE_CONTENT_INVALID",
            "Yahoo chart response is invalid, mismatched or lacks completed historical rows.",
        ) from None


class ConnectorService:
    """Acquires a temporary delivery; caller imports it via the shared Service."""

    def __init__(self, workspace: Path, *, fetcher: HttpFetcher | None = None):
        self.workspace = workspace.resolve()
        self.fetcher = fetcher or HttpFetcher()

    def execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "extract_text":
            path = Path(payload["path"])
            raw = path.read_bytes()
            return {
                "text": extract_html_text(raw)
                if path.suffix.lower() in {".html", ".htm"}
                else raw.decode("utf-8-sig")
            }
        if operation == "extract_pdf_page":
            return {"text": extract_pdf_page(payload["path"], payload["page"])}
        source = SourceDefinition.load(self.workspace, str(payload.get("source_id", "")))
        if operation == "plan":
            parameters: dict[str, Any] = {}
            if source.connector_id in {"yahoo-chart-v1", "tencent-kline-v1"}:
                try:
                    start = date.fromisoformat(payload["start_date"])
                    end = date.fromisoformat(payload["end_date"])
                    if start > end or (end - start).days > 300:
                        raise ValueError("range")
                except (KeyError, TypeError, ValueError):
                    raise ConnectorError(
                        "CONFIG_INVALID", "Provide an ordered ISO date range of at most 300 days."
                    ) from None
                if source.connector_id == "yahoo-chart-v1":
                    parameters = {
                        "symbol": source.source_symbol,
                        "period1": int(
                            datetime.combine(start, datetime.min.time(), UTC).timestamp()
                        ),
                        "period2": int(
                            datetime.combine(
                                end + timedelta(days=1), datetime.min.time(), UTC
                            ).timestamp()
                        ),
                        "interval": "1d",
                        "events": "div,splits",
                    }
                else:
                    parameters = {"param": f"{source.source_symbol},day,{start},{end},320,"}
            return {
                "source_id": source.source_id,
                "security_id": source.security_id,
                "parameters": parameters,
                "dataset_id": source.dataset_id,
            }
        if operation == "parse":
            path = Path(payload.get("document_path", payload.get("path", "")))
            security_id = source.security_id or str(payload.get("security_id", ""))
            if not security_id or not source.source_symbol:
                raise ConnectorError(
                    "CONFIG_INVALID", "Parsing requires configured security and source symbol."
                )
            if source.connector_id in OBSERVATION_PARSERS:
                try:
                    records = OBSERVATION_PARSERS[source.connector_id](
                        path.read_bytes(),
                        source.source_symbol,
                        security_id,
                        observed_at=payload.get("first_observed_at", ""),
                    )
                except PARSER_ERRORS:
                    raise ConnectorError(
                        "SOURCE_CONTENT_INVALID", "Source observation schema is invalid."
                    ) from None
                return {"records": records, "parser_id": source.connector_id, "limitations": []}
            if source.connector_id == "yahoo-chart-v1":
                parsed = parse_yahoo_chart(
                    path.read_bytes(),
                    source.source_symbol,
                    security_id,
                    observed_at=payload.get("first_observed_at", ""),
                )
                records = parsed["records"]
            elif source.connector_id == "tencent-kline-v1":
                parsed = parse_tencent_kline(
                    path.read_bytes(),
                    source.source_symbol,
                    observed_at=payload.get("first_observed_at", ""),
                )
                if not re.fullmatch(r"[A-Z]{3}", source.currency):
                    raise ConnectorError("CONFIG_INVALID", "Configured quote currency is required.")
                records = [
                    {
                        "security_id": security_id,
                        "trading_date": row["trading_date"],
                        **{key: row[key] for key in ("open", "high", "low", "close")},
                        "volume": row["provider_volume"],
                        "volume_unit": "provider-native",
                        "price_basis": "provider-native",
                        "currency": source.currency,
                        "session": "regular-final",
                    }
                    for row in parsed["observations"]
                ]
            else:
                raise ConnectorError("OPERATION_UNSUPPORTED", "No JSON parser for this source.")
            return {
                "records": records,
                "parser_id": source.connector_id,
                "limitations": parsed["limitations"],
            }

        if operation == "source_check":
            return {
                "protocol_version": "1",
                "status": "ok",
                "source": source.readiness(),
                "artifact_refs": [],
                "issues": [],
                "next_actions": [],
            }
        if operation != "collect":
            raise ConnectorError("OPERATION_UNSUPPORTED", "Unsupported connector operation.")
        target = self.workspace / ".research-local" / "collections" / uuid.uuid4().hex
        if (
            not target.resolve().is_relative_to(self.workspace)
            or (self.workspace / ".research-local").is_symlink()
        ):
            raise ConnectorError(
                "CONFIG_INVALID", "Local collection directory escapes the workspace."
            )
        result = self.fetcher.fetch(source, payload.get("parameters", {}), target)
        receipt = asdict(result)
        receipt["archive_permissions"] = source.archive_permissions
        receipt["usage_basis"] = source.usage_basis
        (target / "delivery.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        output = {
            "protocol_version": "1",
            "status": "acquired",
            "delivery": receipt,
            "artifact_refs": [receipt["path"]],
            "issues": [],
            "next_actions": ["import through the shared application service"],
            "import_request": {
                "path": receipt["path"],
                "source_id": source.source_id,
                "published_at": payload.get("published_at"),
                "title": source.name or source.source_id,
            },
        }
        if source.connector_id == "yahoo-chart-v1":
            output["candidate_preview"] = parse_yahoo_chart(
                Path(result.path).read_bytes(),
                str(payload.get("parameters", {}).get("symbol", "")),
                str(payload.get("security_id", "source-preview")),
                observed_at=result.fetched_at,
            )
        elif source.connector_id == "tencent-kline-v1":
            output["candidate_preview"] = parse_tencent_kline(
                Path(result.path).read_bytes(),
                str(payload.get("parameters", {}).get("param", "")).split(",")[0],
                observed_at=result.fetched_at,
            )
        return output


def parse_tencent_kline(data: bytes, expected_symbol: str, *, observed_at: str) -> dict[str, Any]:
    """Retain provider field semantics; unit and price basis require separate evidence."""
    try:
        if not re.fullmatch(r"hk[0-9]{5}", expected_symbol):
            raise ValueError("symbol")
        response = json.loads(data)
        if response["code"] != 0:
            raise ValueError("provider error")
        payload = response["data"][expected_symbol]
        rows = payload["day"]
        observations = []
        dates = set()
        observed_date = (
            _observation_time(observed_at).astimezone(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
        )
        missing_dates = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                raise ValueError("row")
            day = datetime.strptime(row[0], "%Y-%m-%d").date().isoformat()
            if day in dates:
                raise ValueError("duplicate date")
            if day >= observed_date:
                missing_dates.append(day)
                continue
            dates.add(day)
            values = [float(value) for value in row[1:6]]
            if not all(math.isfinite(value) and value >= 0 for value in values):
                raise ValueError("number")
            observations.append(
                dict(
                    zip(
                        ("trading_date", "open", "close", "high", "low", "provider_volume"), row[:6]
                    )
                )
            )
        if not observations:
            raise ValueError("empty")
        return {
            "symbol": expected_symbol,
            "observations": observations,
            "missing_or_provisional_dates": missing_dates,
            "price_basis": "provider-native",
            "volume_unit": "unverified",
            "limitations": [
                "The day response branch is not independent proof of unadjusted prices.",
                "Volume units and complete exchange-session coverage require evidence.",
                "Observations cannot be published as standard daily-prices without reconciliation.",
            ],
        }
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
        raise ConnectorError("SOURCE_CONTENT_INVALID", "Tencent day response is invalid.") from None


def extract_pdf_page(path: Path | str, page: int) -> str:
    """Extract one physical PDF page (1-based), without OCR or inferred content."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ConnectorError("PDF_PAGE_INVALID", "PDF physical page must be a positive integer.")
    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted or page > len(reader.pages):
            raise ConnectorError("PDF_PAGE_INVALID", "Encrypted PDF or page outside document.")
        text = reader.pages[page - 1].extract_text(extraction_mode="layout")
        if not text or not text.strip():
            raise ConnectorError(
                "PDF_TEXT_MISSING", "Page has no extractable text; OCR requires review."
            )
        return text
    except (OSError, PdfReadError, ValueError, IndexError):
        raise ConnectorError("PDF_INVALID", "Cannot parse PDF evidence.") from None


def _observation_time(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("timezone required")
        return moment
    except (TypeError, ValueError):
        raise ConnectorError(
            "OBSERVATION_TIME_REQUIRED",
            "Parsing requires the original timezone-aware first observation time.",
        ) from None
