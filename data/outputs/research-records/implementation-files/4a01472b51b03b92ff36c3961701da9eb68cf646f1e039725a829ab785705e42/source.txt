"""Deterministic expectation checks and one-request acquisition orchestration."""

from datetime import datetime, timedelta
from uuid import uuid4

from investment_domain import CoverageRequest, DomainError, EnsureRequest, ExpectationSet
from investment_repository import digest_bytes, fingerprint, identifier, utc_now

from .evidence_time import document_available


def detect(service, payload):
    request = CoverageRequest.model_validate(payload)
    repo = service.repo
    if not request.expectation_path.startswith("data/inputs/"):
        raise DomainError("INVALID_EXPECTATION_PATH", "Expectations must be versioned input files")
    path = repo.path(request.expectation_path)
    if not path.is_file():
        return dict(
            status="blocked",
            coverage=dict(expected_count=0, present_count=0),
            gaps=[dict(reason="unknown_expectation", retryable=False)],
            artifact_refs=[],
        )
    expectation = ExpectationSet.model_validate(repo.read_json(request.expectation_path))
    if expectation.dataset_id != request.dataset_id or expectation.subject_id != request.subject_id:
        raise DomainError(
            "EXPECTATION_SCOPE_MISMATCH", "Expectation has a different dataset or subject"
        )
    refs = [request.expectation_path]
    cutoff = request.information_cutoff
    mode = request.knowledge_mode
    dependencies = []
    for doc_id in expectation.evidence_document_ids:
        document, doc_refs = repo.effective_document(doc_id, mode, cutoff)
        dependencies.append(document)
        refs.append(doc_refs)
    as_of = request.as_of or datetime.fromisoformat(utc_now())
    # Historical expectations themselves must be knowable by the same cutoff.
    if cutoff and mode != "retrospective_explanation":
        if (
            expectation.published_at > cutoff
            or (
                mode == "live_observed"
                and max(expectation.observed_at, expectation.registered_at) > cutoff
            )
            or any(not document_available(doc, mode, cutoff) for doc in dependencies)
        ):
            return dict(
                status="blocked",
                coverage=dict(expected_count=0, present_count=0),
                gaps=[dict(reason="expectation_unavailable_at_cutoff", retryable=False)],
                artifact_refs=refs,
            )
        as_of = min(as_of, cutoff)
    observed = service._coverage(request.model_dump(mode="json", exclude_none=True))
    rows = [
        r for r in observed["rows"] if not request.source_id or r["source_id"] == request.source_id
    ]
    gaps, excluded = [], []
    expected_count = present_count = 0
    items = [x for x in expectation.items if request.start <= x.date <= request.end]
    unknown_dates = []
    if request.dataset_id == "daily-prices":
        dates = {x.date for x in items}
        day = request.start
        while day <= request.end:
            if day not in dates:
                unknown_dates.append(day.isoformat())
            day += timedelta(days=1)
    elif request.start < expectation.start or request.end > expectation.end or not items:
        gaps.append(dict(reason="unknown_expectation", retryable=False))
    for missing_day in unknown_dates:
        gaps.append(dict(date=missing_day, reason="unknown_expectation", retryable=False))
    for item in items:
        key = dict(date=item.date.isoformat())
        if not item.expected or item.due_at > as_of:
            excluded.append(
                dict(
                    **key,
                    reason="not_expected" if not item.expected else "not_due",
                    basis=item.reason,
                )
            )
            continue
        expected_count += 1
        if request.dataset_id == "daily-prices":
            matched = any(r["trading_date"] == key["date"] for r in rows)
            reason = "missing_observation"
            missing_metrics = []
        else:
            assert item.period_start is not None
            actual = {
                r["metric_id"]
                for r in rows
                if r["period_end"] == key["date"]
                and r["period_start"] == item.period_start.isoformat()
                and r["scope"] == item.scope
                and r["currency"] == item.currency
            }
            missing_metrics = sorted(set(item.metric_ids) - actual)
            matched = not missing_metrics
            reason = "disclosure_not_found"
            if item.report_document_id:
                report, report_refs = repo.effective_document(item.report_document_id, mode, cutoff)
                report_visible = True
                if cutoff and mode != "retrospective_explanation":
                    report_visible = document_available(report, mode, cutoff)
                if report_visible:
                    refs.append(report_refs)
                    reason = "processing_required"
        if matched:
            present_count += 1
        else:
            if mode == "live_observed":
                reason = "historically_unavailable"
            gaps.append(
                dict(
                    **key,
                    reason=reason,
                    missing_metrics=missing_metrics,
                    retryable=reason in ("missing_observation", "disclosure_not_found"),
                    report_document_id=item.report_document_id,
                )
            )
    if not gaps:
        status = "complete"
    elif all(g["reason"] == "processing_required" for g in gaps):
        status = "review_required"
    elif any(g["retryable"] for g in gaps):
        status = "partial"
    else:
        status = "blocked"
    return dict(
        status=status,
        coverage=dict(expected_count=expected_count, present_count=present_count),
        gaps=gaps,
        excluded=excluded,
        artifact_refs=sorted(set(refs + observed["artifact_refs"])),
        next_actions=[]
        if not gaps
        else ["ensure_plan" if status == "partial" else "resolve_evidence_or_review"],
        request=request.model_dump(mode="json", exclude_none=True),
    )


def source_hash(service, acquisition):
    if not acquisition:
        return None
    source = identifier(acquisition["source_id"])
    path = service.repo.path(f"research/sources/{source}/source.yaml")
    return digest_bytes(path.read_bytes()) if path.is_file() else None


def plan(service, payload):
    request = EnsureRequest.model_validate(payload)
    base = request.model_dump(mode="json", exclude_none=True, exclude={"acquisition"})
    before = detect(service, base)
    acquisition = request.acquisition.model_dump(mode="json") if request.acquisition else None
    if acquisition and request.source_id and acquisition["source_id"] != request.source_id:
        raise DomainError("SOURCE_SCOPE_MISMATCH", "Acquisition and requested source differ")
    if request.as_of and request.as_of > datetime.fromisoformat(utc_now()):
        raise DomainError("FUTURE_ENSURE", "Acquisition cannot ensure future observations")
    task = acquisition if before["status"] == "partial" else None
    path = service.repo.path(request.expectation_path)
    expectation_hash = (
        fingerprint(service.repo.read_json(request.expectation_path)) if path.is_file() else None
    )
    value = dict(
        request=base,
        before=before,
        acquisition=task,
        expectation_hash=expectation_hash,
        source_hash=source_hash(service, task),
        repository_revision=service.repo.revision(),
        created_at=utc_now(),
        max_requests=1,
    )
    plan_id = "ensure-" + fingerprint(value)
    value["plan_id"] = plan_id
    ref = f".research-local/ensure-plans/{plan_id}.json"
    service.repo.json(ref, value)
    return dict(
        status="planned" if task else before["status"],
        plan_id=plan_id,
        before=before,
        tasks=[task] if task else [],
        artifact_refs=[ref],
        next_actions=["ensure_apply"] if task else before.get("next_actions", []),
    )


def apply(service, payload):
    import fcntl

    plan_id = identifier(payload["plan_id"])
    lock_path = service.repo.path(f".research-local/ensure-locks/{plan_id}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            return _apply_locked(service, payload)
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _apply_locked(service, payload):
    plan_id = identifier(payload["plan_id"])
    value = service.repo.read_json(f".research-local/ensure-plans/{plan_id}.json")
    body = {k: v for k, v in value.items() if k != "plan_id"}
    if plan_id != "ensure-" + fingerprint(body):
        raise DomainError("PLAN_CHANGED", "Ensure plan was modified")
    receipt = f".research-local/ensure-results/{plan_id}.json"
    request = value["request"]
    exp_path = service.repo.path(request["expectation_path"])
    current_hash = (
        fingerprint(service.repo.read_json(request["expectation_path"]))
        if exp_path.is_file()
        else None
    )
    if current_hash != value["expectation_hash"]:
        raise DomainError("PLAN_STALE", "Expectation changed; create a new ensure plan", 4)
    if source_hash(service, value["acquisition"]) != value["source_hash"]:
        raise DomainError("PLAN_STALE", "Source configuration changed; create a new ensure plan", 4)
    before = detect(service, request)
    if service.repo.path(receipt).is_file():
        result = service.repo.read_json(receipt)
        for ref in result.get("artifact_refs", []):
            if not service.repo.path(ref).is_file():
                raise DomainError(
                    "PLAN_STALE", "Previously recorded evidence is missing; replan or restore it", 4
                )
        if result.get("acquisition"):
            service.repo.document(result["acquisition"]["document_id"])
        if fingerprint(before) != fingerprint(result["after"]):
            raise DomainError(
                "PLAN_STALE", "Coverage changed since this ensure result; create a new plan", 4
            )
        result["after"] = before
        result["replayed"] = True
        return result
    refs = []
    acquisition_result = None
    issue = None
    if before["status"] == "partial" and value["acquisition"]:
        # Changed repository state is rechecked, never blindly executes a stale need.
        try:
            delivery_ref = f".research-local/ensure-deliveries/{plan_id}.json"
            if service.repo.path(delivery_ref).is_file():
                acquisition_result = service.repo.read_json(delivery_ref)
            else:
                acquisition_result = service._collect(value["acquisition"])
                service.repo.json(delivery_ref, acquisition_result)
            refs.extend(acquisition_result.get("artifact_refs", []))
            if request["dataset_id"] == "daily-prices":
                prepared = service._prepare(
                    dict(document_id=acquisition_result["document_id"], dataset_id="daily-prices")
                )
                checked = service._validate(dict(candidate_id=prepared["candidate_id"]))
                if checked["status"] != "eligible":
                    raise DomainError(
                        "QUALITY_BLOCKED", "Acquired records did not pass deterministic validation"
                    )
                ingestion = service._ingest_plan(dict(candidate_id=prepared["candidate_id"]))
                result = service._ingest_apply(dict(plan_id=ingestion["plan_id"]))
                refs.extend(result["artifact_refs"])
        except DomainError as exc:
            issue = dict(code=exc.code, message=exc.message)
    after = detect(service, request)
    status = after["status"]
    actions = after.get("next_actions", [])
    if acquisition_result and request["dataset_id"] == "financial-facts" and status != "complete":
        status = "review_required"
        actions = [
            "verify_report_identity",
            "prepare",
            "validate",
            "review",
            "ingest_plan",
            "ingest_apply",
            "detect_gaps",
        ]
    if issue and status != "complete":
        status = "blocked"
    result = dict(
        status=status,
        plan_id=plan_id,
        before=before,
        after=after,
        acquisition=acquisition_result,
        issues=[issue] if issue else [],
        artifact_refs=refs,
        next_actions=actions,
    )
    # Durable evidence belongs in Git; local receipt supports idempotent replay.
    audit = f"data/outputs/research-records/{plan_id}/{uuid4().hex}/ensure.json"
    result["artifact_refs"] = sorted(set(refs + [audit]))
    service.repo.json(audit, result)
    service.repo.json(receipt, result)
    return result
