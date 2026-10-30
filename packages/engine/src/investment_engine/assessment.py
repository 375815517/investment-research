"""Evidence-grounded suitability checks shared by every application interface."""

from calendar import monthrange
from datetime import date

from investment_domain import AssessInputsRequest


def financial_period(row):
    """Calendar-aligned year/half/quarter intervals compare across leap years."""
    start = date.fromisoformat(row["period_start"])
    end = date.fromisoformat(row["period_end"])
    if start.day == 1 and end.day == monthrange(end.year, end.month)[1]:
        return "calendar_months", (end.year - start.year) * 12 + end.month - start.month + 1
    return "exact_days", (end - start).days + 1


def assess(service, payload):
    request = AssessInputsRequest.model_validate(payload)
    audit = service._audit_inputs(request.model_dump(mode="json", exclude={"purpose"}))
    findings, observations = [], []
    all_refs = set(audit["artifact_refs"])
    quantitative = request.purpose == "quantitative_comparison"

    def finding(code, dimension, message, index, refs, *, blocking=False, informational=False):
        findings.append(
            dict(
                code=code,
                dimension=dimension,
                severity="error" if blocking else "info" if informational else "warning",
                message=message,
                requirement_index=index,
                evidence_refs=sorted(set(refs)),
            )
        )

    for index, (requirement, audited) in enumerate(zip(request.requirements, audit["results"])):
        query = requirement.model_dump(mode="json", exclude={"minimum_records"}, exclude_none=True)
        query.update(knowledge_mode=request.knowledge_mode)
        if request.information_cutoff:
            query["information_cutoff"] = request.information_cutoff.isoformat()
        coverage = service._coverage(query)
        rows = coverage["rows"]
        refs = coverage["artifact_refs"]
        documents = {}
        for document_id in sorted({ref for row in rows for ref in row["document_refs"]}):
            document, metadata_path = service.repo.effective_document(
                document_id, request.knowledge_mode, request.information_cutoff
            )
            documents[document_id] = document
            all_refs.update((metadata_path, document["path"]))
        sources = sorted({row["source_id"] for row in rows})
        unknown_publication = sorted(
            document_id
            for document_id, doc in documents.items()
            if not doc.get("availability_upper_bound")
        )
        observations.append(
            dict(
                requirement_index=index,
                observed_count=audited["observed_count"],
                source_ids=sources,
                document_ids=sorted(documents),
                unknown_publication_document_ids=unknown_publication,
                excluded=coverage["excluded"],
            )
        )
        if audited["status"] != "satisfied":
            finding(
                "REQUIRED_SAMPLES_MISSING",
                "coverage",
                "Declared minimum sample count is not met after availability and cutoff filtering",
                index,
                refs,
                blocking=True,
            )
        if unknown_publication:
            finding(
                "PUBLICATION_TIME_UNKNOWN",
                "temporal",
                "Some originals lack a supported public availability bound; do not use them for historical decisions",
                index,
                [documents[key]["path"] for key in unknown_publication],
            )
        if request.knowledge_mode != "retrospective_explanation":
            finding(
                "PUBLICATION_ASSERTION_NOT_AUTHENTICATED",
                "temporal",
                "Cutoff filtering passed only for importer-asserted timestamps, not independently authenticated publication history",
                index,
                refs,
                informational=not rows,
            )
        if rows and len(sources) == 1:
            finding(
                "SINGLE_SOURCE_SCOPE",
                "reliability",
                "Only one source is represented; this is not independent corroboration",
                index,
                refs,
                informational=True,
            )
        elif rows:
            finding(
                "SOURCE_INDEPENDENCE_UNVERIFIED",
                "reliability",
                "Multiple source IDs do not establish independent origins or agreement",
                index,
                refs,
            )
        if any(row.get("price_basis") == "provider-native" for row in rows):
            finding(
                "PRICE_BASIS_UNVERIFIED",
                "comparability",
                "Provider-native prices have no verified adjustment basis; no comparable return claim",
                index,
                refs,
                blocking=quantitative,
            )
        if any(row.get("volume_unit", row.get("unit")) == "provider-native" for row in rows):
            finding(
                "NATIVE_UNIT_UNVERIFIED",
                "comparability",
                "Native volume units are not established as shares or lots",
                index,
                refs,
                blocking=quantitative,
            )
        if any(row.get("metric_id") == "pe_provider" for row in rows):
            finding(
                "PE_METHOD_NOT_STANDARDIZED",
                "comparability",
                "Source PE is not a verified common earnings window or platform-calculated TTM",
                index,
                refs,
                blocking=quantitative,
            )
        if requirement.dataset_id == "document-facts" and rows:
            finding(
                "SOURCE_ASSERTIONS_ONLY",
                "reliability",
                "Records establish what the source said, not independent truth, causality or representative sentiment",
                index,
                refs,
                informational=True,
            )
            if quantitative:
                finding(
                    "TEXT_NOT_QUANTITATIVE_SAMPLE",
                    "comparability",
                    "Text assertions cannot stand in for quantitative observations or a sentiment population",
                    index,
                    refs,
                    blocking=True,
                )
        groups: dict[str, set[tuple]] = {}
        for row in rows:
            # Compare dimensions only within the same metric; different metrics naturally differ.
            metric = row.get("metric_id", requirement.dataset_id)
            signature = tuple(
                row.get(key)
                for key in (
                    "source_unit",
                    "unit",
                    "currency",
                    "scope",
                    "session",
                    "share_class",
                    "basis",
                )
            )
            groups.setdefault(metric, set()).add(signature)
        if any(len(signatures) > 1 for signatures in groups.values()):
            finding(
                "MIXED_MEASUREMENT_BASIS",
                "comparability",
                "A metric has mixed units, scope, sessions, share classes or source bases; partition or explicitly normalize before comparison",
                index,
                refs,
                blocking=quantitative,
            )
        if requirement.dataset_id == "financial-facts":
            periods: dict[str, set[tuple]] = {}
            for row in rows:
                periods.setdefault(row["metric_id"], set()).add(financial_period(row))
            if any(len(intervals) > 1 for intervals in periods.values()):
                finding(
                    "MIXED_FINANCIAL_PERIODS",
                    "comparability",
                    "A financial metric mixes reporting interval lengths; annual, half-year and quarterly values cannot be directly compared",
                    index,
                    refs,
                    blocking=quantitative,
                )
        if quantitative and any(
            row.get("metric_id") in {"issued_shares", "free_float_shares"} for row in rows
        ):
            finding(
                "SHARE_DENOMINATOR_REVIEW_REQUIRED",
                "comparability",
                "Share observations alone do not certify a same-date same-class denominator or an unrounded float ratio",
                index,
                refs,
            )

    errors = any(item["severity"] == "error" for item in findings)
    warnings = any(item["severity"] == "warning" for item in findings)
    return dict(
        status="blocked" if errors else "limited" if warnings else "ready",
        purpose=request.purpose,
        scope="declared_sample_requirements",
        ready_means="Usable only for the declared bounded purpose and samples; not certified investment truth or complete history",
        audit=audit,
        observations=observations,
        findings=findings,
        dimensions=dict(
            integrity="verified_original_and_batch_hashes",
            coverage=dict(
                declared_samples=audit["status"],
                full_history="not_assessed",
                source_population="not_assessed",
            ),
            reliability="traceable_source_claims_not_independently_authenticated",
            temporal=(
                "cutoff_filtered_importer_assertions"
                if request.knowledge_mode != "retrospective_explanation"
                else "retrospective_only"
            ),
            comparability=(
                "limitations_found"
                if any(item["dimension"] == "comparability" for item in findings)
                else "no_structural_conflict_detected_semantic_equivalence_not_certified"
            ),
        ),
        limitations=[
            "Sample counts cannot prove trading-calendar, report-series, policy or news completeness",
            "Checks do not certify causality, forecast suitability, sentiment representativeness or cross-source independence",
            "Hashes establish byte integrity, not authenticity or semantic truth; admission review is an assertion, not reviewer identity verification",
        ],
        artifact_refs=sorted(all_refs),
        next_actions=sorted({item["code"] for item in findings if item["severity"] != "info"}),
    )
