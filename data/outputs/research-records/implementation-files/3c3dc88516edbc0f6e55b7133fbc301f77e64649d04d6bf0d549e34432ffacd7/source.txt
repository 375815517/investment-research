"""Run a synthetic offline CLI acceptance in a temporary workspace, never production data."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_demo() -> dict:
    with tempfile.TemporaryDirectory(prefix="research-demo-") as directory:
        root = Path(directory)
        (root / "pyproject.toml").write_text("[tool.investment-research]\nschema-version = 1\n")
        (root / "AGENTS.md").write_text("Synthetic acceptance workspace.\n")
        price = {
            "security_id": "demo-xiaomi",
            "trading_date": "2024-01-02",
            "open": "10",
            "high": "12",
            "low": "9",
            "close": "11",
            "volume": "1000",
            "currency": "HKD",
            "volume_unit": "shares",
            "price_basis": "unadjusted",
            "session": "regular-final",
        }
        original = root / "synthetic-prices.csv"
        with original.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(price))
            writer.writeheader()
            writer.writerow(price)
        calls = []

        def cli(arguments: list[str], payload: dict | None = None) -> dict:
            command = [
                sys.executable,
                "-m",
                "investment_cli",
                "--workspace",
                str(root),
                "--json",
                *arguments,
            ]
            if payload is not None:
                command += ["--request", "-"]
            result = subprocess.run(
                command,
                input=json.dumps(payload) if payload is not None else None,
                text=True,
                capture_output=True,
                check=False,
                cwd="/tmp",
            )
            output = json.loads(result.stdout)
            if result.returncode:
                raise RuntimeError(f"{arguments}: {output}")
            calls.append({"command": " ".join(arguments), "status": output["status"]})
            return output

        doc = cli(
            ["data", "import"],
            {
                "path": str(original),
                "source_id": "demo-source",
                "published_at": "2024-01-03T00:00:00Z",
            },
        )
        again = cli(["data", "import"], {"path": str(original), "source_id": "demo-source"})
        assert again["document_id"] == doc["document_id"]
        batch = cli(
            ["data", "prepare"], {"document_id": doc["document_id"], "dataset_id": "daily-prices"}
        )
        cli(["data", "validate"], {"candidate_id": batch["candidate_id"]})
        plan = cli(["data", "ingest", "--dry-run"], {"candidate_id": batch["candidate_id"]})
        cli(["data", "ingest", "--apply"], {"plan_id": plan["plan_id"]})
        assert (
            cli(["data", "ingest", "--apply"], {"plan_id": plan["plan_id"]})["status"]
            == "unchanged"
        )
        assert cli(["data", "coverage"], {"subject_id": "demo-xiaomi"})["record_count"] == 1
        assert (
            cli(
                ["data", "coverage"],
                {
                    "knowledge_mode": "historical_reconstruction",
                    "information_cutoff": "2024-01-02T12:00:00Z",
                },
            )["record_count"]
            == 0
        )
        cli(["data", "index", "--rebuild"])
        (root / ".research-local/index.json").unlink()
        cli(["data", "index", "--rebuild"])
        report = root / "synthetic-report.txt"
        report.write_text("Synthetic fixture: consolidated revenue 100 million CNY in 2024.\n")
        financial_doc = cli(["data", "import"], {"path": str(report), "source_id": "demo-report"})
        fact = {
            "company_id": "demo-xiaomi",
            "metric_id": "revenue",
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "source_value": "100",
            "source_unit": "millions",
            "currency": "CNY",
            "scope": "consolidated",
            "record_kind": "reported_actual",
            "locator": "line:1",
            "excerpt": report.read_text().strip(),
        }
        candidate = cli(
            ["data", "prepare"],
            {
                "document_id": financial_doc["document_id"],
                "dataset_id": "financial-facts",
                "records": [fact],
            },
        )
        # Review is an explicit fixture check, not a claim of independent AI validation.
        cli(
            ["data", "review"],
            {
                "candidate_id": candidate["candidate_id"],
                "reviewer": "offline-fixture-review",
                "decision": "approved",
                "notes": "Synthetic original line 1 checked; no live model used.",
            },
        )
        plan = cli(["data", "ingest", "--dry-run"], {"candidate_id": candidate["candidate_id"]})
        cli(["data", "ingest", "--apply"], {"plan_id": plan["plan_id"]})
        assert cli(["data", "coverage"], {"dataset_id": "financial-facts"})["record_count"] == 1
        return {
            "status": "passed",
            "data_identity": "synthetic",
            "production_data_written": False,
            "steps": calls,
        }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
