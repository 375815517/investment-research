"""Explicit publication-evidence review; never edits original metadata."""

import re
from pathlib import Path

from investment_domain import DocumentMetadataRevisionRequest, DomainError
from investment_repository.metadata import append_revision
from .datasets import html_text


def revise_metadata(service, payload):
    request = DocumentMetadataRevisionRequest.model_validate(payload)
    evidence, _ = service.repo.document(request.evidence_document_id)
    path = service.repo.path(evidence["path"])
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        match = re.fullmatch(r"pdf:page:([1-9][0-9]*)", request.locator)
        if not match or service.connector_service is None:
            raise DomainError(
                "PUBLICATION_EVIDENCE_INVALID", "PDF evidence needs physical page extractor"
            )
        page = service.connector_service.execute(
            "extract_pdf_page", {"path": str(path), "page": int(match[1])}
        )
        text = page["text"]
    elif suffix in (".html", ".htm"):
        text = html_text(path.read_text())
    elif suffix in (".txt", ".md", ".csv", ".json"):
        text = path.read_text()
    else:
        raise DomainError("PUBLICATION_EVIDENCE_INVALID", "Unsupported publication evidence format")
    if " ".join(request.excerpt.split()) not in " ".join(text.split()):
        raise DomainError(
            "PUBLICATION_EVIDENCE_INVALID", "Publication excerpt is absent from evidence"
        )
    return append_revision(service.repo, request)
