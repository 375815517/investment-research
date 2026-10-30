"""Resolve source-reported action confirmations to registered declarations."""


def resolve(repo, record):
    target = record.get("updates_action_id")
    if not target:
        return [], []
    matches = []
    batches = repo.batches()
    superseded = {prior for _, batch in batches for prior in batch.get("supersedes", [])}
    for ref, batch in batches:
        if batch.get("batch_id") in superseded:
            continue
        if batch["dataset_id"] != "corporate-actions":
            continue
        for row in batch["rows"]:
            if row.get("action_id") == target and row["security_id"] == record["security_id"]:
                matches.append((ref, batch, row))
    if len(matches) != 1:
        raise ValueError("Action update requires one registered declaration for the same security")
    ref, batch, row = matches[0]
    if row["action_type"] != record["action_type"]:
        raise ValueError("Action update cannot change the declared action type")
    if row["announcement_date"] > record["announcement_date"]:
        raise ValueError("Action update cannot predate the referenced declaration")
    if row.get("updates_action_id") == record["action_id"]:
        raise ValueError("Action update cycle is invalid")
    return sorted(set([ref, *batch.get("dependency_batches", [])])), batch["documents"]
