"""Reviewed source assertions and dimensional market observations."""

import pytest

from investment_domain import DomainError
from investment_engine import Service
from test_core import admit


FACT = dict(
    fact_id="policy-announcement",
    document_kind="policy",
    subject_type="jurisdiction",
    subject_id="demo-cn",
    event_date="2024-01-02",
    assertion_type="source_assertion",
    statement="The source announces a target, not an achieved result.",
    locator="heading:Policy target",
    excerpt="Policy target 100 & growing",
)
OBS = dict(
    security_id="demo-xiaomi",
    observed_date="2024-01-02",
    metric_id="short_sale_volume",
    source_value="100",
    value_status="reported",
    unit="shares",
    basis="Source-reported morning short-sale flow, not outstanding positions",
    session="intraday",
    share_class="ordinary-hk",
    record_kind="source_reported",
    locator="line:1",
    excerpt="short_sale_volume,100",
)


def prepare(tmp_path, dataset, rows, text=None, suffix=".txt", source="demo-source"):
    service = Service(tmp_path)
    path = tmp_path / ("evidence" + suffix)
    path.write_text(text or "\n".join(row["excerpt"] for row in rows))
    doc = service.execute(
        "import", dict(path=str(path), source_id=source, published_at="2024-01-03T00:00:00Z")
    )
    batch = service.execute(
        "prepare", dict(dataset_id=dataset, document_id=doc["document_id"], records=rows)
    )
    return service, doc, batch


def approve(service, batch, **kwargs):
    return service.execute(
        "review",
        dict(
            candidate_id=batch["candidate_id"],
            reviewer="test-reviewer",
            decision="approved",
            notes="Verified source meaning, scope, units and evidence",
            **kwargs,
        ),
    )


def test_policy_html_meaning_review_and_source_query(tmp_path):
    service, doc, batch = prepare(
        tmp_path,
        "document-facts",
        [FACT],
        "<h1>Policy target</h1><p>100 &amp; growing</p><script>invented</script>",
        ".html",
    )
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "review_required"
    )
    with pytest.raises(DomainError) as exc:
        approve(service, batch)
    assert exc.value.code == "SEMANTIC_REVIEW_REQUIRED"
    approve(service, batch, statement_consistency_checked=True)
    admit(service, batch)
    result = service.execute(
        "coverage",
        dict(
            dataset_id="document-facts",
            subject_id="demo-cn",
            document_kind="policy",
            source_id="demo-source",
            start="2024-01-02",
            end="2024-01-02",
        ),
    )
    assert result["record_count"] == 1
    assert result["rows"][0]["document_refs"] == [doc["document_id"]]
    assert any("policies/jurisdiction/demo-cn/facts" in ref for ref in result["artifact_refs"])
    assert (
        service.execute("coverage", dict(dataset_id="document-facts", source_id="another"))[
            "record_count"
        ]
        == 0
    )
    assert (
        service.execute("coverage", dict(dataset_id="document-facts", document_kind="news_report"))[
            "record_count"
        ]
        == 0
    )


@pytest.mark.parametrize(
    "change",
    [
        {"assertion_type": "ai_inference"},
        {"statement": " "},
        {"effective_from": "2024-02-01", "effective_to": "2024-01-01"},
        {"excerpt": "Unstated achieved target"},
    ],
)
def test_policy_invalid_or_unsupported_claim_quarantines(tmp_path, change):
    service, _, batch = prepare(tmp_path, "document-facts", [dict(FACT, **change)], FACT["excerpt"])
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "quarantined"
    )


def test_market_source_flow_and_position_are_distinct(tmp_path):
    rows = [
        OBS,
        dict(
            OBS,
            metric_id="reported_short_position",
            session="point_in_time",
            basis="Aggregate reportable outstanding shares, threshold limited",
        ),
    ]
    service, _, batch = prepare(tmp_path, "market-observations", rows)
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "review_required"
    )
    with pytest.raises(DomainError) as exc:
        admit(service, batch)
    assert exc.value.code == "REVIEW_REQUIRED"
    approve(service, batch)
    admit(service, batch)
    result = service.execute(
        "coverage", dict(dataset_id="market-observations", metric_id="reported_short_position")
    )
    assert result["record_count"] == 1 and result["rows"][0]["source_value"] == "100"
    assert any("markets/observations/demo-xiaomi" in ref for ref in result["artifact_refs"])


@pytest.mark.parametrize(
    "change",
    [
        {"metric_id": "short_sale_ratio", "unit": "percent"},
        {"metric_id": "turnover", "unit": "shares"},
        {"source_value": "0", "value_status": "not_disclosed", "missing_reason": "not stated"},
        {"source_value": None},
        {"observed_at": "2024-01-02T12:00:00Z"},
        {"metric_id": "ai_sentiment"},
        {"source_value": "-1"},
        {"metric_id": "free_float_shares", "unit": "percent"},
    ],
)
def test_invalid_market_dimensions_and_unknowns_quarantine(tmp_path, change):
    service, _, batch = prepare(tmp_path, "market-observations", [dict(OBS, **change)])
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "quarantined"
    )


def test_unknown_value_does_not_satisfy_required_sample(tmp_path):
    row = dict(
        OBS,
        metric_id="pe_provider",
        source_value=None,
        value_status="not_disclosed",
        missing_reason="Source explicitly displays N/A",
        unit="multiple",
        excerpt="PE N/A",
    )
    service, _, batch = prepare(tmp_path, "market-observations", [row])
    approve(service, batch)
    admit(service, batch)
    result = service.execute(
        "audit_inputs",
        dict(
            requirements=[
                dict(
                    dataset_id="market-observations",
                    subject_id="demo-xiaomi",
                    start="2024-01-01",
                    end="2024-01-04",
                    metric_id="pe_provider",
                )
            ]
        ),
    )
    assert result["status"] == "partial"
    assert result["results"][0]["observed_count"] == 0
    assert result["results"][0]["unavailable_count"] == 1


def test_audit_scope_evidence_integrity_and_historical_cutoff(tmp_path):
    service, doc, batch = prepare(tmp_path, "market-observations", [OBS])
    approve(service, batch)
    admit(service, batch)
    req = dict(
        requirements=[
            dict(
                dataset_id="market-observations",
                subject_id="demo-xiaomi",
                start="2024-01-01",
                end="2024-01-04",
                metric_id="short_sale_volume",
            )
        ]
    )
    result = service.execute("audit_inputs", req)
    assert result["status"] == "complete" and result["scope"] == "declared_sample_requirements"
    assert (
        service.execute(
            "audit_inputs",
            dict(
                req,
                knowledge_mode="historical_reconstruction",
                information_cutoff="2024-01-02T23:00:00Z",
            ),
        )["status"]
        == "partial"
    )
    service.repo.path(doc["document"]["path"]).write_text("tampered")
    with pytest.raises(DomainError) as exc:
        service.execute("audit_inputs", req)
    assert exc.value.code == "EVIDENCE_CHANGED"


def test_ratio_requires_evidenced_denominator(tmp_path):
    service, doc, _ = prepare(tmp_path, "market-observations", [OBS])
    row = dict(
        OBS,
        metric_id="short_sale_ratio",
        unit="percent",
        source_value="10",
        denominator_ref=dict(
            definition="Short-sale turnover / same-session security turnover",
            period_start="2024-01-02",
            period_end="2024-01-02",
            market="HKEX",
            share_class="ordinary-hk",
            document_id=doc["document_id"],
            locator="line:1",
        ),
    )
    batch = service.execute(
        "prepare",
        dict(dataset_id="market-observations", document_id=doc["document_id"], records=[row]),
    )
    assert (
        service.execute("validate", dict(candidate_id=batch["candidate_id"]))["status"]
        == "review_required"
    )
    approve(service, batch)
    admit(service, batch)
    assert service.execute("coverage", dict(dataset_id="market-observations"))["record_count"] == 1


def test_observation_instants_normalize_to_utc_for_keys_and_date_filters(tmp_path):
    row = dict(OBS, observed_date=None, observed_at="2024-01-02T00:30:00+08:00")
    service, doc, batch = prepare(tmp_path, "market-observations", [row])
    approve(service, batch)
    admit(service, batch)
    second = service.execute(
        "prepare",
        dict(
            dataset_id="market-observations",
            document_id=doc["document_id"],
            records=[dict(row, observed_at="2024-01-01T16:30:00Z")],
        ),
    )
    approve(service, second)
    admit(service, second)
    result = service.execute(
        "coverage", dict(dataset_id="market-observations", start="2024-01-01", end="2024-01-01")
    )
    assert result["record_count"] == 1
    assert result["rows"][0]["observed_at"] == "2024-01-01T16:30:00Z"
    assert len(result["rows"][0]["batch_refs"]) == 2
    assert (
        service.execute(
            "coverage", dict(dataset_id="market-observations", start="2024-01-02", end="2024-01-02")
        )["record_count"]
        == 0
    )


@pytest.mark.parametrize(
    "published,visible",
    [("2025-01-01T00:00:00Z", False), (None, False), ("2024-01-02T00:00:00Z", True)],
)
def test_ratio_dependency_publication_obeys_historical_cutoff(tmp_path, published, visible):
    service, doc, _ = prepare(tmp_path, "market-observations", [OBS])
    path = tmp_path / "denominator.txt"
    path.write_text("Same-session total turnover and denominator scope")
    denominator = service.execute(
        "import", dict(path=str(path), source_id="demo-source", published_at=published)
    )
    row = dict(
        OBS,
        metric_id="short_sale_ratio",
        source_value="10",
        unit="percent",
        denominator_ref=dict(
            definition="Same-session turnover",
            period_start="2024-01-02",
            period_end="2024-01-02",
            market="HKEX",
            share_class="ordinary-hk",
            document_id=denominator["document_id"],
            locator="line:1",
        ),
    )
    batch = service.execute(
        "prepare",
        dict(dataset_id="market-observations", document_id=doc["document_id"], records=[row]),
    )
    approve(service, batch)
    admit(service, batch)
    result = service.execute(
        "coverage",
        dict(
            dataset_id="market-observations",
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-04T00:00:00Z",
        ),
    )
    assert result["record_count"] == int(visible)
    if not visible:
        assert result["excluded"][0]["reason"] == "dependency_unavailable_at_cutoff"
    assert service.execute("coverage", dict(dataset_id="market-observations"))["record_count"] == 1
