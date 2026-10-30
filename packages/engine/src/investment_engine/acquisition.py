"""Bounded, append-only acquisition tasks that survive deletion of local caches."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from investment_domain import DomainError
from investment_repository import fingerprint, identifier, utc_now

BASE = "data/outputs/research-records/acquisition"


def _only(payload, fields):
    if set(payload) - set(fields):
        raise DomainError("INVALID_REQUEST", "Unsupported acquisition fields")


def _connector(service):
    if service.connector_service is None:
        raise DomainError("CONNECTOR_UNAVAILABLE", "Acquisition requires a connector service")
    return service.connector_service


def _archive_delivery(service, response, source_id, title):
    delivery = response["delivery"]
    return service._import(
        dict(
            path=delivery["path"],
            source_id=source_id,
            title=title or source_id,
            origin_url=response["origin_url"],
            collection_context=dict(delivery=delivery),
        )
    )


def _source_wait(service, binding_id):
    from investment_connectors.providers import load_binding

    provider, _ = load_binding(service.repo.root, binding_id)
    folder = service.repo.path(f"{BASE}/source-status/{provider.provider_id}")
    waits = []
    for path in folder.glob("*.json") if folder.exists() else []:
        receipt = service.repo.read_json(path.relative_to(service.repo.root).as_posix())
        waits.append(datetime.fromisoformat(receipt["retry_at"]))
    latest = max(waits) if waits else datetime.now(timezone.utc)
    return max(0.0, (latest - datetime.now(timezone.utc)).total_seconds())


def _record_retry(service, binding_id, exc):
    if not getattr(exc, "retryable", False):
        return
    delay = getattr(exc, "retry_after_seconds", None)
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay if delay is not None else 60)
    from investment_connectors.providers import load_binding

    provider, _ = load_binding(service.repo.root, binding_id)
    service.repo.json(
        f"{BASE}/source-status/{provider.provider_id}/{uuid4().hex}.json",
        dict(
            recorded_at=utc_now(),
            retry_at=retry_at.isoformat(),
            issue_code=getattr(exc, "code", "SOURCE_FAILED"),
        ),
    )


def _check_source_wait(service, binding_id):
    from investment_connectors import ConnectorError

    wait = _source_wait(service, binding_id)
    if wait > 0:
        raise ConnectorError(
            "SOURCE_RETRY_PENDING",
            "Provider cooldown has not elapsed",
            retryable=True,
            retry_after_seconds=wait,
        )


def discover(service, payload):
    _only(payload, {"binding_id", "parameters", "max_pages", "resume_discovery_id"})
    binding_id = identifier(payload["binding_id"])
    from investment_connectors.providers import load_binding

    provider, binding = load_binding(service.repo.root, binding_id)
    maximum = payload.get("max_pages", 1)
    if (
        not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or not 1 <= maximum <= provider.max_pages
    ):
        raise DomainError("INVALID_REQUEST", "Discovery page count exceeds provider bound")
    parameters = payload.get("parameters", {})
    pages, entries, refs, issues = [], {}, [], []
    if payload.get("resume_discovery_id"):
        previous = _discovery(service, payload["resume_discovery_id"])
        _check_configuration(service, previous)
        if previous["binding_id"] != binding_id or previous["next_parameters"] is None:
            raise DomainError(
                "INVALID_REQUEST", "Discovery cannot resume this binding or completed cursor"
            )
        pages = list(previous["pages"])
        entries = {item["item_id"]: item for item in previous["entries"]}
        parameters = previous["next_parameters"]
    for _ in range(maximum):
        try:
            _check_source_wait(service, binding_id)
            response = _connector(service).execute(
                "discover", dict(binding_id=binding_id, parameters=parameters)
            )
        except Exception as exc:
            _record_retry(service, binding_id, exc)
            issues.append(
                dict(
                    code=getattr(exc, "code", type(exc).__name__),
                    parameters=parameters,
                    retryable=getattr(exc, "retryable", False),
                )
            )
            break
        imported = (
            _archive_delivery(service, response, binding_id, "Report discovery listing")
            if response.get("delivery")
            else dict(document_id=None, artifact_refs=[])
        )
        refs.extend(imported["artifact_refs"])
        pages.append(
            dict(
                parameters=parameters,
                document_id=imported["document_id"],
                origin_url=response["origin_url"],
            )
        )
        for item in response["entries"]:
            item_id = "item-" + fingerprint(dict(binding_id=binding_id, url=item["url"]))[:24]
            entries[item_id] = dict(
                item, item_id=item_id, listing_document_id=imported["document_id"]
            )
        parameters = response["next_parameters"]
        if parameters is None:
            break
    body = dict(
        binding_id=binding_id,
        provider_id=provider.provider_id,
        provider_fingerprint=fingerprint(asdict(provider)),
        binding_fingerprint=fingerprint(asdict(binding)),
        recorded_at=utc_now(),
        pages=pages,
        entries=list(entries.values()),
        next_parameters=parameters,
        resumed_from=payload.get("resume_discovery_id"),
        issues=issues,
        scope="configured_date_requests_not_calendar_or_source_coverage"
        if provider.discovery_mode == "date_window"
        else "fetched_listing_pages_only",
        limitations=[
            "Matched links do not certify all report periods, release times or extracted fields"
        ],
    )
    discovery_id = "discovery-" + fingerprint(body)[:24]
    ref = f"{BASE}/discoveries/{discovery_id}.json"
    service.repo.json(ref, dict(body, discovery_id=discovery_id))
    return dict(
        status=("partial" if entries else "blocked") if issues else "discovered",
        issues=issues,
        discovery_id=discovery_id,
        entries=body["entries"],
        next_parameters=parameters,
        scope=body["scope"],
        artifact_refs=refs + [ref],
    )


def _discovery(service, discovery_id):
    value = service.repo.read_json(f"{BASE}/discoveries/{identifier(discovery_id)}.json")
    body = {key: val for key, val in value.items() if key != "discovery_id"}
    if "discovery-" + fingerprint(body)[:24] != discovery_id:
        raise DomainError("DISCOVERY_CHANGED", "Discovery manifest was changed")
    for page in value["pages"]:
        if page.get("document_id"):
            service.repo.document(page["document_id"])
    return value


def _check_configuration(service, discovery):
    from investment_connectors.providers import load_binding

    provider, binding = load_binding(service.repo.root, discovery["binding_id"])
    for key, config in (("provider_fingerprint", provider), ("binding_fingerprint", binding)):
        current = asdict(config)
        compatible = [current]
        for optional, default in (
            ("discovery_mode", "html_links"),
            ("window_days", 31),
            ("request_method", "GET"),
            ("fixed_parameters", {}),
            ("parameters", {}),
        ):
            if current.get(optional) == default:
                compatible += [
                    {k: v for k, v in config.items() if k != optional}
                    for config in list(compatible)
                ]
        if discovery.get(key) and discovery[key] not in {
            fingerprint(config) for config in compatible
        }:
            raise DomainError(
                "SOURCE_CONFIG_CHANGED", "Provider binding changed; create a new discovery"
            )


def _reuse_archived(service, task, item):
    candidates = []
    for path in service.repo.path("data/inputs/collection-records").glob("*/*/*/collection.json"):
        receipt = service.repo.read_json(path.relative_to(service.repo.root).as_posix())
        if receipt.get("origin_url") == item["url"] and receipt.get("document_id"):
            candidates.append(receipt)
    if not candidates:
        return None
    prior = max(candidates, key=lambda value: value["observed_at"])
    document, _ = service.repo.document(prior["document_id"])
    return service._import(
        dict(
            path=str(service.repo.path(document["path"])),
            source_id=task["binding_id"],
            title=item["title"] or task["binding_id"],
            origin_url=item["url"],
            collection_context=dict(
                reuse_archived=True,
                reused_document_id=document["document_id"],
                reused_collection_id=prior["collection_id"],
                limitation="Archived version explicitly reused; remote revision not checked",
            ),
        )
    )


def plan(service, payload):
    _only(payload, {"discovery_id", "dataset_id", "item_ids"})
    from .datasets import MODELS

    dataset = payload["dataset_id"]
    if dataset not in MODELS or dataset == "daily-prices":
        raise DomainError(
            "INVALID_REQUEST", "Report acquisition needs a registered reviewed dataset"
        )
    discovery = _discovery(service, payload["discovery_id"])
    selected = payload.get("item_ids", [item["item_id"] for item in discovery["entries"]])
    if not isinstance(selected, list) or not selected or len(selected) != len(set(selected)):
        raise DomainError("INVALID_REQUEST", "Select distinct discovered items")
    available = {item["item_id"]: item for item in discovery["entries"]}
    if set(selected) - set(available):
        raise DomainError("INVALID_REQUEST", "Task items must come from discovery evidence")
    body = dict(
        discovery_id=discovery["discovery_id"],
        binding_id=discovery["binding_id"],
        dataset_id=dataset,
        items=[available[key] for key in sorted(selected)],
    )
    task_id = "acquisition-" + fingerprint(body)[:24]
    ref = f"{BASE}/{task_id}/plan.json"
    service.repo.json(ref, dict(body, task_id=task_id))
    return dict(status="planned", task_id=task_id, items=body["items"], artifact_refs=[ref])


def _plan(service, task_id):
    task_id = identifier(task_id)
    value = service.repo.read_json(f"{BASE}/{task_id}/plan.json")
    body = {key: val for key, val in value.items() if key != "task_id"}
    if "acquisition-" + fingerprint(body)[:24] != task_id:
        raise DomainError("TASK_CHANGED", "Task plan changed")
    _discovery(service, value["discovery_id"])
    return value


def _state(service, task):
    folder = service.repo.path(f"{BASE}/{task['task_id']}/events")
    previous = None
    latest = None
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        event = service.repo.read_json(path.relative_to(service.repo.root).as_posix())
        body = {key: val for key, val in event.items() if key != "event_hash"}
        if fingerprint(body) != event["event_hash"] or event["previous_hash"] != previous:
            raise DomainError("TASK_EVENT_CHANGED", "Acquisition event chain changed")
        previous, latest = event["event_hash"], event
    if latest is None:
        return dict(
            items=[dict(item, stage="pending_fetch", attempts=0) for item in task["items"]],
            sequence=0,
            event_hash=None,
        )
    return latest


def _event(service, task_id, previous, items):
    event = dict(
        task_id=task_id,
        sequence=previous["sequence"] + 1,
        previous_hash=previous["event_hash"],
        recorded_at=utc_now(),
        items=items,
    )
    event["event_hash"] = fingerprint(event)
    ref = f"{BASE}/{task_id}/events/{event['sequence']:06d}.json"
    service.repo.json(ref, event)
    return event


@contextmanager
def _task_lock(service, task_id):
    import fcntl

    path = service.repo.path(f".research-local/acquisition/{task_id}.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def status(service, payload):
    with service.repo.read_snapshot():
        _only(payload, {"task_id"})
        task = _plan(service, payload["task_id"])
        current = _state(service, task)
        stages = {item["stage"] for item in current["items"]}
        verified = [item for item in current["items"] if item["stage"] == "verified"]
        if verified:
            service.repo.batches()
            for item in verified:
                service.repo.document(item["document_id"])
                for ref in item["ingest_refs"]:
                    if not service.repo.path(ref).is_file():
                        raise DomainError(
                            "TASK_EVIDENCE_MISSING", "Verified acquisition evidence is missing"
                        )
        overall = (
            "complete"
            if stages == {"verified"}
            else "completed_with_skips"
            if stages <= {"verified", "skipped"}
            else "blocked"
            if stages & {"failed", "rejected"}
            else "pending"
        )
        return dict(
            status=overall,
            task_id=task["task_id"],
            items=current["items"],
            artifact_refs=[f"{BASE}/{task['task_id']}/plan.json"],
            scope="selected_documents_and_candidates_not_full_research_coverage",
        )


def _restore(service, item):
    if item.get("candidate_ref"):
        candidate = service.repo.read_json(item["candidate_ref"])
        cid = candidate["candidate_id"]
        service.repo.json(f".research-local/candidates/{cid}.json", candidate)
        service._candidate(cid)
    for ref in item.get("review_refs", []):
        review = service.repo.read_json(ref)
        if fingerprint(review) != item.get("review_hashes", {}).get(ref):
            raise DomainError("REVIEW_CHANGED", "Persisted acquisition review changed")
        service.repo.json(
            f".research-local/reviews/{review['candidate_id']}/{Path(ref).name}", review
        )


def run(service, payload):
    _only(payload, {"task_id", "max_items", "submissions", "reuse_archived"})
    task = _plan(service, payload["task_id"])
    maximum = payload.get("max_items", 1)
    if not isinstance(maximum, int) or isinstance(maximum, bool) or not 1 <= maximum <= 20:
        raise DomainError("INVALID_REQUEST", "Run handles 1..20 items")
    if not isinstance(payload.get("reuse_archived", False), bool):
        raise DomainError("INVALID_REQUEST", "reuse_archived must be boolean")
    submissions = payload.get("submissions", {})
    if not isinstance(submissions, dict) or set(submissions) - {
        x["item_id"] for x in task["items"]
    }:
        raise DomainError("INVALID_REQUEST", "Submission references an unknown task item")
    with _task_lock(service, task["task_id"]):
        state = _state(service, task)
        items = state["items"]
        processed = 0
        for item in items:
            if processed >= maximum:
                break
            submission = submissions.get(item["item_id"], {})
            _only(submission, {"records", "review", "supersedes", "parser_version", "skip_reason"})
            if "skip_reason" in submission:
                reason = submission["skip_reason"]
                if (
                    not isinstance(reason, str)
                    or not reason.strip()
                    or len(reason) > 2000
                    or set(submission) != {"skip_reason"}
                    or item["stage"] in {"verified", "approved"}
                    or item.get("ingest_refs")
                    or any(
                        service.repo.read_json(ref).get("decision") == "approved"
                        for ref in item.get("review_refs", [])
                    )
                ):
                    raise DomainError(
                        "INVALID_REQUEST", "Skip requires a reason and an unapproved item"
                    )
                if item["stage"] != "skipped":
                    item.update(stage="skipped", skip_reason=reason.strip())
                    item.pop("issue", None)
                    state = _event(service, task["task_id"], state, items)
                    processed += 1
                continue
            if item["stage"] == "skipped" and submission:
                raise DomainError("INVALID_REQUEST", "Skipped items require a new task selection")
            if item["stage"] in {"verified", "skipped"}:
                continue
            if item.get("retry_at") and datetime.fromisoformat(item["retry_at"]) > datetime.now(
                timezone.utc
            ):
                continue
            if (
                item["stage"] in {"awaiting_extraction", "awaiting_review", "rejected"}
                and not submission
            ):
                continue
            processed += 1
            item["attempts"] += 1
            try:
                if not item.get("document_id"):
                    _check_configuration(service, _discovery(service, task["discovery_id"]))
                    imported = (
                        _reuse_archived(service, task, item)
                        if payload.get("reuse_archived", False)
                        else None
                    )
                    if imported is not None:
                        item["retrieval_mode"] = "explicit_archived_version_reuse"
                    else:
                        _check_source_wait(service, task["binding_id"])
                        response = _connector(service).execute(
                            "collect_item", dict(binding_id=task["binding_id"], url=item["url"])
                        )
                        imported = _archive_delivery(
                            service, response, task["binding_id"], item["title"]
                        )
                        item["retrieval_mode"] = "fetched"
                    item.update(
                        document_id=imported["document_id"],
                        stage="awaiting_extraction",
                        collection_refs=imported["artifact_refs"],
                    )
                    state = _event(service, task["task_id"], state, items)
                service.repo.document(item["document_id"])
                auto_prepare = False
                if not item.get("candidate_id") and task["dataset_id"] == "market-observations":
                    from investment_connectors.providers import load_binding
                    from investment_connectors.observations import OBSERVATION_PARSERS

                    provider, _ = load_binding(service.repo.root, task["binding_id"])
                    auto_prepare = provider.connector_id in OBSERVATION_PARSERS
                if "records" in submission or auto_prepare:
                    from investment_connectors.providers import load_binding

                    _, binding = load_binding(service.repo.root, task["binding_id"])
                    for record in submission.get("records", []):
                        for field, expected in (
                            ("company_id", binding.subject_id),
                            ("security_id", binding.security_id),
                        ):
                            if field in record and (not expected or record[field] != expected):
                                raise DomainError(
                                    "SUBJECT_MISMATCH",
                                    "Candidate does not match the task object binding",
                                )
                    prepared = service._prepare(
                        dict(
                            document_id=item["document_id"],
                            dataset_id=task["dataset_id"],
                            parser_source_id=task["binding_id"],
                            records=submission.get("records"),
                            supersedes=submission.get("supersedes", []),
                            parser_version=submission.get(
                                "parser_version", "reviewed-extraction-v1"
                            ),
                        )
                    )
                    cid = prepared["candidate_id"]
                    ref = f"{BASE}/{task['task_id']}/candidates/{cid}.json"
                    service.repo.json(ref, service._candidate(cid))
                    item.update(
                        candidate_id=cid,
                        candidate_ref=ref,
                        review_refs=[],
                        review_hashes={},
                        stage="awaiting_review",
                    )
                    state = _event(service, task["task_id"], state, items)
                if item.get("candidate_id"):
                    _restore(service, item)
                    if item.get("review_refs") and item["stage"] == "failed":
                        last_review = service.repo.read_json(item["review_refs"][-1])
                        item["stage"] = (
                            "approved" if last_review["decision"] == "approved" else "rejected"
                        )
                    checked = service._validate(dict(candidate_id=item["candidate_id"]))
                    if checked["status"] not in {"eligible", "review_required"}:
                        raise DomainError("QUALITY_BLOCKED", "Candidate needs correction")
                    if submission.get("review"):
                        review = service._review(
                            dict(submission["review"], candidate_id=item["candidate_id"])
                        )
                        ref = f"{BASE}/{task['task_id']}/reviews/{Path(review['review_ref']).name}"
                        service.repo.json(ref, service.repo.read_json(review["review_ref"]))
                        item.setdefault("review_refs", []).append(ref)
                        item.setdefault("review_hashes", {})[ref] = fingerprint(
                            service.repo.read_json(ref)
                        )
                        item["stage"] = "approved" if review["status"] == "approved" else "rejected"
                        state = _event(service, task["task_id"], state, items)
                    if item["stage"] == "approved" or checked["status"] == "eligible":
                        proposed = service._ingest_plan(dict(candidate_id=item["candidate_id"]))
                        receipt = service._ingest_apply(dict(plan_id=proposed["plan_id"]))
                        item.update(stage="verified", ingest_refs=receipt["artifact_refs"])
                        # Read all committed batches to verify archive hashes after admission.
                        with service.repo.read_snapshot():
                            service.repo.batches()
                item.pop("issue", None)
                item.pop("retry_at", None)
            except Exception as exc:
                _record_retry(service, task["binding_id"], exc)
                retryable = getattr(exc, "retryable", False)
                item.update(
                    stage="failed",
                    issue=dict(code=getattr(exc, "code", type(exc).__name__), retryable=retryable),
                )
                if retryable:
                    delay = getattr(exc, "retry_after_seconds", None)
                    item["retry_at"] = (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=delay if delay is not None else 60)
                    ).isoformat()
                failure_id = "collection-" + uuid4().hex
                stamp = utc_now()
                service.repo.json(
                    f"data/inputs/collection-records/{task['binding_id']}/{stamp[:4]}/{failure_id}/collection.json",
                    dict(
                        collection_id=failure_id,
                        status="failed",
                        observed_at=stamp,
                        source_id=task["binding_id"],
                        task_id=task["task_id"],
                        item_id=item["item_id"],
                        issue=item["issue"],
                    ),
                )
            state = _event(service, task["task_id"], state, items)
    return status(service, dict(task_id=task["task_id"]))
