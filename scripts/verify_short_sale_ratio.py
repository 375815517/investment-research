"""Calculate a labelled validation ratio from matched admitted source observations.

This does not write source_reported observations or investment factors. Persist stdout
as a research record when needed; the source documents and batches remain authoritative.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from investment_engine import Service


def calculate(service: Service, security: str, source: str, day: str) -> dict:
    coverage = service.execute(
        "coverage",
        dict(
            dataset_id="market-observations",
            subject_id=security,
            source_id=source,
            start=day,
            end=day,
        ),
    )
    selected = {}
    for metric in ("short_sale_turnover", "turnover"):
        rows = [
            row
            for row in coverage["rows"]
            if row["metric_id"] == metric
            and row["session"] == "full_day"
            and row["value_status"] == "reported"
        ]
        if len(rows) != 1:
            raise ValueError(f"Expected exactly one full-day {metric}; found {len(rows)}")
        selected[metric] = rows[0]
    numerator, denominator = selected["short_sale_turnover"], selected["turnover"]
    for field in ("security_id", "observed_date", "share_class", "currency", "unit"):
        if numerator.get(field) != denominator.get(field) or not numerator.get(field):
            raise ValueError(f"Cannot establish matching {field}")
    if numerator["unit"] != "currency":
        raise ValueError("Turnover inputs must be monetary observations")
    shared_docs = set(numerator["document_refs"]) & set(denominator["document_refs"])
    if not shared_docs:
        raise ValueError("Require a shared source report for this validation calculation")
    short, total = Decimal(numerator["source_value"]), Decimal(denominator["source_value"])
    if not 0 <= short <= total or total <= 0:
        raise ValueError("Require positive total turnover and short turnover within total")
    return dict(
        status="calculated",
        record_kind="derived_validation",
        metric="short_sale_turnover_share",
        formula="short_sale_turnover / turnover",
        source_value=str(short / total),
        percent=str(short / total * Decimal(100)),
        security_id=security,
        source_id=source,
        observed_date=day,
        inputs=selected,
        artifact_refs=coverage["artifact_refs"],
        limitations=[
            "Calculated from reviewed source observations, not a directly disclosed ratio",
            "Short-selling turnover share is neither short-position share nor investor sentiment",
            "One date does not establish a historical series or long-position distribution",
            "Matching fields do not replace review of the report's counter and turnover scope",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--security", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    result = calculate(Service(args.workspace), args.security, args.source, str(args.date))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
