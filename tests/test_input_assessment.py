"""Suitability is purpose-specific and cannot turn sample counts into full history."""

import pytest

from investment_domain import DomainError
from investment_engine import Service
from test_core import PRICE, admit, candidate
from test_observations import FACT, OBS, approve, prepare


def request(dataset="market-observations", subject="demo-xiaomi", **changes):
    return dict(
        requirements=[
            dict(dataset_id=dataset, subject_id=subject, start="2024-01-01", end="2024-01-04")
        ],
        **changes,
    )


def test_bounded_source_description_does_not_certify_full_history(tmp_path):
    service, _, batch = prepare(tmp_path, "document-facts", [FACT])
    approve(service, batch, statement_consistency_checked=True)
    admit(service, batch)
    before = service.repo.revision()
    result = service.execute("assess_inputs", request("document-facts", "demo-cn"))
    assert result["status"] == "ready"
    assert result["scope"] == "declared_sample_requirements"
    assert result["dimensions"]["coverage"] == dict(
        declared_samples="complete", full_history="not_assessed", source_population="not_assessed"
    )
    assert "SOURCE_ASSERTIONS_ONLY" in {item["code"] for item in result["findings"]}
    assert service.repo.revision() == before


def test_missing_requirement_remains_blocked(tmp_path):
    result = Service(tmp_path).execute("assess_inputs", request())
    assert result["status"] == "blocked"
    assert result["audit"]["status"] == "partial"
    assert result["findings"][0]["code"] == "REQUIRED_SAMPLES_MISSING"


def test_native_price_units_block_comparison_but_allow_limited_description(tmp_path):
    service, _, batch = candidate(
        tmp_path, [dict(PRICE, price_basis="provider-native", volume_unit="provider-native")]
    )
    admit(service, batch)
    payload = request("daily-prices")
    payload["requirements"][0]["price_basis"] = "provider-native"
    description = service.execute("assess_inputs", payload)
    assert description["status"] == "limited"
    compared = service.execute("assess_inputs", dict(payload, purpose="quantitative_comparison"))
    assert compared["status"] == "blocked"
    assert {item["code"] for item in compared["findings"] if item["severity"] == "error"} == {
        "PRICE_BASIS_UNVERIFIED",
        "NATIVE_UNIT_UNVERIFIED",
    }


def test_historical_purpose_requires_filtered_mode(tmp_path):
    with pytest.raises(DomainError, match="cutoff-filtered"):
        Service(tmp_path).execute("assess_inputs", request(purpose="historical_point_in_time"))
    with pytest.raises(DomainError, match="information_cutoff"):
        Service(tmp_path).execute(
            "assess_inputs",
            request(purpose="historical_point_in_time", knowledge_mode="historical_reconstruction"),
        )


def test_historical_filter_cannot_be_overridden_by_sample_success(tmp_path):
    service, _, batch = prepare(tmp_path, "market-observations", [OBS])
    approve(service, batch)
    admit(service, batch)
    result = service.execute(
        "assess_inputs",
        request(
            purpose="historical_point_in_time",
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-02T23:00:00Z",
        ),
    )
    assert result["status"] == "blocked"
    assert result["audit"]["results"][0]["observed_count"] == 0
    assert result["observations"][0]["excluded"][0]["reason"] == "not_public_at_cutoff"
    eligible = service.execute(
        "assess_inputs",
        request(
            purpose="historical_point_in_time",
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-04T23:00:00Z",
        ),
    )
    assert eligible["status"] == "limited"
    assert "PUBLICATION_ASSERTION_NOT_AUTHENTICATED" in eligible["next_actions"]


def test_unknown_publication_is_explicit_not_invented(tmp_path):
    service = Service(tmp_path)
    path = tmp_path / "unknown.txt"
    path.write_text(OBS["excerpt"])
    doc = service.execute("import", dict(path=str(path), source_id="demo-source"))
    batch = service.execute(
        "prepare",
        dict(document_id=doc["document_id"], dataset_id="market-observations", records=[OBS]),
    )
    approve(service, batch)
    admit(service, batch)
    result = service.execute("assess_inputs", request())
    assert result["status"] == "limited"
    assert result["observations"][0]["unknown_publication_document_ids"] == [doc["document_id"]]
    assert "PUBLICATION_TIME_UNKNOWN" in result["next_actions"]


def test_mixed_sessions_not_blended_and_provider_pe_not_ttm(tmp_path):
    pe = dict(
        OBS, metric_id="pe_provider", unit="multiple", source_value="12", session="point_in_time"
    )
    rows = [OBS, dict(OBS, session="full_day", source_value="300"), pe]
    service, _, batch = prepare(tmp_path, "market-observations", rows)
    approve(service, batch)
    admit(service, batch)
    result = service.execute("assess_inputs", request(purpose="quantitative_comparison"))
    assert result["status"] == "blocked"
    assert {"MIXED_MEASUREMENT_BASIS", "PE_METHOD_NOT_STANDARDIZED"} <= set(result["next_actions"])


def test_integrity_failure_never_returns_ready(tmp_path):
    service, doc, batch = prepare(tmp_path, "market-observations", [OBS])
    approve(service, batch)
    admit(service, batch)
    metadata, _ = service.repo.document(doc["document_id"])
    service.repo.path(metadata["path"]).write_text("changed")
    with pytest.raises(DomainError) as exc:
        service.execute("assess_inputs", request())
    assert exc.value.code == "EVIDENCE_CHANGED"


def test_text_cannot_be_quantitative_population(tmp_path):
    service, _, batch = prepare(tmp_path, "document-facts", [FACT])
    approve(service, batch, statement_consistency_checked=True)
    admit(service, batch)
    result = service.execute(
        "assess_inputs", request("document-facts", "demo-cn", purpose="quantitative_comparison")
    )
    assert result["status"] == "blocked"
    assert "TEXT_NOT_QUANTITATIVE_SAMPLE" in result["next_actions"]


def test_assessment_snapshot_verifies_once_per_request_and_refreshes(tmp_path, monkeypatch):
    import investment_repository
    from pathlib import Path

    service, doc, batch = prepare(tmp_path, "market-observations", [OBS])
    approve(service, batch)
    admit(service, batch)
    metadata, _ = service.repo.document(doc["document_id"])
    original = service.repo.path(metadata["path"])
    original_bytes = original.read_bytes()
    source_hashes, scans = [], []
    digest = investment_repository.digest_bytes
    rglob = Path.rglob

    def count_hash(content):
        if content == original_bytes:
            source_hashes.append(1)
        return digest(content)

    def count_scan(path, pattern, *args, **kwargs):
        if pattern == "batch.json":
            scans.append(1)
        return rglob(path, pattern, *args, **kwargs)

    monkeypatch.setattr(investment_repository, "digest_bytes", count_hash)
    monkeypatch.setattr(Path, "rglob", count_scan)
    payload = request()
    payload["requirements"] *= 32
    for expected in (1, 2):
        result = service.execute("assess_inputs", payload)
        assert result["status"] == "ready"
        assert len(source_hashes) == expected
        assert len(scans) == expected
    original.write_text("changed between requests")
    with pytest.raises(DomainError) as exc:
        service.execute("assess_inputs", payload)
    assert exc.value.code == "EVIDENCE_CHANGED"
    # Failed request also releases snapshot state, allowing the next normal operation.
    assert service.repo._snapshot.get() is None


def test_read_snapshot_is_read_only_and_return_values_are_isolated(tmp_path):
    service, doc, batch = prepare(tmp_path, "market-observations", [OBS])
    approve(service, batch)
    admit(service, batch)
    with service.repo.read_snapshot():
        metadata, _ = service.repo.document(doc["document_id"])
        metadata["published_at"] = "invented"
        assert service.repo.document(doc["document_id"])[0]["published_at"] != "invented"
        batches = service.repo.batches()
        batches[0][1]["rows"] = []
        assert len(service.repo.batches()[0][1]["rows"]) == 1
        with pytest.raises(DomainError) as exc:
            service.repo.json("data/forbidden.json", {})
        assert exc.value.code == "READ_ONLY_SNAPSHOT"
    service.repo.json(".research-local/after-snapshot.json", {})


def financial_row(start, end):
    return dict(
        company_id="demo-xiaomi",
        metric_id="revenue",
        period_start=start,
        period_end=end,
        source_value="100",
        source_unit="millions",
        currency="CNY",
        scope="consolidated",
        record_kind="reported_actual",
        locator="line:1",
        excerpt="Revenue 100",
    )


def test_financial_half_year_and_annual_are_not_comparable(tmp_path):
    rows = [financial_row("2023-01-01", "2023-12-31"), financial_row("2024-01-01", "2024-06-30")]
    service, _, batch = prepare(tmp_path, "financial-facts", rows)
    approve(service, batch)
    admit(service, batch)
    payload = request("financial-facts", purpose="quantitative_comparison")
    payload["requirements"][0].update(start="2023-01-01", end="2024-12-31")
    result = service.execute("assess_inputs", payload)
    assert result["status"] == "blocked"
    assert "MIXED_FINANCIAL_PERIODS" in result["next_actions"]


def test_leap_and_nonleap_full_years_share_period_basis(tmp_path):
    rows = [financial_row("2023-01-01", "2023-12-31"), financial_row("2024-01-01", "2024-12-31")]
    service, _, batch = prepare(tmp_path, "financial-facts", rows)
    approve(service, batch)
    admit(service, batch)
    payload = request("financial-facts", purpose="quantitative_comparison")
    payload["requirements"][0].update(start="2023-01-01", end="2024-12-31")
    result = service.execute("assess_inputs", payload)
    assert result["status"] == "ready"
    assert "MIXED_FINANCIAL_PERIODS" not in result["next_actions"]
