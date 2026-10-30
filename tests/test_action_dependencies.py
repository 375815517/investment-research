"""An actual payment must retain a resolvable source declaration."""

from types import SimpleNamespace

import pytest

from investment_engine.action_dependencies import resolve


def test_legacy_payment_defaults_are_compatible_without_hiding_changed_dates():
    from copy import deepcopy

    from investment_domain import CorporateAction
    from investment_engine.datasets import canonical_row

    legacy = dict(
        security_id="sample-hk",
        action_id="distribution-paid",
        action_type="spinoff",
        action_status="effected",
        updates_action_id="distribution-declared",
        announcement_date="2023-03-24",
        payment_date="2023-03-24",
        share_class="ordinary",
        basis="Certificates dispatched; investor receipt date is not established",
        locator="pdf:page:1",
        excerpt="Certificates dispatched on 24 March 2023",
    )
    original = deepcopy(legacy)
    current = CorporateAction.model_validate(legacy).model_dump(mode="json")
    assert canonical_row("corporate-actions", legacy) == canonical_row("corporate-actions", current)
    assert legacy == original
    assert canonical_row("corporate-actions", legacy) != canonical_row(
        "corporate-actions", dict(current, payment_date="2023-03-25")
    )
    assert canonical_row("corporate-actions", dict(legacy, batch_refs=["old/batch.json"]))[
        "batch_refs"
    ] == ["old/batch.json"]


def test_confirmation_references_same_security_and_type_without_guessing_terms():
    declaration = dict(
        action_id="declared",
        security_id="tencent-hk",
        action_type="spinoff",
        announcement_date="2021-12-23",
        ratio="0.1",
    )
    batch = dict(
        dataset_id="corporate-actions", rows=[declaration], documents=["source-declaration"]
    )
    repo = SimpleNamespace(batches=lambda: [("declaration/batch.json", batch)])
    confirmation = dict(
        action_id="paid",
        security_id="tencent-hk",
        action_type="spinoff",
        announcement_date="2022-03-25",
        updates_action_id="declared",
    )
    assert resolve(repo, confirmation) == (["declaration/batch.json"], ["source-declaration"])
    assert "ratio" not in confirmation
    for override in [
        dict(security_id="xiaomi-hk"),
        dict(action_type="cash_dividend"),
        dict(announcement_date="2020-01-01"),
    ]:
        with pytest.raises(ValueError):
            resolve(repo, dict(confirmation, **override))
    repo.batches = lambda: [("a", batch), ("b", batch)]
    with pytest.raises(ValueError, match="one registered"):
        resolve(repo, confirmation)


def test_freeze_pins_transitive_action_declaration_files(tmp_path):
    import json
    from investment_engine.bundles import _pinned_files

    objects = {
        "payment/batch.json": {
            "files": [{"path": "payment/rows.json"}],
            "documents": ["paid"],
            "dependency_batches": ["declared/batch.json"],
        },
        "declared/batch.json": {
            "files": [{"path": "declared/rows.json"}],
            "documents": ["declaration"],
        },
    }
    for ref, body in objects.items():
        p = tmp_path / ref
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(body))
        (p.parent / "rows.json").write_text("[]")
    for doc in ["paid", "declaration"]:
        (tmp_path / f"{doc}.pdf").write_text(doc)
        (tmp_path / f"{doc}.json").write_text("{}")
    repo = SimpleNamespace(
        read_json=lambda ref: objects[ref],
        path=lambda ref: tmp_path / ref,
        document=lambda doc: ({"path": f"{doc}.pdf", "sha256": doc}, f"{doc}.json"),
    )
    assessment = {
        "artifact_refs": ["payment/batch.json"],
        "audit": {
            "keys": [
                {
                    "expected": {"dataset_id": "corporate-actions"},
                    "rows": [{"document_refs": ["paid"]}],
                }
            ]
        },
    }
    files, documents = _pinned_files(SimpleNamespace(repo=repo), assessment)
    assert {"declared/batch.json", "declared/rows.json", "declaration.pdf", "declaration.json"} <= {
        item["path"] for item in files
    }
    assert set(documents) == {"paid", "declaration"}


def test_action_update_resolves_active_revision_only():
    row = dict(
        action_id="declaration",
        security_id="demo",
        action_type="cash_dividend",
        announcement_date="2024-01-01",
    )
    old = dict(batch_id="old", dataset_id="corporate-actions", rows=[row], documents=["old-source"])
    new = dict(old, batch_id="new", supersedes=["old"], documents=["new-source"])
    repo = SimpleNamespace(batches=lambda: [("old/batch.json", old), ("new/batch.json", new)])
    assert resolve(repo, dict(row, action_id="confirmed", updates_action_id="declaration")) == (
        ["new/batch.json"],
        ["new-source"],
    )
