"""Exact input keys, comparison groups and immutable replay boundaries."""

from pathlib import Path
from copy import deepcopy
import shutil

import pytest

from investment_domain import DomainError
from investment_engine import Service
from investment_engine import bundles, profiles, transforms
from test_core import admit
from test_observations import prepare, approve

FINANCIAL = dict(
    company_id="demo-company",
    metric_id="revenue",
    period_start="2024-01-01",
    period_end="2024-12-31",
    source_value="10",
    source_unit="millions",
    currency="CNY",
    scope="consolidated",
    record_kind="reported_actual",
    locator="line:1",
    excerpt="Revenue 10 million",
)


def insert(root, row=None, source="source-a"):
    row = row or FINANCIAL
    service, doc, batch = prepare(root, "financial-facts", [row], source=source)
    approve(service, batch)
    admit(service, batch)
    return service, doc


def key(key_id="revenue", source="source-a", **selectors):
    return dict(
        key_id=key_id,
        dataset_id="financial-facts",
        subject_id="demo-company",
        source_id=source,
        selectors=dict(
            metric_id="revenue",
            period_start="2024-01-01",
            period_end="2024-12-31",
            scope="consolidated",
            currency="CNY",
            **selectors,
        ),
    )


def profile(keys=None, groups=None, **changes):
    return dict(
        profile_id="test-inputs",
        expected_keys=keys or [key()],
        comparison_groups=groups or [],
        **changes,
    )


def test_duplicate_period_cannot_satisfy_another_expected_period(tmp_path):
    service, _ = insert(tmp_path)
    insert(tmp_path)  # source re-acquisition is idempotent, not a second year.
    missing = key("next-year")
    missing["selectors"].update(period_start="2025-01-01", period_end="2025-12-31")
    result = profiles.audit(service, profile([key(), missing]))
    assert result["status"] == "partial"
    assert result["satisfied_required_count"] == 1
    assert result["missing_key_ids"] == ["next-year"]


def test_wrong_currency_cannot_fill_expected_key(tmp_path):
    service, _ = insert(tmp_path)
    expected = key()
    expected["selectors"]["currency"] = "HKD"
    assert profiles.audit(service, profile([expected]))["missing_key_ids"] == ["revenue"]


def test_multiple_sources_do_not_silently_choose_a_value(tmp_path):
    service, _ = insert(tmp_path)
    insert(tmp_path, dict(FINANCIAL, excerpt="Second report revenue 10 million"), "source-b")
    expected = key(source=None)
    result = profiles.audit(service, profile([expected]))
    assert result["keys"][0]["status"] == "ambiguous"
    assert result["status"] == "partial"


def mixed_sources(root):
    service, _ = insert(root)
    insert(
        root,
        dict(
            FINANCIAL,
            source_value="10000",
            source_unit="thousands",
            excerpt="Revenue 10000 thousand",
        ),
        "source-b",
    )
    keys = [key("left"), key("right", "source-b")]
    return service, profile(
        keys,
        [dict(group_id="same-revenue", key_ids=["left", "right"])],
        purpose="quantitative_comparison",
    )


def test_split_requirements_still_block_mixed_scale(tmp_path):
    service, request = mixed_sources(tmp_path)
    result = profiles.assess(service, request)
    assert result["status"] == "blocked"
    assert "COMPARISON_SCALE" in result["next_actions"]


def test_normalization_retains_source_values_and_derivation(tmp_path):
    service, request = mixed_sources(tmp_path)
    before = service.repo.revision()
    result = transforms.normalize(service, dict(profile=request, target_scale="units"))
    assert result["status"] == "normalized"
    assert {row["normalized_value"] for row in result["records"]} == {"10000000"}
    assert {row["input"]["source_value"] for row in result["records"]} == {"10", "10000"}
    assert all(row["record_kind"] == "derived_normalization" for row in result["records"])
    assert service.repo.revision() == before
    repeated = transforms.normalize(service, dict(profile=request, target_scale="units"))
    assert repeated["transformation_id"] == result["transformation_id"]


def test_scale_permission_does_not_hide_currency_conflict(tmp_path):
    service, _ = insert(tmp_path)
    insert(tmp_path, dict(FINANCIAL, currency="HKD", excerpt="Revenue HKD 10 million"), "source-b")
    right = key("right", "source-b")
    right["selectors"]["currency"] = "HKD"
    request = profile(
        [key("left"), right],
        [dict(group_id="mixed", key_ids=["left", "right"], normalize_scales=True)],
        purpose="quantitative_comparison",
    )
    result = transforms.normalize(service, dict(profile=request))
    assert result["status"] == "blocked"
    assert "COMPARISON_DIMENSIONS" in result["assessment"]["next_actions"]


def test_half_year_and_full_year_cannot_be_compared_by_default(tmp_path):
    service, _ = insert(tmp_path)
    insert(
        tmp_path,
        dict(FINANCIAL, period_end="2024-06-30", excerpt="Half year revenue 10 million"),
        "source-b",
    )
    half = key("half", "source-b")
    half["selectors"]["period_end"] = "2024-06-30"
    request = profile(
        [key("year"), half],
        [dict(group_id="periods", key_ids=["year", "half"])],
        purpose="quantitative_comparison",
    )
    assert "COMPARISON_DIMENSIONS" in profiles.assess(service, request)["next_actions"]


def test_bundle_reclone_and_new_data_do_not_replace_frozen_inputs(tmp_path):
    original, clone = tmp_path / "original", tmp_path / "clone"
    original.mkdir()
    service, _ = insert(original)
    result = bundles.freeze(service, dict(profile=profile()))
    before = service.repo.read_json(result["artifact_refs"][0])
    insert(
        original,
        dict(
            FINANCIAL,
            period_start="2025-01-01",
            period_end="2025-12-31",
            excerpt="2025 revenue 10 million",
        ),
    )
    shutil.copytree(original, clone, ignore=shutil.ignore_patterns(".research-local"))
    checked = bundles.verify(Service(clone), dict(bundle_id=result["bundle_id"]))
    assert checked["status"] == "verified"
    assert checked["record_count"] == 1
    assert service.repo.read_json(result["artifact_refs"][0]) == before


def test_bundle_detects_evidence_and_bundle_changes(tmp_path):
    service, doc = insert(tmp_path)
    result = bundles.freeze(service, dict(profile=profile()))
    metadata, _ = service.repo.document(doc["document_id"])
    service.repo.path(metadata["path"]).write_text("changed")
    checked = bundles.verify(service, dict(bundle_id=result["bundle_id"]))
    assert checked["status"] == "blocked"
    assert checked["issues"][0]["code"] == "PINNED_FILE_CHANGED"
    path = service.repo.path(result["artifact_refs"][0])
    original = service.repo.read_json(result["artifact_refs"][0])
    changed = deepcopy(original)
    changed["assessment"]["status"] = "invented-ready"
    import json

    path.write_text(json.dumps(changed))
    with pytest.raises(DomainError) as exc:
        bundles.verify(service, dict(bundle_id=result["bundle_id"]))
    assert exc.value.code == "BUNDLE_CHANGED"


def test_bundle_detects_implementation_change(tmp_path):
    service, _ = insert(tmp_path)
    code = tmp_path / "packages/example/transform.py"
    code.parent.mkdir(parents=True)
    code.write_text("VERSION = 1\n")
    frozen = bundles.freeze(service, dict(profile=profile()))
    code.write_text("VERSION = 2\n")
    result = bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))
    assert result["status"] == "blocked"
    assert any(issue["kind"] == "implementation" for issue in result["issues"])


def test_bundle_pins_selected_metadata_and_its_evidence(tmp_path):
    from investment_engine.temporal import revise_metadata

    service, source = insert(tmp_path)
    evidence, _, _ = service.repo.import_bytes(
        b"Published 2024-01-02; corrected 2024-01-03", "index", ".txt", None, "Index"
    )
    payload = dict(
        document_id=source["document_id"],
        evidence_document_id=evidence["document_id"],
        publication=dict(precision="date", date="2024-01-02", timezone="Asia/Hong_Kong"),
        locator="text:date",
        excerpt="Published 2024-01-02",
        reviewer="test",
    )
    revision = revise_metadata(service, payload)
    frozen = bundles.freeze(service, dict(profile=profile()))
    stored = service.repo.read_json(frozen["artifact_refs"][0])
    assert (
        stored["documents"][source["document_id"]]["metadata_revision"] == revision["revision_id"]
    )
    assert evidence["path"] in {file["path"] for file in stored["evidence_files"]}
    # A later reviewed assertion does not replace the frozen metadata selection.
    revised = dict(
        payload,
        expected_revision_id=revision["revision_id"],
        publication=dict(precision="date", date="2024-01-03", timezone="Asia/Hong_Kong"),
        excerpt="corrected 2024-01-03",
    )
    revise_metadata(service, revised)
    assert bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))["status"] == "verified"
    service.repo.path(evidence["path"]).write_text("changed index")
    assert bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))["status"] == "blocked"


def test_frozen_transformation_replays_in_clean_clone(tmp_path):
    original, clone = tmp_path / "original", tmp_path / "clone"
    original.mkdir()
    service, request = mixed_sources(original)
    normalized = transforms.normalize(service, dict(profile=request, target_scale="units"))
    request["comparison_groups"][0]["normalize_scales"] = True
    frozen = bundles.freeze(
        service, dict(profile=request, transformation_ids=[normalized["transformation_id"]])
    )
    shutil.copytree(original, clone, ignore=shutil.ignore_patterns(".research-local"))
    result = bundles.verify(Service(clone), dict(bundle_id=frozen["bundle_id"]))
    assert result["status"] == "verified"
    assert result["replay_results"][0]["status"] == "reproduced"
    assert {v["normalized_value"] for v in result["replay_results"][0]["values"]} == {"10000000"}


def test_bundle_rejects_transformation_of_unselected_records(tmp_path):
    service, request = mixed_sources(tmp_path)
    normalized = transforms.normalize(service, dict(profile=request))
    with pytest.raises(DomainError) as exc:
        bundles.freeze(
            service, dict(profile=profile(), transformation_ids=[normalized["transformation_id"]])
        )
    assert exc.value.code == "TRANSFORM_INPUT_NOT_IN_BUNDLE"


def test_same_period_different_basis_is_still_incompatible():
    class FakeService:
        def _coverage(self, request):
            return dict(
                rows=[
                    dict(
                        FINANCIAL,
                        source_id=request.get("source_id"),
                        basis="ifrs" if request.get("source_id") == "source-a" else "adjusted",
                        document_refs=[],
                        batch_refs=[],
                    )
                ],
                artifact_refs=[],
                excluded=[],
            )

    request = profile(
        [key("left"), key("right", "source-b")],
        [dict(group_id="basis", key_ids=["left", "right"])],
        purpose="quantitative_comparison",
    )
    result = profiles.assess(FakeService(), request)
    assert result["status"] == "blocked"
    assert "basis" in result["findings"][0]["message"]


def test_ratio_requires_same_period_even_when_join_fields_omit_dates(tmp_path):
    service, _ = insert(tmp_path)
    insert(
        tmp_path,
        dict(
            FINANCIAL,
            metric_id="gross-profit",
            period_start="2025-01-01",
            period_end="2025-12-31",
            excerpt="2025 gross profit 10 million",
        ),
        "source-b",
    )
    other = key("profit", "source-b")
    other["selectors"].update(
        metric_id="gross-profit", period_start="2025-01-01", period_end="2025-12-31"
    )
    request = profile(
        [key("revenue"), other],
        [
            dict(
                group_id="margin", kind="ratio", key_ids=["revenue", "profit"], join_on=["currency"]
            )
        ],
        purpose="quantitative_comparison",
    )
    result = profiles.assess(service, request)
    assert result["status"] == "blocked"
    assert any("period_end" in finding["message"] for finding in result["findings"])


def test_comparison_can_explicitly_compare_distinct_annual_periods(tmp_path):
    service, _ = insert(tmp_path)
    insert(
        tmp_path,
        dict(
            FINANCIAL,
            period_start="2025-01-01",
            period_end="2025-12-31",
            excerpt="2025 revenue 10 million",
        ),
        "source-b",
    )
    other = key("next", "source-b")
    other["selectors"].update(period_start="2025-01-01", period_end="2025-12-31")
    request = profile(
        [key("prior"), other],
        [dict(group_id="growth-inputs", key_ids=["prior", "next"])],
        purpose="quantitative_comparison",
    )
    assert profiles.assess(service, request)["status"] == "ready"


def test_bundle_pins_supporting_metadata_original_and_detects_tampering(tmp_path):
    from investment_engine.temporal import revise_metadata

    service, source = insert(tmp_path)
    evidence, _, _ = service.repo.import_bytes(
        b"Published 2024-01-02", "index", ".txt", None, "Index"
    )
    counterpart, _, _ = service.repo.import_bytes(
        b"Equivalent report attachment", "exchange", ".txt", None, "Counterpart"
    )
    revise_metadata(
        service,
        dict(
            document_id=source["document_id"],
            evidence_document_id=evidence["document_id"],
            supporting_document_ids=[counterpart["document_id"]],
            publication=dict(precision="date", date="2024-01-02", timezone="Asia/Hong_Kong"),
            locator="text:date",
            excerpt="Published 2024-01-02",
            reviewer="test",
        ),
    )
    frozen = bundles.freeze(service, dict(profile=profile()))
    stored = service.repo.read_json(frozen["artifact_refs"][0])
    files = {item["path"] for item in stored["evidence_files"]}
    assert counterpart["path"] in files
    assert str(Path(counterpart["path"]).parent / "document.json") in files
    assert bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))["status"] == "verified"
    service.repo.path(counterpart["path"]).write_bytes(b"Altered counterpart")
    result = bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))
    assert result["status"] == "blocked"
    assert any(item["path"] == counterpart["path"] for item in result["issues"])


def v2_bundle_fixture(tmp_path):
    from test_contracts_v2 import observation, exact_key

    root = Path(__file__).parents[1]
    for ref in ["research/metrics/revenue/v1.json", "research/units/scales.json"]:
        target = tmp_path / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / ref, target)
    row = observation(locator="line:1", excerpt="Revenue 1000")
    service, _, batch = prepare(tmp_path, "financial-observations", [row], source="issuer")
    approve(service, batch, statement_consistency_checked=True)
    admit(service, batch)
    return service, profile([exact_key()])


@pytest.mark.parametrize("ref", ["research/metrics/revenue/v1.json", "research/units/scales.json"])
def test_bundle_automatically_pins_v2_metric_and_scales(tmp_path, ref):
    service, request = v2_bundle_fixture(tmp_path)
    unrelated = service.repo.path("research/metrics/unrelated/v1.json")
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("{}")
    frozen = bundles.freeze(service, dict(profile=request))
    stored = service.repo.read_json(frozen["artifact_refs"][0])
    files = {item["path"] for item in stored["evidence_files"]}
    assert ref in files
    assert "research/metrics/unrelated/v1.json" not in files
    service.repo.path(ref).write_text("{}")
    assert bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))["status"] == "blocked"


def test_bundle_missing_v2_dictionary_is_not_legacy_compatibility(tmp_path):
    service, request = v2_bundle_fixture(tmp_path)
    service.repo.path("research/metrics/revenue/v1.json").unlink()
    with pytest.raises(DomainError) as exc:
        bundles.freeze(service, dict(profile=request))
    assert exc.value.code == "BUNDLE_DEFINITION_MISSING"


def test_bundle_declared_calendar_is_pinned_and_missing_refs_fail(tmp_path):
    service, _ = insert(tmp_path)
    ref = "research/calendars/xhkg/2025.json"
    calendar = service.repo.path(ref)
    calendar.parent.mkdir(parents=True)
    calendar.write_text('{"sessions":["2025-01-02"]}')
    frozen = bundles.freeze(service, dict(profile=profile(definition_refs=[ref])))
    calendar.write_text('{"sessions":[]}')
    assert bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))["status"] == "blocked"
    calendar.unlink()
    with pytest.raises(DomainError) as exc:
        bundles.freeze(service, dict(profile=profile(definition_refs=[ref])))
    assert exc.value.code == "BUNDLE_INPUT_MISSING"


@pytest.mark.parametrize(
    "ref",
    [
        "../secret",
        "/research/file",
        "research/../private",
        "research//file",
        "research/./file",
        "research\\file",
        "data/outputs/file",
        "research/file\n",
    ],
)
def test_profile_definition_refs_reject_unsafe_or_out_of_scope_paths(ref):
    from pydantic import ValidationError
    from investment_domain import InputRequirementProfile

    with pytest.raises(ValidationError):
        InputRequirementProfile.model_validate(profile(definition_refs=[ref]))


def test_freeze_archives_code_bytes_and_offers_restore_without_execution(tmp_path):
    service, _ = insert(tmp_path)
    ref = "packages/example/transform.py"
    code = service.repo.path(ref)
    code.parent.mkdir(parents=True)
    code.write_text("raise RuntimeError('must never execute archived code')\n")
    frozen = bundles.freeze(service, dict(profile=profile()))
    stored = service.repo.read_json(frozen["artifact_refs"][0])
    item = next(item for item in stored["implementation"]["files"] if item["path"] == ref)
    assert service.repo.path(item["archive_ref"]).read_bytes() == code.read_bytes()
    code.write_text("# changed working tree\n")
    checked = bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))
    assert checked["status"] == "blocked"
    assert checked["implementation_recoverable"] is True
    assert checked["issues"][0]["restore_from"] == item["archive_ref"]
    code.write_bytes(service.repo.path(item["archive_ref"]).read_bytes())
    assert bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))["status"] == "verified"
    service.repo.path(item["archive_ref"]).write_text("corrupted archive")
    checked = bundles.verify(service, dict(bundle_id=frozen["bundle_id"]))
    assert checked["status"] == "blocked"
    assert checked["implementation_recoverable"] is False
    assert any(issue["code"] == "IMPLEMENTATION_ARCHIVE_CHANGED" for issue in checked["issues"])


def test_code_archive_deduplicates_equal_bytes(tmp_path):
    service, _ = insert(tmp_path)
    for name in ["a", "b"]:
        path = service.repo.path(f"packages/example/{name}.py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VERSION=1\n")
    frozen = bundles.freeze(service, dict(profile=profile()))
    manifest = service.repo.read_json(frozen["artifact_refs"][0])["implementation"]["files"]
    assert len(manifest) == 2
    assert manifest[0]["archive_ref"] == manifest[1]["archive_ref"]


def test_legacy_bundle_companion_restores_archives_without_rewriting_bundle(tmp_path):
    from investment_repository import digest_bytes, fingerprint

    service, _ = insert(tmp_path)
    code = service.repo.path("packages/example/module.py")
    code.parent.mkdir(parents=True)
    code.write_text("VALUE=1\n")
    frozen = bundles.freeze(service, dict(profile=profile()))
    original = service.repo.read_json(frozen["artifact_refs"][0])
    core = {k: v for k, v in original.items() if k != "bundle_id"}
    archived_files = deepcopy(core["implementation"]["files"])
    for item in core["implementation"]["files"]:
        item.pop("archive_ref")
    legacy_id = "inputs-" + fingerprint(core)[:32]
    ref = f"data/outputs/research-records/input-bundles/{legacy_id}/bundle.json"
    service.repo.json(ref, dict(bundle_id=legacy_id, **core))
    before = service.repo.path(ref).read_bytes()
    body = dict(bundle_id=legacy_id, bundle_sha256=digest_bytes(before), files=archived_files)
    companion_ref = str(Path(ref).parent / "implementation-companion.json")
    service.repo.json(
        companion_ref, dict(companion_id="implementation-" + fingerprint(body), **body)
    )
    code.write_text("VALUE=2\n")
    checked = bundles.verify(service, dict(bundle_id=legacy_id))
    assert checked["status"] == "blocked"
    assert checked["implementation_recoverable"] is True
    assert checked["issues"][0]["restore_from"] == archived_files[0]["archive_ref"]
    assert service.repo.path(ref).read_bytes() == before
    service.repo.path(companion_ref).write_text("{}")
    checked = bundles.verify(service, dict(bundle_id=legacy_id))
    assert any(issue["code"] == "IMPLEMENTATION_COMPANION_CHANGED" for issue in checked["issues"])
