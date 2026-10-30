"""Conservative point-in-time availability of archived supporting documents."""

from datetime import datetime

from investment_domain import DomainError


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise DomainError("TIMEZONE_REQUIRED", "Evidence timestamp must include timezone")
    return result


def document_available(document, mode, cutoff):
    if mode == "retrospective_explanation":
        return True
    published = document.get("availability_upper_bound", document.get("published_at"))
    if not published or timestamp(published) > cutoff:
        return False
    if mode == "live_observed":
        revised = document.get("metadata_revision_recorded_at")
        if revised and timestamp(revised) > cutoff:
            return False
        observed = document.get("first_observed_at")
        if not observed or timestamp(observed) > cutoff:
            return False
    return True
