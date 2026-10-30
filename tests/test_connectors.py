from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from investment_connectors import ConnectorError, ConnectorService, HttpFetcher, SourceDefinition

CSV = b"security_id,trading_date,open,high,low,close,volume,currency\ndemo-hk,2025-01-02,10,12,9,11,100,HKD\n"


class Response(io.BytesIO):
    def __init__(self, body=CSV, content_type="text/csv"):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


class Opener:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def definition(**kwargs):
    return SourceDefinition(
        source_id="fixture",
        url="https://example.invalid/prices",
        archive_permissions="allowed",
        **kwargs,
    )


def test_csv_delivery_is_original_and_does_not_claim_ingested(tmp_path):
    fetcher = HttpFetcher(opener=Opener(Response()))
    result = fetcher.fetch(definition(), {}, tmp_path)
    assert Path(result.path).read_bytes() == CSV
    assert result.rows == 1
    assert result.size_bytes == len(CSV)
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "body,kind",
    [
        (b"<html>rate limited</html>", "text/html"),
        (b"<!DOCTYPE html>bad", "text/plain"),
        (b"error\nrate limited\n", "text/plain"),
        (b"", "text/csv"),
        (b'{"error": true}', "application/json"),
    ],
)
def test_success_http_error_content_rejected(tmp_path, body, kind):
    with pytest.raises(ConnectorError, match="CSV|HTML"):
        HttpFetcher(opener=Opener(Response(body, kind))).fetch(definition(), {}, tmp_path)
    assert not list(tmp_path.iterdir())


def test_size_bound(tmp_path):
    with pytest.raises(ConnectorError) as caught:
        HttpFetcher(opener=Opener(Response())).fetch(definition(max_bytes=10), {}, tmp_path)
    assert caught.value.code == "SOURCE_SIZE_LIMIT"


def test_retry_is_bounded_and_secret_not_in_error(tmp_path):
    errors = [URLError("private_token=DO_NOT_PRINT"), URLError("private_token=DO_NOT_PRINT")]
    opener = Opener(*errors)
    with pytest.raises(ConnectorError) as caught:
        HttpFetcher(opener=opener, sleep=lambda _: None).fetch(definition(), {}, tmp_path)
    assert len(opener.calls) == 2
    assert "DO_NOT_PRINT" not in str(caught.value)
    assert caught.value.retryable


def test_http_auth_error_not_retried(tmp_path):
    opener = Opener(HTTPError("https://example.invalid", 401, "secret details", {}, None))
    with pytest.raises(ConnectorError) as caught:
        HttpFetcher(opener=opener).fetch(definition(), {}, tmp_path)
    assert len(opener.calls) == 1
    assert not caught.value.retryable
    assert "secret details" not in str(caught.value)


def test_temporary_failure_then_csv(tmp_path):
    opener = Opener(HTTPError("https://example.invalid", 503, "temporary", {}, None), Response())
    result = HttpFetcher(opener=opener, sleep=lambda _: None).fetch(definition(), {}, tmp_path)
    assert result.attempts == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"url": "file:///tmp/a"},
        {"url": "https://user:pass@example.invalid/a"},
        {"url": "https://example.invalid/a?token=secret"},
        {"connector_id": "run-python"},
        {"max_attempts": 100},
        {"auth_env": "secret-value!"},
    ],
)
def test_config_rejects_unsafe_or_unknown_values(kwargs):
    values = {"source_id": "fixture", "url": "https://example.invalid/a"}
    values.update(kwargs)
    with pytest.raises(ConnectorError):
        SourceDefinition(**values)


def test_parameter_allowlist(tmp_path):
    with pytest.raises(ConnectorError):
        HttpFetcher(opener=Opener()).fetch(definition(), {"unknown": "value"}, tmp_path)


def test_credential_is_header_only_and_readiness_is_honest(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_TEST_TOKEN", "private-value")
    source = definition(auth_env="RESEARCH_TEST_TOKEN")
    readiness = source.readiness()
    assert readiness["authentication"] == "configured"
    assert readiness["network"] == "not_checked"
    assert "private-value" not in json.dumps(readiness)
    opener = Opener(Response())
    result = HttpFetcher(opener=opener).fetch(source, {}, tmp_path)
    assert opener.calls[0][0].get_header("Authorization") == "Bearer private-value"
    assert "private-value" not in json.dumps(result.request)


def test_service_source_check_and_collect(tmp_path):
    directory = tmp_path / "research/sources/fixture"
    directory.mkdir(parents=True)
    (directory / "source.yaml").write_text(
        json.dumps(
            {
                "source_id": "fixture",
                "url": "https://example.invalid/prices",
                "archive_permissions": "allowed",
            }
        )
    )
    service = ConnectorService(tmp_path, fetcher=HttpFetcher(opener=Opener(Response())))
    assert (
        service.execute("source_check", {"source_id": "fixture"})["source"]["network"]
        == "not_checked"
    )
    result = service.execute("collect", {"source_id": "fixture"})
    assert result["status"] == "acquired"
    assert Path(result["import_request"]["path"]).read_bytes() == CSV
    assert not (tmp_path / "data").exists()


def test_source_path_traversal_rejected(tmp_path):
    with pytest.raises(ConnectorError):
        SourceDefinition.load(tmp_path, "../outside")


def test_unknown_archival_permission_stops_before_network(tmp_path):
    opener = Opener()
    source = SourceDefinition(source_id="fixture", url="https://example.invalid/prices")
    with pytest.raises(ConnectorError) as caught:
        HttpFetcher(opener=opener).fetch(source, {}, tmp_path)
    assert caught.value.code == "SOURCE_ARCHIVE_BLOCKED"
    assert not opener.calls


def yahoo_fixture(symbol="1810.HK"):
    return json.dumps(
        {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "symbol": symbol,
                            "currency": "HKD",
                            "exchangeTimezoneName": "Asia/Hong_Kong",
                            "exchangeName": "HKG",
                            "dataGranularity": "1d",
                        },
                        "timestamp": [1735781400, 1735867800],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [10, None],
                                    "high": [12, None],
                                    "low": [9, None],
                                    "close": [11, None],
                                    "volume": [100, None],
                                }
                            ],
                            "adjclose": [{"adjclose": [8, 9]}],
                        },
                    }
                ],
            }
        }
    ).encode()


def test_yahoo_parser_keeps_native_basis_and_missing_rows():
    from investment_connectors import parse_yahoo_chart

    result = parse_yahoo_chart(yahoo_fixture(), "1810.HK", "xiaomi-hk")
    assert len(result["records"]) == 1
    assert result["records"][0]["close"] == "11"
    assert result["records"][0]["price_basis"] == "provider-native"
    assert result["missing_or_provisional_dates"]
    assert result["limitations"]


def test_yahoo_mismatched_symbol_is_rejected():
    from investment_connectors import parse_yahoo_chart

    with pytest.raises(ConnectorError):
        parse_yahoo_chart(yahoo_fixture(), "OTHER.HK", "xiaomi-hk")


def test_yahoo_url_template_and_original_json(tmp_path):
    source = SourceDefinition(
        source_id="yahoo-test",
        url="https://example.invalid/chart/{symbol}",
        connector_id="yahoo-chart-v1",
        allowed_parameters=("symbol", "interval"),
        archive_permissions="allowed",
    )
    opener = Opener(Response(yahoo_fixture(), "application/json"))
    result = HttpFetcher(opener=opener).fetch(
        source, {"symbol": "1810.HK", "interval": "1d"}, tmp_path
    )
    assert "/chart/1810.HK?interval=1d" in opener.calls[0][0].full_url
    assert Path(result.path).suffix == ".json"
    assert Path(result.path).read_bytes() == yahoo_fixture()
