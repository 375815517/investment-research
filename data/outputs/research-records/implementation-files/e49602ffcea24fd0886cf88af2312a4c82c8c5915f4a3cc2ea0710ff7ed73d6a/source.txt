"""Immutable input bundles pin evidence, metadata selections and executable sources."""

import subprocess
from pathlib import Path

from investment_domain import DomainError, FreezeInputsRequest, VerifyBundleRequest
from investment_repository import digest_bytes, fingerprint, identifier

from .profiles import assess
from .transforms import replay

BUNDLE_VERSION = "input-bundle-v1"


def _code_manifest(root, archived_contents):
    files = []

    def capture(path, relative):
        current = root
        for component in Path(relative).parts:
            current = current / component
            if current.is_symlink():
                raise DomainError("UNSAFE_PATH", relative)
        content = path.read_bytes()
        sha = digest_bytes(content)
        archive_ref = f"data/outputs/research-records/implementation-files/{sha}/source.txt"
        archived_contents[archive_ref] = content
        return dict(path=relative, sha256=sha, archive_ref=archive_ref)

    for folder in ("packages", "apps", "ai/tooling", "scripts"):
        directory = root / folder
        if directory.is_dir():
            for path in directory.rglob("*.py"):
                if any(part in {"__pycache__", "build", "dist", ".venv"} for part in path.parts):
                    continue
                if path.is_symlink():
                    raise DomainError("UNSAFE_PATH", str(path))
                files.append(capture(path, path.relative_to(root).as_posix()))
    for relative in ("uv.lock", "pyproject.toml"):
        path = root / relative
        if path.is_file():
            files.append(capture(path, relative))
    try:
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=5,
            text=True,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        head = None
    return dict(
        git_head_at_freeze=head,
        files=sorted(files, key=lambda f: f["path"]),
        note="Exact source and lock bytes are content-addressed archives; HEAD alone does not certify a clean tree. Archives are never automatically executed.",
    )


def _pinned_files(service, assessment, definition_refs=()):
    refs = set(assessment["artifact_refs"]) | set(definition_refs)
    has_v2 = any(
        key["expected"]["dataset_id"] in {"financial-observations", "operating-observations"}
        for key in assessment["audit"]["keys"]
    )
    scales_ref = "research/units/scales.json"
    if has_v2 or service.repo.path(scales_ref).is_file():
        refs.add(scales_ref)
    for key in assessment["audit"]["keys"]:
        if key["expected"]["dataset_id"] not in {
            "financial-observations",
            "operating-observations",
        }:
            continue
        for row in key["rows"]:
            metric, version = (
                identifier(row["metric_id"]),
                identifier(row.get("metric_version", "1")),
            )
            ref = f"research/metrics/{metric}/v{version}.json"
            if not service.repo.path(ref).is_file():
                raise DomainError("BUNDLE_DEFINITION_MISSING", ref)
            refs.add(ref)
            from investment_domain.measurements import MetricDefinition, SourceObservation

            definition = MetricDefinition.model_validate(service.repo.read_json(ref))
            if definition.dataset_id != key["expected"]["dataset_id"]:
                raise DomainError("BUNDLE_DEFINITION_MISMATCH", ref)
            definition.check_observation(
                SourceObservation.model_validate(
                    {field: row[field] for field in SourceObservation.model_fields if field in row}
                )
            )

    documents, selections = set(), {}
    for key in assessment["audit"]["keys"]:
        for row in key["rows"]:
            documents.update(row.get("document_refs", []))
            refs.update(row.get("document_metadata_refs", []))
            selections.update(row.get("metadata_revision_ids", {}))
            refs.update(row.get("batch_refs", []))
    pending_batches = [ref for ref in refs if ref.endswith("/batch.json")]
    seen_batches = set()
    while pending_batches:
        ref = pending_batches.pop()
        if ref in seen_batches:
            continue
        seen_batches.add(ref)
        batch = service.repo.read_json(ref)
        refs.update(file["path"] for file in batch["files"])
        documents.update(batch.get("documents", []))
        for dependency in batch.get("dependency_batches", []):
            refs.add(dependency)
            pending_batches.append(dependency)
    pinned_documents = {}
    for doc_id in sorted(documents):
        doc, metadata_ref = service.repo.document(doc_id)
        refs.update((metadata_ref, doc["path"]))
        selection = selections.get(doc_id, "original")
        pinned_documents[doc_id] = dict(original_sha256=doc["sha256"], metadata_revision=selection)
    # Metadata revisions cite evidence originals. Pin their exact bytes and original
    # metadata; do not resolve those evidence documents through future revisions.
    pending = [ref for ref in refs if "/metadata-revisions/" in ref]
    visited = set()
    while pending:
        ref = pending.pop()
        if ref in visited:
            continue
        visited.add(ref)
        revision = service.repo.read_json(ref)
        evidence_ids = list(revision.get("evidence_document_ids", []))
        if revision.get("evidence_document_id"):
            evidence_ids.append(revision["evidence_document_id"])
        evidence_ids.extend(item.get("document_id") for item in revision.get("evidence", []))
        evidence_ids.extend(
            item["document_id"] for item in revision.get("supporting_documents", [])
        )
        for evidence_id in filter(None, evidence_ids):
            evidence, metadata_ref = service.repo.document(evidence_id)
            refs.update((metadata_ref, evidence["path"]))
        previous = revision.get("previous_revision_id")
        if previous and previous != "original":
            parent = str(Path(ref).parent / (previous + ".json"))
            refs.add(parent)
            pending.append(parent)
    manifest = []
    for ref in sorted(refs):
        path = service.repo.path(ref)
        if not path.is_file():
            raise DomainError("BUNDLE_INPUT_MISSING", ref)
        manifest.append(dict(path=ref, sha256=digest_bytes(path.read_bytes())))
    return manifest, pinned_documents


def freeze(service, payload):
    request = FreezeInputsRequest.model_validate(payload)
    archived_contents: dict[str, bytes] = {}
    with service.repo.read_snapshot():
        assessment = assess(service, request.profile.model_dump(mode="json"))
        files, documents = _pinned_files(service, assessment, request.profile.definition_refs)
        transformations = []
        frozen_rows = {
            (key["key_id"], fingerprint(row))
            for key in assessment["audit"]["keys"]
            for row in key["rows"]
        }
        for transformation_id in request.transformation_ids:
            ref = f"data/outputs/research-records/transformations/{transformation_id}/run.json"
            run = service.repo.read_json(ref)
            if "normalization-" + fingerprint(run)[:32] != transformation_id:
                raise DomainError("TRANSFORM_CHANGED", transformation_id, 4)
            for record in run["records"]:
                if (record["key_id"], record["input_sha256"]) not in frozen_rows:
                    raise DomainError("TRANSFORM_INPUT_NOT_IN_BUNDLE", record["key_id"], 4)
            replayed = replay(run)
            files.append(dict(path=ref, sha256=digest_bytes(service.repo.path(ref).read_bytes())))
            transformations.append(
                dict(transformation_id=transformation_id, path=ref, replayed_values=replayed)
            )
        files.sort(key=lambda item: item["path"])
        bundle = dict(
            bundle_version=BUNDLE_VERSION,
            label=request.label,
            profile=request.profile.model_dump(mode="json"),
            assessment=assessment,
            evidence_files=files,
            documents=documents,
            implementation=_code_manifest(service.repo.root, archived_contents),
            transformations=transformations,
            limitations=[
                "Freezing a blocked or limited input set preserves its limitations; it does not certify readiness",
                "Verification reads pinned files and rows, never substitutes newly available data",
                "Source and implementation hashes establish reproducibility boundaries, not source authenticity",
            ],
        )
    for archive_ref, content in archived_contents.items():
        service.repo.write(archive_ref, content)
    bundle_id = "inputs-" + fingerprint(bundle)[:32]
    path = f"data/outputs/research-records/input-bundles/{bundle_id}/bundle.json"
    service.repo.json(path, dict(bundle_id=bundle_id, **bundle))
    return dict(
        status="frozen",
        bundle_id=bundle_id,
        assessment_status=assessment["status"],
        artifact_refs=[path],
        findings=assessment["findings"],
        limitations=bundle["limitations"],
    )


def verify(service, payload):
    request = VerifyBundleRequest.model_validate(payload)
    ref = f"data/outputs/research-records/input-bundles/{request.bundle_id}/bundle.json"
    bundle = service.repo.read_json(ref)
    core = {key: value for key, value in bundle.items() if key != "bundle_id"}
    if bundle.get("bundle_id") != request.bundle_id or (
        "inputs-" + fingerprint(core)[:32] != request.bundle_id
    ):
        raise DomainError("BUNDLE_CHANGED", "Bundle content no longer matches its identifier", 4)
    issues = []
    archive_map = {}
    companion_ref = str(Path(ref).parent / "implementation-companion.json")
    if service.repo.path(companion_ref).is_file():
        companion = service.repo.read_json(companion_ref)
        core_companion = {k: v for k, v in companion.items() if k != "companion_id"}
        expected = {(item["path"], item["sha256"]) for item in bundle["implementation"]["files"]}
        if (
            companion.get("companion_id") != "implementation-" + fingerprint(core_companion)
            or companion.get("bundle_id") != request.bundle_id
            or companion.get("bundle_sha256") != digest_bytes(service.repo.path(ref).read_bytes())
            or {(item["path"], item["sha256"]) for item in companion.get("files", [])} != expected
        ):
            issues.append(
                dict(
                    code="IMPLEMENTATION_COMPANION_CHANGED",
                    kind="implementation_archive",
                    path=companion_ref,
                )
            )
        else:
            archive_map.update({item["path"]: item["archive_ref"] for item in companion["files"]})
    archive_checks = []
    for item in bundle["implementation"]["files"]:
        archive_ref = item.get("archive_ref", archive_map.get(item["path"]))
        if not archive_ref:
            continue  # Old bundles remain readable; no claim of recoverable code.
        canonical = (
            f"data/outputs/research-records/implementation-files/{item['sha256']}/source.txt"
        )
        valid = archive_ref == canonical and service.repo.path(archive_ref).is_file()
        if valid:
            valid = digest_bytes(service.repo.path(archive_ref).read_bytes()) == item["sha256"]
        archive_checks.append(dict(path=item["path"], archive_ref=archive_ref, valid=valid))
        if not valid:
            issues.append(
                dict(
                    code="IMPLEMENTATION_ARCHIVE_CHANGED",
                    kind="implementation_archive",
                    path=archive_ref,
                )
            )
        else:
            archive_map[item["path"]] = archive_ref
    for kind, files in (
        ("evidence", bundle["evidence_files"]),
        ("implementation", bundle["implementation"]["files"]),
    ):
        for file in files:
            path = service.repo.path(file["path"])
            if not path.is_file() or digest_bytes(path.read_bytes()) != file["sha256"]:
                issues.append(
                    dict(
                        code="PINNED_FILE_CHANGED",
                        kind=kind,
                        path=file["path"],
                        **(
                            {
                                "restore_from": archive_map[file["path"]],
                                "action": "Restore the archived file into an isolated checkout before verification; no code is executed automatically",
                            }
                            if kind == "implementation" and file["path"] in archive_map
                            else {}
                        ),
                    )
                )
    replay_results = []
    if not issues:
        for transformation in bundle.get("transformations", []):
            try:
                values = replay(service.repo.read_json(transformation["path"]))
                if values != transformation["replayed_values"]:
                    raise DomainError("TRANSFORM_REPLAY_MISMATCH", transformation["path"], 4)
                replay_results.append(
                    dict(
                        transformation_id=transformation["transformation_id"],
                        status="reproduced",
                        values=values,
                    )
                )
            except (DomainError, ValueError, KeyError) as exc:
                issues.append(
                    dict(
                        code=getattr(exc, "code", "TRANSFORM_REPLAY_MISMATCH"),
                        kind="transformation",
                        path=transformation["path"],
                    )
                )
    return dict(
        status="blocked" if issues else "verified",
        bundle_id=request.bundle_id,
        assessment_status=bundle["assessment"]["status"],
        profile=bundle["profile"],
        issues=issues,
        artifact_refs=[ref],
        replay_results=replay_results,
        implementation_archives=archive_checks,
        implementation_recoverable=(
            len(archive_checks) == len(bundle["implementation"]["files"])
            and all(item["valid"] for item in archive_checks)
        ),
        record_count=sum(len(key["rows"]) for key in bundle["assessment"]["audit"]["keys"]),
        limitations=bundle["limitations"],
    )
