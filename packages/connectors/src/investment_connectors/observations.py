"""Source-labelled market observations, never inferred long/short positioning."""

from __future__ import annotations
import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def extract_html_text(data: bytes | str) -> str:
    parser = VisibleText()
    parser.feed(data.decode("utf-8-sig") if isinstance(data, bytes) else data)
    return " ".join(" ".join(parser.parts).split())


def _number(value: str) -> str:
    result = Decimal(value.replace(",", ""))
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid nonnegative observation")
    return str(result)


def _record(
    security_id: str,
    day: str,
    metric: str,
    value: str,
    unit: str,
    basis: str,
    session: str,
    locator: str,
    excerpt: str,
) -> dict[str, Any]:
    return dict(
        security_id=security_id,
        observed_date=day,
        metric_id=metric,
        source_value=_number(value),
        value_status="reported",
        unit=unit,
        currency="HKD" if unit == "currency" else None,
        basis=basis,
        session=session,
        share_class="Specified source stock-code counter; no cross-class aggregation inferred",
        record_kind="source_reported",
        locator=locator,
        excerpt=excerpt,
    )


def parse_sfc_short_positions(
    data: bytes, symbol: str, security_id: str, *, observed_at: str = ""
) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    columns = [
        "Date",
        "Stock Code",
        "Stock Name",
        "Aggregated Reportable Short Positions (Shares)",
        "Aggregated Reportable Short Positions (HK$)",
    ]
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != columns:
        raise ValueError("SFC CSV headers changed")
    matches = [
        (i, row) for i, row in enumerate(reader, 2) if row["Stock Code"].zfill(5) == symbol.zfill(5)
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one specified-security SFC observation")
    line, row = matches[0]
    day = datetime.strptime(row["Date"], "%d/%m/%Y").date().isoformat()
    excerpt = text.splitlines()[line - 1]
    basis = "SFC aggregated reportable short positions; reporting-threshold population, not total market short interest or net long/short balance."
    return [
        _record(
            security_id,
            day,
            metric,
            row[column],
            unit,
            basis,
            "reporting_period",
            f"text:line:{line}",
            excerpt,
        )
        for metric, column, unit in [
            ("reported_short_position", columns[3], "shares"),
            ("reported_short_position_value", columns[4], "currency"),
        ]
    ]


def parse_hkex_short_turnover(
    data: bytes, symbol: str, security_id: str, *, observed_at: str = ""
) -> list[dict[str, Any]]:
    # This source uses ASCII preformatted rows; visible text is also retained for evidence checks.
    text = data.decode("utf-8-sig")
    visible = extract_html_text(text)
    match = re.search(r"TRADING DATE\s*:\s*(\d{1,2} [A-Z]{3} \d{4})", visible)
    if not match or "SHORTSELL REPORT" not in visible:
        raise ValueError("Missing HKEX report heading/date")
    day = datetime.strptime(match[1], "%d %b %Y").date().isoformat()
    if "up to day close today" in visible:
        session = "full_day"
    elif "up to morning close today" in visible:
        session = "intraday"
    else:
        raise ValueError("Unknown HKEX session")
    rows = re.findall(r"^\s*([%]?)(\d+)\s+(.+?)\s+([\d,]+)\s+([\d,]+)\s*$", text, re.M)
    matches = [row for row in rows if row[1].zfill(5) == symbol.zfill(5)]
    if len(matches) != 1 or matches[0][0]:
        raise ValueError("Missing/duplicate HKD stock row or non-HKD counter")
    _, code, name, shares, amount = matches[0]
    excerpt = " ".join(f"{code} {name} {shares} {amount}".split())
    basis = "HKEX short-selling turnover; transaction flow for the stated session, not short-position stock or investor long/short ratio."
    return [
        _record(
            security_id, day, metric, value, unit, basis, session, f"text:stock:{symbol}", excerpt
        )
        for metric, value, unit in [
            ("short_sale_volume", shares, "shares"),
            ("short_sale_turnover", amount, "currency"),
        ]
    ]


OBSERVATION_PARSERS = {
    "sfc-short-positions-v1": parse_sfc_short_positions,
    "hkex-short-turnover-v1": parse_hkex_short_turnover,
}
PARSER_ERRORS = (ValueError, KeyError, TypeError, UnicodeError, InvalidOperation)


def parse_stockanalysis_statistics(
    data: bytes, symbol: str, security_id: str, *, observed_at: str = ""
) -> list[dict[str, Any]]:
    text = extract_html_text(data)
    if f"HKG:{int(symbol)}" not in text:
        raise ValueError("Security identity missing")
    moment = datetime.fromisoformat(observed_at)
    if moment.tzinfo is None:
        raise ValueError("Snapshot time requires timezone")
    definitions = [
        (
            "Shares Outstanding",
            "issued_shares",
            "shares",
            "Provider all-share-classes total; rounded displayed value",
        ),
        (
            "Float",
            "free_float_shares",
            "shares",
            "Provider Float; share-class universe/float methodology unverified; rounded displayed value",
        ),
        (
            "PE Ratio",
            "pe_provider",
            "multiple",
            "Provider PE Ratio, described as trailing PE; earnings/price alignment not independently verified",
        ),
    ]
    records = []
    for label, metric, unit, basis in definitions:
        match = re.search(r"\b" + re.escape(label) + r"\s+([0-9]+(?:\.[0-9]+)?)([BMT]?)\b", text)
        if not match:
            raise ValueError("Missing labelled statistic")
        scale = {"": 1, "M": 10**6, "B": 10**9, "T": 10**12}[match[2]]
        value = str(Decimal(match[1]) * scale)
        row = _record(
            security_id,
            "2000-01-01",
            metric,
            value,
            unit,
            basis + "; snapshot acquisition time is not the fundamental effective date",
            "point_in_time",
            "text:label:" + label,
            match[0],
        )
        del row["observed_date"]
        row["observed_at"] = moment.isoformat()
        row["share_class"] = (
            "Provider aggregation; class coverage stated in basis, no cross-class ratio inferred"
        )
        records.append(row)
    return records


def parse_stockanalysis_ratios(
    data: bytes, symbol: str, security_id: str, *, observed_at: str = ""
) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    if f"HKG:{int(symbol)}" not in extract_html_text(text):
        raise ValueError("Security identity missing")
    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", text, re.S | re.I):
        for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S | re.I):
            cells = [
                extract_html_text(cell)
                for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, re.S | re.I)
            ]
            if not cells or cells[0] != "PE Ratio":
                continue
            headers = re.findall(r'<th\b[^>]*id="([^"]+)"[^>]*>(.*?)</th>', table, re.S | re.I)
            headers = list(dict(headers).items())
            headers = [
                (key, value)
                for key, value in headers
                if key == "TTM" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", key)
            ]
            if len(headers) != len(cells) - 1:
                raise ValueError("PE table dates and values misaligned")
            records = []
            for (date_id, date_html), value in zip(headers, cells[1:], strict=True):
                if date_id == "TTM":
                    # This is a live comparative column, not a historical release.
                    continue
                day = datetime.strptime(date_id, "%Y-%m-%d").date().isoformat()
                if value in {"-", "n/a"}:
                    continue
                records.append(
                    _record(
                        security_id,
                        day,
                        "pe_provider",
                        value,
                        "multiple",
                        "StockAnalysis historical PE Ratio at provider period ending; hindsight snapshot, not proof of historical publication availability or independently recomputed PE",
                        "point_in_time",
                        f"text:PE Ratio:{day}",
                        extract_html_text(row_html),
                    )
                )
            if not records:
                raise ValueError("No reported historical PE")
            return records
    raise ValueError("No labelled PE table")


OBSERVATION_PARSERS.update(
    {
        "stockanalysis-statistics-v1": parse_stockanalysis_statistics,
        "stockanalysis-ratios-v1": parse_stockanalysis_ratios,
    }
)
