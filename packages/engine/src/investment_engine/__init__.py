"""Shared ingestion application service for CLI, agents and future workers."""

import csv
import io
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from investment_domain import SCHEMAS, DailyPrice, DomainError, FinancialFact, ImportRequest
from investment_repository import (
    Repository,
    digest_bytes,
    encoded,
    fingerprint,
    identifier,
    utc_now,
)


class Service:
    OPERATIONS = (
        "capabilities",
        "schema",
        "import",
        "prepare",
        "validate",
        "review",
        "ingest_plan",
        "ingest_apply",
        "coverage",
        "status",
        "resume",
        "index",
        "source_check",
        "collect",
        "detect_gaps",
        "ensure_plan",
        "ensure_apply",
    )

    def __init__(self, workspace: Path, connector_service=None):
        self.repo = Repository(workspace)
        self.connector_service = connector_service

    def execute(self, operation: str, payload: dict) -> dict:
        if operation not in self.OPERATIONS:
            raise DomainError("UNSUPPORTED_OPERATION", operation)
        if not isinstance(payload, dict):
            raise DomainError("INVALID_REQUEST", "Request must be an object")
        operation_id = "op-" + uuid4().hex
        checkpoint = f".research-local/operations/{operation_id}.json"
        saved = dict(operation=operation, payload=payload, status="running", started_at=utc_now())
        self.repo.json(checkpoint, saved)
        try:
            result = getattr(self, "_" + operation)(payload)
            result = dict(result)
            result.update(protocol_version="1", operation_id=operation_id)
            for key, value in dict(
                summary=operation.replace("_", " "), artifact_refs=[], issues=[], next_actions=[]
            ).items():
                result.setdefault(key, value)
            saved.update(status="completed", result=result, finished_at=utc_now())
            self.repo.json(checkpoint, saved, immutable=False)
            return result
        except (ValidationError, KeyError, ValueError, OSError) as exc:
            err = DomainError("INVALID_REQUEST", str(exc))
            saved.update(status="failed", error=dict(code=err.code, message=err.message))
            self.repo.json(checkpoint, saved, immutable=False)
            raise err from exc
        except DomainError as exc:
            saved.update(status="failed", error=dict(code=exc.code, message=exc.message))
            self.repo.json(checkpoint, saved, immutable=False)
            raise

    def _detect_gaps(self, payload):
        from .ensure import detect

        return detect(self, payload)

    def _ensure_plan(self, payload):
        from .ensure import plan

        return plan(self, payload)

    def _ensure_apply(self, payload):
        from .ensure import apply

        return apply(self, payload)

    def _capabilities(self, payload):
        return dict(
            status="available",
            operations=list(self.OPERATIONS),
            datasets=["daily-prices", "financial-facts"],
            limitations=[
                "No automatic Git commit or push",
                "Publication time is importer-asserted",
                "Calendar completeness requires evidence-backed expectation inputs; live source authentication is separate",
                "Financial semantics require explicit review; no automatic OCR or model calls",
            ],
        )

    def _source_check(self, payload):
        if self.connector_service is None:
            raise DomainError("CONNECTOR_UNAVAILABLE", "No connector service configured")
        return self.connector_service.execute("source_check", payload)

    def _collect(self, payload):
        if self.connector_service is None:
            raise DomainError("CONNECTOR_UNAVAILABLE", "No connector service configured")
        try:
            delivery = self.connector_service.execute("collect", payload)
        except Exception as exc:
            code = getattr(exc, "code", "SOURCE_FAILED")
            source_id = identifier(payload.get("source_id", "unknown"))
            stamp = utc_now()
            collection_id = "collection-" + uuid4().hex
            receipt = dict(
                collection_id=collection_id,
                source_id=source_id,
                observed_at=stamp,
                status="failed",
                issue_code=code,
                parameters=self._redact(payload.get("parameters", {})),
            )
            self.repo.json(
                f"data/inputs/collection-records/{source_id}/{stamp[:4]}/{collection_id}/collection.json",
                receipt,
            )
            raise DomainError(
                code,
                "Source acquisition failed; see the archived collection receipt",
                getattr(exc, "exit_code", 5),
            ) from exc
        request = dict(delivery["import_request"])
        raw_delivery = delivery.get("delivery", {})
        request["origin_url"] = raw_delivery.get("request_url", raw_delivery.get("url"))
        request["collection_context"] = {
            "delivery": raw_delivery,
            "parameters": payload.get("parameters", {}),
        }
        imported = self._import(request)
        imported["delivery"] = delivery.get("delivery")
        if "candidate_preview" in delivery:
            imported["candidate_preview"] = delivery["candidate_preview"]
        return imported

    def _schema(self, payload):
        name = payload.get("contract")
        if name and name not in SCHEMAS:
            raise DomainError("UNKNOWN_CONTRACT", name)
        return dict(
            status="available",
            schemas={k: c.model_json_schema() for k, c in SCHEMAS.items() if not name or k == name},
        )

    def _import(self, payload):
        request = ImportRequest.model_validate(payload)
        path = Path(request.path).expanduser()
        if not path.is_absolute():
            path = self.repo.path(request.path)
        if not path.is_file():
            raise DomainError("IMPORT_NOT_FOUND", str(path))
        if path.stat().st_size > 32 * 1024 * 1024:
            raise DomainError("IMPORT_TOO_LARGE", "MVP import limit is 32 MiB")
        doc, refs, duplicate = self.repo.import_bytes(
            path.read_bytes(),
            request.source_id,
            path.suffix,
            request.published_at.isoformat() if request.published_at else None,
            request.title,
            self._redact_url(request.origin_url),
            self._redact(request.collection_context),
        )
        return dict(
            status="unchanged" if duplicate else "received",
            document_id=doc["document_id"],
            document=doc,
            artifact_refs=refs,
            next_actions=["prepare"],
        )

    @staticmethod
    def _redact_url(value):
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise DomainError("INVALID_ORIGIN_URL", "Origin URL must be HTTP(S)")
        host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        query = [
            (
                k,
                "[REDACTED]"
                if re.search(r"token|secret|password|key|auth|credential", k, re.I)
                else v,
            )
            for k, v in parse_qsl(parsed.query)
        ]
        return urlunsplit((parsed.scheme, host, parsed.path, urlencode(query), ""))

    @classmethod
    def _redact(cls, value):
        if isinstance(value, dict):
            return {
                k: "[REDACTED]"
                if re.search(r"token|secret|password|key|auth|credential", str(k), re.I)
                else cls._redact(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [cls._redact(x) for x in value]
        if isinstance(value, str) and value.startswith(("https://", "http://")):
            return cls._redact_url(value)
        return value

    def _candidate(self, candidate_id):
        candidate = self.repo.read_json(
            f".research-local/candidates/{identifier(candidate_id)}.json"
        )
        body = {k: v for k, v in candidate.items() if k != "candidate_id"}
        if (
            "candidate-" + fingerprint(body) != candidate_id
            or candidate.get("candidate_id") != candidate_id
        ):
            raise DomainError(
                "CANDIDATE_CHANGED",
                "Candidate changed after preparation; create a new candidate",
                4,
            )
        return candidate

    def _prepare(self, payload):
        doc, _ = self.repo.document(payload["document_id"])
        dataset = payload["dataset_id"]
        if dataset not in ("daily-prices", "financial-facts"):
            raise DomainError("UNKNOWN_DATASET", dataset)
        records = payload.get("records")
        if dataset == "daily-prices" and records is not None:
            raise DomainError(
                "UNTRUSTED_PRICE_OVERRIDE",
                "Price candidates must be parsed from the archived source; records overrides are not supported",
            )
        if records is None:
            if dataset != "daily-prices":
                raise DomainError(
                    "CANDIDATES_REQUIRED",
                    "Financial extraction requires records with evidence locators",
                )
            if Path(doc["path"]).suffix.lower() == ".csv":
                text = self.repo.path(doc["path"]).read_text(encoding="utf-8-sig")
                if text.lstrip().startswith("<"):
                    raise DomainError("UNEXPECTED_CONTENT", "HTML is not a price CSV")
                records = list(csv.DictReader(io.StringIO(text)))
            else:
                if self.connector_service is None:
                    raise DomainError(
                        "PARSER_UNAVAILABLE",
                        "Archived source requires its deterministic connector parser",
                    )
                try:
                    parsed = self.connector_service.execute(
                        "parse",
                        {
                            "document_path": str(self.repo.path(doc["path"])),
                            "source_id": doc["source_id"],
                            "first_observed_at": doc["first_observed_at"],
                        },
                    )
                except Exception as exc:
                    raise DomainError(
                        getattr(exc, "code", "PARSE_FAILED"), "Archived source parser failed", 3
                    ) from exc
                records = parsed["records"]
                payload = dict(payload, parser_version=parsed["parser_id"])
        if not isinstance(records, list) or not records:
            raise DomainError("EMPTY_BATCH", "A candidate batch must contain records")
        candidate = dict(
            dataset_id=dataset,
            contract_version="1",
            document_id=doc["document_id"],
            document_sha256=doc["sha256"],
            source_id=doc["source_id"],
            parser_version=payload.get(
                "parser_version", "csv-v1" if dataset == "daily-prices" else "manual-v1"
            ),
            records=records,
            supersedes=payload.get("supersedes", []),
        )
        candidate_id = "candidate-" + fingerprint(candidate)
        candidate["candidate_id"] = candidate_id
        rel = f".research-local/candidates/{candidate_id}.json"
        self.repo.json(rel, candidate)
        return dict(
            status="prepared",
            candidate_id=candidate_id,
            candidate_hash=fingerprint(candidate),
            record_count=len(records),
            artifact_refs=[rel],
            next_actions=["validate"],
        )

    def _check(self, candidate):
        doc, _ = self.repo.document(candidate["document_id"])
        if doc["sha256"] != candidate["document_sha256"]:
            raise DomainError("EVIDENCE_CHANGED", candidate["document_id"], 4)
        model = DailyPrice if candidate["dataset_id"] == "daily-prices" else FinancialFact
        normalized, issues, keys = [], [], set()
        for index, raw in enumerate(candidate["records"]):
            try:
                record = model.model_validate(raw).model_dump(mode="json")
                key = (
                    (
                        record["security_id"],
                        record["trading_date"],
                        record["session"],
                        record["price_basis"],
                    )
                    if model is DailyPrice
                    else (
                        record["company_id"],
                        record["metric_id"],
                        record["period_start"],
                        record["period_end"],
                        record["scope"],
                        record["currency"],
                    )
                )
                if model is DailyPrice and not (
                    record["security_id"].startswith("demo-")
                    and candidate["source_id"].startswith("demo-")
                ):
                    registrations = list(
                        self.repo.path(
                            f"data/inputs/markets/securities/{record['security_id']}"
                        ).glob("*/security.json")
                    )
                    if len(registrations) != 1:
                        raise ValueError(
                            "Exactly one unambiguous security registration with user confirmation is required"
                        )
                    registration = self.repo.read_json(
                        registrations[-1].relative_to(self.repo.root).as_posix()
                    )
                    if (
                        not registration.get("user_confirmed")
                        or registration.get("currency") != record["currency"]
                    ):
                        raise ValueError("Security confirmation or currency does not match")
                if key in keys:
                    raise ValueError("Duplicate business key in candidate")
                keys.add(key)
                if model is FinancialFact:
                    # Evidence text matching can verify an excerpt, not its financial interpretation.
                    if Path(doc["path"]).suffix in (".txt", ".md", ".csv", ".json", ".html"):
                        if record["excerpt"] not in self.repo.path(doc["path"]).read_text():
                            raise ValueError("Evidence excerpt not present in original")
                    elif Path(doc["path"]).suffix.lower() == ".pdf":
                        page_match = re.fullmatch(r"pdf:page:([1-9][0-9]*)", record["locator"])
                        if not page_match or self.connector_service is None:
                            raise ValueError(
                                "PDF requires pdf:page:<physical-page> and a configured extractor"
                            )
                        try:
                            page = self.connector_service.execute(
                                "extract_pdf_page",
                                {
                                    "path": str(self.repo.path(doc["path"])),
                                    "page": int(page_match[1]),
                                },
                            )
                        except Exception as exc:
                            raise ValueError("PDF evidence extraction failed") from exc
                        if " ".join(record["excerpt"].split()) not in " ".join(
                            page["text"].split()
                        ):
                            raise ValueError(
                                "Evidence excerpt not present on the specified PDF page"
                            )
                    else:
                        raise ValueError(
                            "Unsupported evidence format requires a verified text extraction"
                        )
                normalized.append(record)
            except (ValidationError, ValueError) as exc:
                issues.append(
                    dict(
                        code="RECORD_INVALID",
                        message=str(exc),
                        severity="error",
                        record_index=index,
                        retryable=False,
                    )
                )
        if not doc.get("published_at"):
            issues.append(
                dict(
                    code="PUBLICATION_UNKNOWN",
                    message="Historical/live cutoff queries exclude this batch",
                    severity="warning",
                    retryable=False,
                )
            )
        return normalized, issues

    def _validate(self, payload):
        candidate = self._candidate(payload["candidate_id"])
        records, issues = self._check(candidate)
        errors = any(x["severity"] == "error" for x in issues)
        status = (
            "quarantined"
            if errors
            else ("review_required" if candidate["dataset_id"] == "financial-facts" else "eligible")
        )
        report = dict(
            candidate_id=candidate["candidate_id"],
            candidate_hash=fingerprint(candidate),
            status=status,
            rule_version="v1",
            issues=issues,
            record_count=len(records),
        )
        rel = f".research-local/validations/{candidate['candidate_id']}/{fingerprint(report)}.json"
        self.repo.json(rel, report)
        return dict(
            status=status,
            validation=report,
            artifact_refs=[rel],
            issues=issues,
            next_actions=["review" if status == "review_required" else "ingest_plan"]
            if not errors
            else ["correct_candidate"],
        )

    def _review(self, payload):
        candidate = self._candidate(payload["candidate_id"])
        _, issues = self._check(candidate)
        if any(x["severity"] == "error" for x in issues):
            raise DomainError("QUALITY_BLOCKED", "Invalid records cannot be approved", 3)
        if (
            payload["decision"] not in ("approved", "rejected")
            or not payload.get("reviewer")
            or not payload.get("notes")
        ):
            raise DomainError("INVALID_REVIEW", "Review requires decision, reviewer and notes")
        review = dict(
            candidate_id=candidate["candidate_id"],
            candidate_hash=fingerprint(candidate),
            decision=payload["decision"],
            reviewer=payload["reviewer"],
            notes=payload["notes"],
            reviewed_at=utc_now(),
        )
        rel = f".research-local/reviews/{candidate['candidate_id']}/{uuid4().hex}.json"
        self.repo.json(rel, review)
        return dict(
            status=review["decision"],
            review_ref=rel,
            artifact_refs=[rel],
            next_actions=["ingest_plan"],
        )

    def _admission(self, candidate):
        records, issues = self._check(candidate)
        if any(x["severity"] == "error" for x in issues):
            raise DomainError("QUALITY_BLOCKED", "Candidate failed data checks", 3)
        supersedes = candidate.get("supersedes", [])
        if not isinstance(supersedes, list) or any(not isinstance(x, str) for x in supersedes):
            raise DomainError("INVALID_REVISION", "supersedes must be a list of batch identifiers")
        existing = self.repo.batches()
        known = {batch["batch_id"] for _, batch in existing}
        if not set(supersedes) <= known:
            raise DomainError("INVALID_REVISION", "A superseded batch does not exist")

        def business_key(row):
            if candidate["dataset_id"] == "daily-prices":
                return row["security_id"], row["trading_date"], row["session"], row["price_basis"]
            return (
                row["company_id"],
                row["metric_id"],
                row["period_start"],
                row["period_end"],
                row["scope"],
                row["currency"],
            )

        proposed = {business_key(row): row for row in records}
        for _, previous in existing:
            if previous["batch_id"] in supersedes:
                if (
                    previous["dataset_id"] != candidate["dataset_id"]
                    or previous["source_id"] != candidate["source_id"]
                ):
                    raise DomainError(
                        "INVALID_REVISION", "Cannot supersede another dataset or source"
                    )
                if any(business_key(row) not in proposed for row in previous["rows"]):
                    raise DomainError(
                        "INVALID_REVISION", "Replacement must retain every prior business key"
                    )
        replaced_ids = {
            prior for _, prior_batch in existing for prior in prior_batch.get("supersedes", [])
        }
        for _, batch in existing:
            if batch["batch_id"] in replaced_ids:
                continue
            if (
                batch["dataset_id"] != candidate["dataset_id"]
                or batch["source_id"] != candidate["source_id"]
            ):
                continue
            for row in batch["rows"]:
                if (
                    business_key(row) in proposed
                    and row != proposed[business_key(row)]
                    and batch["batch_id"] not in supersedes
                ):
                    raise DomainError(
                        "RECORD_CONFLICT",
                        "Changed same-source records require explicit supersedes batch IDs",
                        4,
                    )
        review = None
        if candidate["dataset_id"] == "financial-facts":
            reviews = [
                self.repo.read_json(p.relative_to(self.repo.root).as_posix())
                for p in self.repo.path(
                    f".research-local/reviews/{candidate['candidate_id']}"
                ).glob("*.json")
            ]
            matches = [x for x in reviews if x["candidate_hash"] == fingerprint(candidate)]
            review = max(matches, key=lambda x: x["reviewed_at"]) if matches else None
            if not review or review["decision"] != "approved":
                raise DomainError(
                    "REVIEW_REQUIRED", "Candidate needs a hash-bound approved review", 3
                )
        return records, issues, review

    def _ingest_plan(self, payload):
        candidate = self._candidate(payload["candidate_id"])
        records, issues, review = self._admission(candidate)
        plan = dict(
            candidate_id=candidate["candidate_id"],
            candidate_hash=fingerprint(candidate),
            base_revision=self.repo.revision(),
            review_hash=fingerprint(review),
            record_count=len(records),
        )
        plan_id = "plan-" + fingerprint(plan)
        plan["plan_id"] = plan_id
        rel = f".research-local/plans/{plan_id}.json"
        self.repo.json(rel, plan)
        return dict(
            status="planned",
            plan_id=plan_id,
            plan=plan,
            issues=issues,
            artifact_refs=[rel],
            next_actions=["ingest_apply"],
        )

    def _ingest_apply(self, payload):
        plan = self.repo.read_json(f".research-local/plans/{identifier(payload['plan_id'])}.json")
        candidate = self._candidate(plan["candidate_id"])
        if fingerprint(candidate) != plan["candidate_hash"]:
            raise DomainError("STALE_PLAN", "Candidate changed after planning", 4)
        receipt_path = f"data/outputs/research-records/ingest-{plan['candidate_hash']}/receipt.json"
        with self.repo.lock():
            if self.repo.path(receipt_path).exists():
                # Validate all referenced content before returning idempotent success.
                self.repo.batches()
                receipt = self.repo.read_json(receipt_path)
                return dict(
                    status="unchanged", artifact_refs=receipt["artifact_refs"], receipt=receipt
                )
            records, issues, review = self._admission(candidate)
            base_without_self = fingerprint(
                sorted(
                    (rel, fingerprint(batch))
                    for rel, batch in self.repo.batches()
                    if batch.get("candidate_hash") != plan["candidate_hash"]
                )
            )
            if (
                fingerprint(review) != plan["review_hash"]
                or base_without_self != plan["base_revision"]
            ):
                raise DomainError("STALE_PLAN", "Repository or review changed after planning", 4)
            doc, doc_meta = self.repo.document(candidate["document_id"])
            groups: dict[tuple[str, str], list[dict]] = {}
            for record in records:
                subject = record.get("security_id", record.get("company_id"))
                period = record.get("trading_date", record.get("period_end"))
                groups.setdefault((subject, period[:4]), []).append(record)
            audit = f"data/outputs/research-records/ingest-{plan['candidate_hash']}"
            refs = [doc["path"], doc_meta]
            self.repo.json(f"{audit}/candidate.json", candidate)
            self.repo.json(
                f"{audit}/validation.json",
                dict(candidate_hash=plan["candidate_hash"], issues=issues, rule_version="v1"),
            )
            self.repo.json(f"{audit}/review.json", review)
            refs.extend(
                [f"{audit}/candidate.json", f"{audit}/validation.json", f"{audit}/review.json"]
            )
            for (subject, year), group in sorted(groups.items()):
                batch_id = "batch-" + fingerprint(
                    dict(candidate_hash=plan["candidate_hash"], subject=subject, year=year)
                )
                is_price = candidate["dataset_id"] == "daily-prices"
                folder = (
                    f"data/inputs/markets/prices/{identifier(subject)}/daily/{year}/{batch_id}"
                    if is_price
                    else f"data/inputs/companies/{identifier(subject)}/financials/{year}/{batch_id}"
                )
                name = "daily-prices.csv" if is_price else "financial-facts.json"
                if is_price:
                    output = io.StringIO(newline="")
                    writer = csv.DictWriter(
                        output, fieldnames=list(DailyPrice.model_fields), lineterminator="\n"
                    )
                    writer.writeheader()
                    writer.writerows(group)
                    content = output.getvalue().encode()
                else:
                    content = encoded(group)
                data_path = f"{folder}/{name}"
                manifest_path = f"{folder}/batch.json"
                if self.repo.path(manifest_path).exists():
                    existing = self.repo.read_json(manifest_path)
                    if existing.get("candidate_hash") != plan["candidate_hash"]:
                        raise DomainError("VERSION_CONFLICT", manifest_path, 4)
                    refs.extend([data_path, manifest_path])
                    continue
                manifest = dict(
                    batch_id=batch_id,
                    dataset_id=candidate["dataset_id"],
                    subject_id=subject,
                    status="complete",
                    contract_version="1",
                    candidate_hash=plan["candidate_hash"],
                    supersedes=candidate.get("supersedes", []),
                    documents=[candidate["document_id"]],
                    source_id=candidate["source_id"],
                    parser_version=candidate["parser_version"],
                    published_at=doc["published_at"],
                    first_observed_at=doc["first_observed_at"],
                    registered_at=utc_now(),
                    rows=group,
                    record_count=len(group),
                    files=[dict(path=data_path, sha256=digest_bytes(content))],
                    audit_ref=f"{audit}/candidate.json",
                )
                self.repo.write(data_path, content)
                # Last write is the visibility boundary for this individual batch.
                self.repo.json(f"{folder}/batch.json", manifest)
                refs.extend([data_path, f"{folder}/batch.json"])
            receipt = dict(
                candidate_hash=plan["candidate_hash"],
                plan_id=plan["plan_id"],
                artifact_refs=refs + [receipt_path],
            )
            self.repo.json(receipt_path, receipt)
        return dict(status="registered", artifact_refs=receipt["artifact_refs"], receipt=receipt)

    def _coverage(self, payload):
        mode = payload.get("knowledge_mode", "retrospective_explanation")
        if mode not in ("retrospective_explanation", "historical_reconstruction", "live_observed"):
            raise DomainError("INVALID_MODE", mode)
        cutoff = payload.get("information_cutoff")
        if mode != "retrospective_explanation" and not cutoff:
            raise DomainError("CUTOFF_REQUIRED", mode)
        cutoff_time = self._timestamp(cutoff) if cutoff else None
        rows, refs, excluded = [], [], []
        from .market_status import visible_closures

        closures = visible_closures(self.repo, mode, cutoff_time)
        eligible = []
        for rel, batch in self.repo.batches():
            if payload.get("dataset_id") and batch["dataset_id"] != payload["dataset_id"]:
                continue
            if payload.get("subject_id") and batch["subject_id"] != payload["subject_id"]:
                continue
            if mode != "retrospective_explanation":
                if (
                    not batch.get("published_at")
                    or self._timestamp(batch["published_at"]) > cutoff_time
                ):
                    excluded.append(dict(batch_id=batch["batch_id"], reason="not_public_at_cutoff"))
                    continue
                if (
                    mode == "live_observed"
                    and max(
                        self._timestamp(batch["first_observed_at"]),
                        self._timestamp(batch["registered_at"]),
                    )
                    > cutoff_time
                ):
                    excluded.append(
                        dict(batch_id=batch["batch_id"], reason="not_observed_at_cutoff")
                    )
                    continue
            eligible.append((rel, batch))
        superseded = {prior for _, batch in eligible for prior in batch.get("supersedes", [])}
        unique: dict[tuple, dict] = {}
        for rel, batch in sorted(eligible, key=lambda item: item[0]):
            if batch["batch_id"] in superseded:
                continue
            matched = False
            for row in batch["rows"]:
                if batch["dataset_id"] == "daily-prices" and row["price_basis"] != payload.get(
                    "price_basis", "unadjusted"
                ):
                    continue
                day = row.get("trading_date", row.get("period_end"))
                if (
                    payload.get("start")
                    and day < payload["start"]
                    or payload.get("end")
                    and day > payload["end"]
                ):
                    continue
                closure = closures.get((row.get("security_id"), day))
                if batch["dataset_id"] == "daily-prices" and closure:
                    excluded.append(
                        dict(
                            batch_id=batch["batch_id"],
                            trading_date=day,
                            reason="confirmed_market_closed",
                            evidence_refs=closure,
                        )
                    )
                    refs.extend(closure)
                    continue
                matched = True
                business_key: tuple
                if batch["dataset_id"] == "daily-prices":
                    business_key = (
                        row["security_id"],
                        row["trading_date"],
                        row["session"],
                        row["price_basis"],
                    )
                else:
                    business_key = (
                        row["company_id"],
                        row["metric_id"],
                        row["period_start"],
                        row["period_end"],
                        row["scope"],
                        row["currency"],
                    )
                key = (batch["dataset_id"], batch["source_id"], *business_key)
                if key in unique:
                    prior = unique[key]
                    if any(prior.get(field) != value for field, value in row.items()):
                        raise DomainError(
                            "RECORD_CONFLICT", "Conflicting active records share a business key", 4
                        )
                    prior["batch_refs"].append(rel)
                    prior["document_refs"] = sorted(
                        set(prior["document_refs"]) | set(batch["documents"])
                    )
                else:
                    unique[key] = dict(
                        row,
                        batch_id=batch["batch_id"],
                        source_id=batch["source_id"],
                        batch_refs=[rel],
                        document_refs=sorted(batch["documents"]),
                    )
            if matched:
                refs.append(rel)
        rows = list(unique.values())
        return dict(
            status="available" if rows else "missing",
            rows=rows,
            record_count=len(rows),
            artifact_refs=refs,
            excluded=excluded,
            coverage=dict(
                observed_records=len(rows), completeness="unknown_without_expected_calendar"
            ),
            issues=[
                dict(
                    code="COVERAGE_LIMITATION",
                    severity="warning",
                    message="Latest explicit revisions returned per source; no source priority or calendar completeness inferred",
                    retryable=False,
                )
            ],
        )

    @staticmethod
    def _timestamp(value):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise DomainError("TIMEZONE_REQUIRED", "Timestamp must include timezone")
        return result

    def _status(self, payload):
        saved = self.repo.read_json(
            f".research-local/operations/{identifier(payload['operation_id'])}.json"
        )
        return dict(status="ok", operation_status=saved["status"], operation=saved)

    def _resume(self, payload):
        saved = self.repo.read_json(
            f".research-local/operations/{identifier(payload['operation_id'])}.json"
        )
        if saved["operation"] in ("status", "resume"):
            raise DomainError("NOT_RESUMABLE", "Cannot recursively resume inspection")
        if saved["status"] == "completed":
            return dict(
                status="unchanged",
                result=saved["result"],
                artifact_refs=saved["result"].get("artifact_refs", []),
            )
        return self.execute(saved["operation"], saved["payload"])

    def _index(self, payload):
        index = [
            dict(
                path=path,
                dataset_id=batch["dataset_id"],
                batch_id=batch["batch_id"],
                subject_id=batch["subject_id"],
                record_count=batch["record_count"],
            )
            for path, batch in self.repo.batches()
        ]
        rel = ".research-local/index.json"
        self.repo.json(rel, index, immutable=False)
        return dict(status="rebuilt", batches=len(index), artifact_refs=[rel])
