"""Append-only, reviewed publication assertions alongside immutable originals."""

from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from investment_domain import DomainError, PublicationAssertion

from . import fingerprint, utc_now


def timestamp(value):
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed is None or parsed.tzinfo is None:
        raise DomainError("TIMEZONE_REQUIRED", "Publication time requires timezone")
    return parsed


def publication_bounds(value):
    assertion = PublicationAssertion.model_validate(value)
    if assertion.precision == "unknown":
        return None, None
    if assertion.precision == "instant":
        assert assertion.published_at is not None
        lower = upper = assertion.published_at
    elif assertion.precision == "interval":
        assert assertion.earliest is not None and assertion.latest is not None
        lower, upper = assertion.earliest, assertion.latest
    else:
        assert assertion.timezone is not None and assertion.date is not None
        zone = ZoneInfo(assertion.timezone)
        lower = datetime.combine(assertion.date, time.min, zone)
        # The next local midnight is a conservative upper bound, NOT a claimed publication instant.
        upper = datetime.combine(assertion.date + timedelta(days=1), time.min, zone)
    return lower.astimezone(timezone.utc).isoformat(), upper.astimezone(timezone.utc).isoformat()


def original_publication(document):
    return (
        dict(precision="instant", published_at=document["published_at"])
        if document.get("published_at")
        else dict(precision="unknown")
    )


def revisions(repo, document_id):
    document, original_path = repo.document(document_id)
    directory = Path(original_path).parent / "metadata-revisions"
    records = {}
    children = {}
    for path in sorted(repo.path(directory.as_posix()).glob("*.json")):
        relative = path.relative_to(repo.root).as_posix()
        record = repo.read_json(relative)
        body = {key: value for key, value in record.items() if key != "revision_id"}
        revision_id = "metadata-" + fingerprint(body)
        if record.get("revision_id") != revision_id or path.stem != revision_id:
            raise DomainError("METADATA_REVISION_INTEGRITY", relative, 4)
        if (
            record.get("document_id") != document_id
            or record.get("document_sha256") != document["sha256"]
        ):
            raise DomainError(
                "METADATA_REVISION_INTEGRITY", "Revision does not bind this original", 4
            )
        PublicationAssertion.model_validate(record["publication"])
        timestamp(record["recorded_at"])
        evidence, _ = repo.document(record["evidence_document_id"])
        if evidence["sha256"] != record["evidence_sha256"]:
            raise DomainError("METADATA_REVISION_INTEGRITY", "Publication evidence changed", 4)
        for support in record.get("supporting_documents", []):
            supporting, _ = repo.document(support["document_id"])
            if supporting["sha256"] != support["sha256"]:
                raise DomainError("METADATA_REVISION_INTEGRITY", "Supporting evidence changed", 4)
        parent = record["previous_revision_id"]
        if parent in children:
            raise DomainError(
                "METADATA_REVISION_CONFLICT", "Branched publication revision history", 4
            )
        children[parent] = revision_id
        records[revision_id] = (record, relative)
    ordered: list[tuple[dict, str]] = []
    current = "original"
    prior_assertion = PublicationAssertion.model_validate(
        original_publication(document)
    ).model_dump(mode="json")
    while current in children:
        child = children[current]
        if child in {item[0]["revision_id"] for item in ordered}:
            raise DomainError("METADATA_REVISION_CONFLICT", "Cyclic revision history", 4)
        record, relative = records[child]
        if record["previous_publication"] != prior_assertion:
            raise DomainError(
                "METADATA_REVISION_INTEGRITY", "Previous publication assertion differs", 4
            )
        if ordered and timestamp(record["recorded_at"]) < timestamp(ordered[-1][0]["recorded_at"]):
            raise DomainError(
                "METADATA_REVISION_CONFLICT", "Revision registration time reversed", 4
            )
        ordered.append((record, relative))
        prior_assertion = record["publication"]
        current = child
    if len(ordered) != len(records):
        raise DomainError("METADATA_REVISION_CONFLICT", "Orphaned publication revision", 4)
    return ordered


def append_revision(repo, request):
    """Request has already undergone excerpt checking and explicit human/agent review."""
    with repo.lock():
        document, original_path = repo.document(request.document_id)
        history = revisions(repo, request.document_id)
        current = history[-1][0]["revision_id"] if history else "original"
        expected = request.expected_revision_id or "original"
        if expected != current:
            raise DomainError("STALE_METADATA_REVISION", "Review must bind the latest assertion", 4)
        evidence, _ = repo.document(request.evidence_document_id)
        previous = history[-1][0]["publication"] if history else original_publication(document)
        body = dict(
            document_id=request.document_id,
            document_sha256=document["sha256"],
            previous_revision_id=current,
            previous_publication=PublicationAssertion.model_validate(previous).model_dump(
                mode="json"
            ),
            publication=request.publication.model_dump(mode="json"),
            evidence_document_id=request.evidence_document_id,
            evidence_sha256=evidence["sha256"],
            supporting_documents=[
                dict(document_id=identifier, sha256=repo.document(identifier)[0]["sha256"])
                for identifier in request.supporting_document_ids
            ],
            locator=request.locator,
            excerpt=request.excerpt,
            reviewer=request.reviewer,
            notes=request.notes,
            recorded_at=utc_now(),
            review_scope="Reviewer attests publication evidence; identity is not authenticated",
        )
        revision_id = "metadata-" + fingerprint(body)
        record = dict(body, revision_id=revision_id)
        relative = (
            Path(original_path).parent / "metadata-revisions" / (revision_id + ".json")
        ).as_posix()
        repo.json(relative, record)
    return dict(
        status="registered", revision_id=revision_id, artifact_refs=[original_path, relative]
    )


def effective_document(
    repo, document_id, mode="retrospective_explanation", cutoff=None, revision_id=None
):
    if mode not in ("retrospective_explanation", "historical_reconstruction", "live_observed"):
        raise DomainError("INVALID_MODE", mode)
    if mode != "retrospective_explanation" and cutoff is None:
        raise DomainError("CUTOFF_REQUIRED", mode)
    cutoff = timestamp(cutoff) if cutoff is not None else None
    document, original_path = repo.document(document_id)
    history = revisions(repo, document_id)
    selected = None
    if revision_id is not None and revision_id != "original":
        selected = next((item for item in history if item[0]["revision_id"] == revision_id), None)
        if selected is None:
            raise DomainError("METADATA_REVISION_NOT_FOUND", revision_id)
    elif revision_id is None:
        eligible = [
            item
            for item in history
            if mode != "live_observed" or timestamp(item[0]["recorded_at"]) <= cutoff
        ]
        selected = eligible[-1] if eligible else None
    assertion = selected[0]["publication"] if selected else original_publication(document)
    assertion = PublicationAssertion.model_validate(assertion).model_dump(mode="json")
    lower, upper = publication_bounds(assertion)
    result = deepcopy(document)
    result.update(
        publication_assertion=assertion,
        publication_precision=assertion["precision"],
        availability_lower_bound=lower,
        availability_upper_bound=upper,
        published_at=assertion.get("published_at"),
        metadata_revision_id=selected[0]["revision_id"] if selected else "original",
        metadata_revision_recorded_at=selected[0]["recorded_at"] if selected else None,
        metadata_evidence_refs=list(
            dict.fromkeys(
                [selected[0]["evidence_document_id"]]
                + [item["document_id"] for item in selected[0].get("supporting_documents", [])]
            )
        )
        if selected
        else [],
    )
    return result, selected[1] if selected else original_path
