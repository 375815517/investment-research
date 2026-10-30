"""Extraction must not silently choose ambiguous rows or interpret missing data as zero."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "report_candidates", Path(__file__).parents[1] / "scripts/extract_report_candidates.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("text", ["—", "–", "-"])
def test_missing_source_number_never_becomes_zero(text):
    with pytest.raises(ValueError, match="not automatically zero"):
        module.number(text)


def test_signed_parenthesized_amount_preserves_precision():
    assert module.number("(1,234.50)") == "-1234.50"


def test_duplicate_source_rows_require_review(monkeypatch, tmp_path):
    class Repository:
        def __init__(self, root):
            pass

        def document(self, identifier):
            return {"path": "report.pdf"}, {}

        def path(self, path):
            return tmp_path / path

    monkeypatch.setattr(module, "Repository", Repository)
    monkeypatch.setattr(
        module,
        "PdfReader",
        lambda path: SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda **kwargs: "Revenue 100 90\nRevenue 110 95")]
        ),
    )
    with pytest.raises(ValueError, match="expected one row, got 2"):
        module.extract(
            tmp_path,
            {
                "document_id": "doc-test",
                "selections": [{"page": 1, "pattern": r"^Revenue[^\n]+", "metric_id": "revenue"}],
            },
        )
