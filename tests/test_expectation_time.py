"""Calendar completeness is only knowable when its supporting evidence is available."""

import pytest

from investment_engine import Service
from test_ensure import expectation


@pytest.mark.parametrize("published", [None, "2024-02-01T00:00:00Z"])
def test_historical_calendar_requires_visible_supporting_document(tmp_path, published):
    service = Service(tmp_path)
    path = tmp_path / "calendar.txt"
    path.write_text("Synthetic closure calendar")
    doc = service.execute(
        "import", dict(path=str(path), source_id="demo-calendar", published_at=published)
    )
    request = expectation(
        service,
        doc["document_id"],
        items=[
            dict(
                date="2024-01-02",
                expected=False,
                due_at="2024-01-02T08:30:00Z",
                reason="Synthetic closure",
            )
        ],
    )
    result = service.execute(
        "detect_gaps",
        dict(
            request,
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-04T00:00:00Z",
        ),
    )
    assert result["status"] == "blocked"
    assert result["gaps"][0]["reason"] == "expectation_unavailable_at_cutoff"
    # Retrospective explanations may use evidence acquired later, explicitly.
    assert service.execute("detect_gaps", request)["status"] == "complete"


def test_live_calendar_requires_document_observed_before_cutoff(tmp_path):
    service = Service(tmp_path)
    path = tmp_path / "calendar.txt"
    path.write_text("Synthetic trading calendar")
    doc = service.execute(
        "import",
        dict(path=str(path), source_id="demo-calendar", published_at="2023-12-01T00:00:00Z"),
    )
    request = expectation(service, doc["document_id"])
    result = service.execute(
        "detect_gaps",
        dict(request, knowledge_mode="live_observed", information_cutoff="2024-01-04T00:00:00Z"),
    )
    assert result["status"] == "blocked"
    assert result["gaps"][0]["reason"] == "expectation_unavailable_at_cutoff"
    reconstructed = service.execute(
        "detect_gaps",
        dict(
            request,
            knowledge_mode="historical_reconstruction",
            information_cutoff="2024-01-04T00:00:00Z",
        ),
    )
    assert reconstructed["gaps"][0]["reason"] == "missing_observation"
