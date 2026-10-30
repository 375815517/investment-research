"""Acquire bounded price-history windows using the shared archive and admission service."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from investment_connectors import ConnectorService
from investment_domain import DomainError
from investment_engine import Service
from investment_repository import fingerprint, utc_now


def windows(start: date, end: date):
    if start > end:
        raise ValueError("Start must not follow end")
    while start <= end:
        boundary = date(start.year, 6, 30) if start.month <= 6 else date(start.year, 12, 31)
        stop = min(boundary, end)
        yield start, stop
        start = stop + timedelta(days=1)


def backfill(root: Path, source: str, security: str, start: date, end: date) -> dict:
    connector = ConnectorService(root)
    service = Service(root, connector)
    request = dict(source_id=source, security_id=security, start=str(start), end=str(end))
    run = dict(request=request, started_at=utc_now(), windows=[], status="running")
    run_id = "price-history-" + fingerprint(dict(request, started_at=run["started_at"]))[:24]
    for begin, stop in windows(start, end):
        result = dict(start=str(begin), end=str(stop))
        try:
            planned = connector.execute(
                "plan", dict(source_id=source, start_date=str(begin), end_date=str(stop))
            )
            if planned.get("security_id") != security:
                raise DomainError("SOURCE_SUBJECT_MISMATCH", "Source security differs from request")
            collected = service.execute(
                "collect", dict(source_id=source, parameters=planned["parameters"])
            )
            result["document_id"] = collected["document_id"]
            result["collection_refs"] = collected["artifact_refs"]
            prepared = service.execute(
                "prepare", dict(document_id=collected["document_id"], dataset_id="daily-prices")
            )
            candidate = service._candidate(prepared["candidate_id"])
            days = [row["trading_date"] for row in candidate["records"]]
            if any(day < str(begin) or day > str(stop) for day in days):
                raise DomainError(
                    "SOURCE_RANGE_MISMATCH", "Response contains dates outside request"
                )
            validated = service.execute("validate", dict(candidate_id=prepared["candidate_id"]))
            result["validation"] = validated
            if validated["status"] != "eligible":
                raise DomainError("QUALITY_BLOCKED", "History window did not pass validation")
            plan = service.execute("ingest_plan", dict(candidate_id=prepared["candidate_id"]))
            receipt = service.execute("ingest_apply", dict(plan_id=plan["plan_id"]))
            result.update(
                status=receipt["status"],
                observed_rows=len(days),
                first=min(days),
                last=max(days),
                artifact_refs=receipt["artifact_refs"],
            )
        except Exception as exc:
            result.update(
                status="blocked", code=getattr(exc, "code", type(exc).__name__), reason=str(exc)
            )
        run["windows"].append(result)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k not in ("validation", "artifact_refs", "collection_refs")
                }
            ),
            flush=True,
        )
        # A persisted independent receipt for every attempted window supports inspection/retry.
        service.repo.json(f"data/outputs/research-records/{run_id}/windows/{begin}.json", result)
    run["status"] = (
        "collected"
        if all(w["status"] in ("registered", "unchanged") for w in run["windows"])
        else "partial"
    )
    run["finished_at"] = utc_now()
    run["limitations"] = [
        "Collection success is not trading-calendar completeness",
        "Price and volume semantics remain as declared by each source",
    ]
    ref = f"data/outputs/research-records/{run_id}/run.json"
    service.repo.json(ref, run)
    print(json.dumps({"status": run["status"], "artifact_ref": ref}), flush=True)
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--source", required=True)
    parser.add_argument("--security", required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    result = backfill(args.workspace, args.source, args.security, args.start, args.end)
    return 0 if result["status"] == "collected" else 3


if __name__ == "__main__":
    raise SystemExit(main())
