"""Exact-key coverage and explicit cross-requirement compatibility checks."""

from collections import defaultdict
from datetime import datetime, timezone

from investment_domain import InputRequirementProfile
from investment_repository import fingerprint

from .assessment import financial_period


def _matches(row, selectors):
    # Equality includes the complete dimensions map; a missing field is not null.
    def equal(field, expected):
        if field not in row:
            return False
        actual = row[field]
        if field == "observed_at" and actual and expected:
            return datetime.fromisoformat(actual.replace("Z", "+00:00")).astimezone(
                timezone.utc
            ) == datetime.fromisoformat(expected.replace("Z", "+00:00")).astimezone(timezone.utc)
        return actual == expected

    return all(equal(field, value) for field, value in selectors.items())


def audit(service, payload):
    profile = InputRequirementProfile.model_validate(payload)
    queries, results, refs = {}, [], set()
    for key in profile.expected_keys:
        query = dict(
            dataset_id=key.dataset_id,
            subject_id=key.subject_id,
            knowledge_mode=profile.knowledge_mode,
        )
        if key.source_id:
            query["source_id"] = key.source_id
        if profile.information_cutoff:
            query["information_cutoff"] = profile.information_cutoff.isoformat()
        if "price_basis" in key.selectors:
            query["price_basis"] = key.selectors["price_basis"]
        token = fingerprint(query)
        if token not in queries:
            queries[token] = service._coverage(query)
        coverage = queries[token]
        matches = [row for row in coverage["rows"] if _matches(row, key.selectors)]
        available = [
            row
            for row in matches
            if row.get("value_status", "reported") == "reported"
            and ("source_value" not in row or row["source_value"] is not None)
        ]
        status = (
            "ambiguous"
            if len(available) > key.max_matches
            else "satisfied"
            if available
            else "unavailable"
            if matches
            else "missing"
        )
        key_refs = sorted({ref for row in matches for ref in row.get("batch_refs", [])})
        refs.update(key_refs)
        results.append(
            dict(
                key_id=key.key_id,
                expected=key.model_dump(mode="json"),
                status=status,
                observed_count=len(available),
                unavailable_count=len(matches) - len(available),
                rows=matches,
                artifact_refs=key_refs,
                excluded=coverage["excluded"],
            )
        )
    missing = [
        item["key_id"]
        for item in results
        if item["expected"]["required"] and item["status"] != "satisfied"
    ]
    return dict(
        status="partial" if missing else "complete",
        scope="declared_exact_keys",
        profile_id=profile.profile_id,
        profile_version=profile.version,
        keys=results,
        required_count=sum(key.required for key in profile.expected_keys),
        satisfied_required_count=sum(
            item["expected"]["required"] and item["status"] == "satisfied" for item in results
        ),
        missing_key_ids=missing,
        artifact_refs=sorted(refs),
        limitations=[
            "Completeness is limited to declared exact keys, not all published reports or internet sources",
            "Unavailable or non-disclosed values never satisfy required numeric inputs",
        ],
    )


def field_value(row, field):
    if field == "scale":
        return row.get("scale", row.get("source_unit", "units"))
    if field == "unit":
        return row.get("unit", "currency" if "source_unit" in row else None)
    if field == "period_type" and "period_type" not in row and row.get("period_start"):
        return financial_period(row)
    if field == "measure_kind" and "source_unit" in row:
        return "legacy_unspecified"
    return row.get(field)


def assess(service, payload):
    profile = InputRequirementProfile.model_validate(payload)
    audited = audit(service, payload)
    findings = []
    by_key = {item["key_id"]: item for item in audited["keys"]}
    quantitative = profile.purpose == "quantitative_comparison"

    def add(code, message, key_ids, *, group_id=None, severity="error"):
        findings.append(
            dict(
                code=code,
                message=message,
                severity=severity,
                key_ids=list(key_ids),
                group_id=group_id,
            )
        )

    for item in audited["keys"]:
        if item["status"] != "satisfied":
            add(
                "EXACT_KEY_" + item["status"].upper(),
                "The exact input key is not satisfied by an unambiguous reported observation",
                [item["key_id"]],
                severity="error" if item["expected"]["required"] else "warning",
            )
        for row in item["rows"]:
            if (
                row.get("price_basis") == "provider-native"
                or row.get("volume_unit", row.get("unit")) == "provider-native"
            ):
                add(
                    "NATIVE_MEASUREMENT_UNVERIFIED",
                    "Price adjustment or volume unit is unresolved",
                    [item["key_id"]],
                    severity="error" if quantitative else "warning",
                )
            if row.get("metric_id") == "pe_provider":
                add(
                    "PROVIDER_PE_UNSTANDARDIZED",
                    "Provider PE does not certify a common earnings basis",
                    [item["key_id"]],
                    severity="error" if quantitative else "warning",
                )
            if row.get("assertion_type") == "source_assertion" and quantitative:
                add(
                    "TEXT_NOT_NUMERIC_INPUT",
                    "Source assertions are not quantitative observations",
                    [item["key_id"]],
                )

    for group in profile.comparison_groups:
        selected = [by_key[key_id] for key_id in group.key_ids]
        if any(item["status"] != "satisfied" or item["observed_count"] != 1 for item in selected):
            add(
                "COMPARISON_CARDINALITY",
                "Each comparison input must resolve to exactly one observation",
                group.key_ids,
                group_id=group.group_id,
            )
            continue
        rows = [item["rows"][0] for item in selected]
        fields = set(group.join_on) | {"currency", "scope", "dimensions", "share_class", "session"}
        # These semantic bases must never be silently reconciled by a scale conversion.
        fields |= {"basis", "accounting_standard", "adjustment_basis", "restatement"}
        if group.kind in {"ratio", "reconciliation"}:
            # Ratios/reconciliations require co-temporal raw inputs. A future
            # explicit derived alignment may support average stocks or lags;
            # omitting join fields must not silently authorize them here.
            fields |= {"period_start", "period_end", "observed_date", "observed_at", "trading_date"}
        if group.kind in {"comparison", "reconciliation"}:
            fields.add("unit")
        if group.kind == "comparison":
            fields.add("metric_id")
        incompatible = [
            field
            for field in sorted(fields)
            if len({fingerprint(field_value(row, field)) for row in rows}) > 1
        ]
        if incompatible:
            add(
                "COMPARISON_DIMENSIONS",
                "Incompatible fields: " + ", ".join(incompatible),
                group.key_ids,
                group_id=group.group_id,
            )
        scales = {field_value(row, "scale") for row in rows}
        if len(scales) > 1 and not group.normalize_scales:
            add(
                "COMPARISON_SCALE",
                "Explicit scale normalization is required before comparison",
                group.key_ids,
                group_id=group.group_id,
            )
        elif len(scales) > 1:
            add(
                "SCALE_NORMALIZATION_REQUIRED",
                "Declared normalization must be executed and retained as derived lineage",
                group.key_ids,
                group_id=group.group_id,
                severity="warning",
            )

    unknown = defaultdict(set)
    seen_documents = {}
    for item in audited["keys"]:
        for row in item["rows"]:
            for doc_id in row.get("document_refs", []):
                if doc_id not in seen_documents:
                    if hasattr(service.repo, "effective_document"):
                        doc, _ = service.repo.effective_document(
                            doc_id,
                            profile.knowledge_mode,
                            profile.information_cutoff,
                            revision_id=row.get("metadata_revision_ids", {}).get(doc_id),
                        )
                    else:
                        doc, _ = service.repo.document(doc_id)
                    seen_documents[doc_id] = doc
                doc = seen_documents[doc_id]
                if not (doc.get("availability_upper_bound") or doc.get("published_at")):
                    unknown[doc_id].add(item["key_id"])
    for doc_id, key_ids in unknown.items():
        add(
            "PUBLICATION_AVAILABILITY_UNKNOWN",
            "No verified public availability bound: " + doc_id,
            sorted(key_ids),
            severity="warning",
        )
    if profile.knowledge_mode != "retrospective_explanation" and any(
        item["rows"] for item in audited["keys"]
    ):
        add(
            "AVAILABILITY_EVIDENCE_SCOPE",
            "Historical filtering relies on reviewed source evidence, not independent certification",
            [],
            severity="warning",
        )
    status = (
        "blocked"
        if any(f["severity"] == "error" for f in findings)
        else ("limited" if any(f["severity"] == "warning" for f in findings) else "ready")
    )
    return dict(
        status=status,
        scope="declared_exact_keys_and_comparison_groups",
        purpose=profile.purpose,
        audit=audited,
        findings=findings,
        artifact_refs=audited["artifact_refs"],
        limitations=[
            "Ready applies only to declared inputs and groups; it is not factor effectiveness or complete history certification",
            "No comparison is inferred between independent keys; downstream joins must declare comparison groups",
            "Hash integrity and review attestations do not certify source truth",
        ],
        next_actions=sorted({finding["code"] for finding in findings}),
    )
