"""Current HKEX report rows must not be confused with prior adjusted data."""

import pytest
from investment_connectors.hkex_daily import parse_hkex_daily_turnover

HTML = b"""<html>DATE: 29 OCT 2026 (THURSDAY)
<a name = "short_selling">SHORT SELLING TURNOVER - DAILY REPORT</a>
Total Short Selling Turnover             Total Turnover
CODE NAME (SH) ($) (SH) ($)
  700 TENCENT 100 2000 400 8000
 1810 XIAOMI-W 200 4000 800 16000
<a name = "adj_short">PREVIOUS DAY ADJUSTED</a>
 700 TENCENT 999 9999 99999 999999
</html>"""


def test_same_report_two_bindings_and_no_previous_day_leak():
    rows = parse_hkex_daily_turnover(HTML, "00700", "tencent-hk")
    assert [r["source_value"] for r in rows] == ["100", "2000", "400", "8000"]
    assert {r["observed_date"] for r in rows} == {"2026-10-29"}
    assert {r["security_id"] for r in rows} == {"tencent-hk"}
    other = parse_hkex_daily_turnover(HTML, "01810", "xiaomi-hk")
    assert other[0]["source_value"] == "200"


@pytest.mark.parametrize(
    "content",
    [
        HTML.replace(b"Total Short Selling Turnover", b"Other Turnover"),
        HTML.replace(b'"adj_short"', b'"changed"'),
        HTML.replace(b"100 2000 400 8000", b"500 2000 400 8000"),
        HTML.replace(b"700 TENCENT 100", b"701 OTHER 100"),
        HTML.replace(b"DATE:", b"UNKNOWN:"),
    ],
)
def test_changed_or_inconsistent_report_fails_closed(content):
    with pytest.raises(ValueError):
        parse_hkex_daily_turnover(content, "00700", "tencent-hk")


def test_rmb_counter_not_assumed_hkd():
    with pytest.raises(ValueError):
        parse_hkex_daily_turnover(HTML, "80700", "tencent-hk")
