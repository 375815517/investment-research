"""Retry only recorded failed historical windows; preserve old failure receipts."""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path

from backfill_price_history import backfill
from investment_repository import Repository


def retry(root: Path, run_path: str, split_days: int = 90) -> dict:
    if not 1 <= split_days <= 183:
        raise ValueError("split_days must be within 1..183")
    repo = Repository(root)
    if not run_path.startswith("data/outputs/research-records/"):
        raise ValueError("A committed-style research run path is required")
    prior = repo.read_json(run_path)
    request = prior["request"]
    runs = []
    for window in prior["windows"]:
        if window["status"] != "blocked":
            continue
        begin, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        while begin <= end:
            stop = min(end, begin + timedelta(days=split_days - 1))
            runs.append(
                backfill(
                    root,
                    request["source_id"],
                    request.get("subject_id", request.get("security_id")),
                    begin,
                    stop,
                    request.get("dataset_id", "daily-prices"),
                )
            )
            begin = stop + timedelta(days=1)
    result = dict(
        status="collected" if all(r["status"] == "collected" for r in runs) else "partial",
        retry_of=run_path,
        runs=runs,
    )
    from investment_repository import fingerprint

    ref = f"data/outputs/research-records/price-retry-{fingerprint(result)[:24]}/run.json"
    repo.json(ref, result)
    print(json.dumps({"status": result["status"], "artifact_ref": ref}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--run", required=True)
    parser.add_argument("--split-days", type=int, default=90)
    args = parser.parse_args()
    raise SystemExit(
        0 if retry(args.workspace, args.run, args.split_days)["status"] == "collected" else 3
    )
