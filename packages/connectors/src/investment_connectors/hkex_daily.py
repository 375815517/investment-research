"""HKEX same-day short/total turnover, scoped to the selected HKD counter."""

import re
from datetime import datetime


def parse_hkex_daily_turnover(data, symbol, security_id, *, observed_at=""):
    from .observations import _record

    text = data.decode("utf-8-sig")
    date_match = re.search(r"DATE:\s*(\d{1,2} [A-Z]{3} \d{4})", text[:6000])
    anchor = re.search(r"<a\s+name\s*=\s*[\"\']short_selling[\"\']", text, re.I)
    if not date_match or not anchor:
        raise ValueError("Missing HKEX daily date or current short-selling section")
    section = text[anchor.start() :]
    next_anchor = re.search(r"<a\s+name\s*=\s*[\"\']adj_short[\"\']", section, re.I)
    if not next_anchor:
        raise ValueError(
            "Missing short-selling section end; cannot distinguish adjusted previous day"
        )
    section = section[: next_anchor.start()]
    if not re.search(r"Total Short Selling Turnover\s+Total Turnover", section):
        raise ValueError("HKEX short/total column labels changed")
    if not re.search(r"\(SH\)\s+\(\$\)\s+\(SH\)\s+\(\$\)", section):
        raise ValueError("HKEX shares/currency units changed")
    if not re.fullmatch(r"0*\d{1,5}", symbol) or int(symbol) >= 80000:
        raise ValueError("Only explicit HKD counters are supported by this parser")
    matches = re.findall(
        r"^\s*(\d+)\s+(.+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$",
        section,
        re.M,
    )
    matches = [row for row in matches if int(row[0]) == int(symbol)]
    if len(matches) != 1:
        raise ValueError("Expected exactly one selected-counter short-selling row")
    code, name, short_volume, short_amount, volume, amount = matches[0]
    from decimal import Decimal

    if Decimal(short_volume.replace(",", "")) > Decimal(volume.replace(",", "")) or (
        Decimal(short_amount.replace(",", "")) > Decimal(amount.replace(",", ""))
    ):
        raise ValueError("Short turnover exceeds the same-counter total")
    day = datetime.strptime(date_match[1], "%d %b %Y").date().isoformat()
    excerpt = " ".join(f"{code} {name} {short_volume} {short_amount} {volume} {amount}".split())
    basis = (
        "HKEX Daily Quotations current-day short-selling report; same HKD counter "
        "short/total transaction flow, not positions or investor long/short distribution"
    )
    return [
        _record(
            security_id,
            day,
            metric,
            value,
            unit,
            basis,
            "full_day",
            f"text:section:short_selling:stock:{int(symbol)}",
            excerpt,
        )
        for metric, value, unit in [
            ("short_sale_volume", short_volume, "shares"),
            ("short_sale_turnover", short_amount, "currency"),
            ("volume", volume, "shares"),
            ("turnover", amount, "currency"),
        ]
    ]
