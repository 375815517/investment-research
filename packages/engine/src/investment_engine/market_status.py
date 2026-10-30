"""Exclude vendor non-trading placeholders only when backed by explicit visible evidence."""

from investment_domain import DomainError, MarketClosure


def visible_closures(repo, mode, cutoff):
    result: dict[tuple[str, str], list[str]] = {}
    for path in sorted(repo.path("data/inputs/markets/trading-status").glob("*/*/*/status.json")):
        relative = path.relative_to(repo.root).as_posix()
        record = MarketClosure.model_validate(repo.read_json(relative))
        if path.parts[-4] != record.security_id:
            raise DomainError("STATUS_SCOPE_MISMATCH", relative)
        if mode != "retrospective_explanation":
            if not record.published_at or record.published_at > cutoff:
                continue
            if mode == "live_observed" and max(record.observed_at, record.registered_at) > cutoff:
                continue
        refs = [relative]
        for document_id in record.evidence_document_ids:
            _, ref = repo.document(document_id)
            refs.append(ref)
        result.setdefault((record.security_id, str(record.trading_date)), []).extend(refs)
    return result
