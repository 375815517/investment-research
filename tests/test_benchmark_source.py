import json

from investment_connectors import ConnectorService
from investment_engine import Service


def test_index_parser_preserves_points_and_exact_original_row(tmp_path):
    provider = tmp_path / "research/sources/index"
    provider.mkdir(parents=True)
    (provider / "source.yaml").write_text("""source_id: index
url: https://example.org/chart
connector_id: tencent-benchmark-v1
dataset_id: benchmark-prices
source_symbol: hkHSI
benchmark_id: hang-seng-index
archive_permissions: research-only
usage_basis: Synthetic offline test fixture
""")
    original = tmp_path / "index.json"
    original.write_text(
        json.dumps(
            {
                "code": 0,
                "data": {
                    "hkHSI": {
                        "day": [
                            ["2024-01-02", "17000", "17100", "17200", "16900", "100"],
                        ]
                    }
                },
            },
            separators=(",", ":"),
        )
    )
    service = Service(tmp_path, ConnectorService(tmp_path))
    doc = service.execute("import", dict(path=str(original), source_id="index"))
    prepared = service.execute(
        "prepare", dict(document_id=doc["document_id"], dataset_id="benchmark-prices")
    )
    result = service.execute("validate", dict(candidate_id=prepared["candidate_id"]))
    assert result["status"] == "review_required"
    row = service._candidate(prepared["candidate_id"])["records"][0]
    assert row["close"] == "17100"
    assert row["currency"] is None
    assert row["unit"] == "points"
    assert row["excerpt"] in original.read_text()
    assert row["index_type"] == "price_index"


def test_v2_basis_wording_does_not_create_another_business_identity():
    from investment_engine.datasets import business_key

    row = dict(
        company_id="sample",
        metric_id="revenue",
        metric_version="1",
        period_start="2024-01-01",
        period_end="2024-12-31",
        period_type="annual",
        measure_kind="flow",
        scope="consolidated",
        unit="currency",
        scale="millions",
        currency="CNY",
        accounting_standard="IFRS",
        adjustment_basis="reported",
        restatement="original",
        dimensions={},
        basis="source text",
    )
    assert business_key("financial-observations", row) == business_key(
        "financial-observations", dict(row, basis="corrected explanation")
    )
