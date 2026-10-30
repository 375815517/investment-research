"""Closed dataset registry and deterministic business keys/partitions."""

from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pydantic import BaseModel

from investment_domain import (
    DailyPrice,
    DocumentFact,
    FinancialFact,
    MarketObservation,
    FinancialObservation,
    OperatingObservation,
    CorporateAction,
    BenchmarkPrice,
)
from investment_repository import identifier, fingerprint

MODELS: dict[str, type[BaseModel]] = {
    "daily-prices": DailyPrice,
    "financial-facts": FinancialFact,
    "document-facts": DocumentFact,
    "market-observations": MarketObservation,
    "financial-observations": FinancialObservation,
    "operating-observations": OperatingObservation,
    "corporate-actions": CorporateAction,
    "benchmark-prices": BenchmarkPrice,
}


def subject(row):
    return row.get(
        "security_id", row.get("company_id", row.get("benchmark_id", row.get("subject_id")))
    )


def canonical_row(dataset, row):
    if dataset == "corporate-actions":
        # Optional contract extensions must not turn an already published action
        # into a conflicting observation when an interrupted task is replayed.
        # Normalize the comparison view only; historical bytes remain unchanged.
        payload = {key: value for key, value in row.items() if key in CorporateAction.model_fields}
        return dict(row, **CorporateAction.model_validate(payload).model_dump(mode="json"))
    if dataset == "market-observations" and row.get("observed_at"):
        return dict(
            row,
            observed_at=datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        )
    return row


def day(row):
    row = canonical_row("market-observations", row)
    return row.get(
        "trading_date",
        row.get(
            "period_end",
            row.get(
                "event_date",
                row.get("observed_date")
                or row.get("effective_date")
                or row.get("ex_date")
                or row.get("announcement_date")
                or (row.get("observed_at") or "")[:10],
            ),
        ),
    )


def business_key(dataset, row):
    row = canonical_row(dataset, row)
    if dataset == "corporate-actions":
        return row["security_id"], row["action_id"], row["action_type"], row["share_class"]
    if dataset == "benchmark-prices":
        return (
            row["benchmark_id"],
            row["trading_date"],
            row["index_type"],
            row["unit"],
            row["currency"],
            row["basis"],
        )
    if dataset == "daily-prices":
        return row["security_id"], row["trading_date"], row["session"], row["price_basis"]
    if dataset == "financial-facts":
        return tuple(
            row[k]
            for k in ("company_id", "metric_id", "period_start", "period_end", "scope", "currency")
        )
    if dataset in {"financial-observations", "operating-observations"}:
        return tuple(
            row.get(k)
            for k in (
                "company_id",
                "metric_id",
                "metric_version",
                "period_start",
                "period_end",
                "period_type",
                "measure_kind",
                "scope",
                "unit",
                "scale",
                "currency",
                "accounting_standard",
                "adjustment_basis",
                "restatement",
            )
        ) + (fingerprint(row["dimensions"]),)
    if dataset == "document-facts":
        return row["subject_type"], row["subject_id"], row["fact_id"]
    return (
        row["security_id"],
        row.get("observed_at"),
        row.get("observed_date"),
        row["metric_id"],
        row["basis"],
        row["session"],
        row["unit"],
        row["currency"],
        row["share_class"],
        fingerprint(row.get("denominator_ref")),
    )


def partition(dataset, row):
    obj = identifier(subject(row))
    if dataset == "corporate-actions":
        return f"markets/corporate-actions/{obj}"
    if dataset == "benchmark-prices":
        return f"markets/benchmarks/{obj}/daily"
    if dataset == "daily-prices":
        return f"markets/prices/{obj}/daily"
    if dataset in {"financial-facts", "financial-observations"}:
        return f"companies/{obj}/financials"
    if dataset == "operating-observations":
        return f"companies/{obj}/operations"
    if dataset == "market-observations":
        return f"markets/observations/{obj}"
    kind = row["document_kind"]
    if kind == "policy":
        return f"policies/{row['subject_type']}/{obj}/facts"
    if kind == "industry_report" and row["subject_type"] == "industry":
        return f"industries/{obj}/facts"
    if kind in ("competition_statement", "company_statement") and row["subject_type"] == "company":
        return f"companies/{obj}/statements"
    return f"events/{row['subject_type']}/{obj}/source-statements"


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_text(text):
    parser = _Text()
    parser.feed(text)
    return " ".join(unescape(" ".join(parser.parts)).split())
