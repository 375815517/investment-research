"""Build immutable exact-input profiles from approved scope and metric definitions.

Requirements come from reviewed configuration, never from the rows already acquired.
Changing a requirement writes a new profile version rather than shrinking old scopes.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from investment_domain import InputRequirementProfile, MetricDefinition
from investment_repository import Repository, identifier


def build(workspace: Path, definition: dict) -> list[str]:
    repo = Repository(workspace)
    version = identifier(definition["version"])
    outputs = []
    for company in definition["companies"]:
        company_id = identifier(company["company_id"])
        security_id = identifier(company["confirmed_security_id"])
        securities = list(repo.path("data/inputs/markets/securities").rglob("security.json"))
        confirmed = [json.loads(path.read_text()) for path in securities if not path.is_symlink()]
        if not any(
            item.get("security_id") == security_id
            and item.get("company_id") == company_id
            and item.get("user_confirmed") is True
            for item in confirmed
        ):
            raise ValueError(f"No confirmed primary security for {company_id}")
        for specification in company["profiles"]:
            name = identifier(specification["name"])
            keys = []
            for year in specification["years"]:
                if type(year) is not int or not 1900 <= year <= 2100:
                    raise ValueError("Profile years must be explicit calendar years")
                for field in specification["fields"]:
                    if "years" in field:
                        field_years = field["years"]
                        if (
                            not isinstance(field_years, list)
                            or not field_years
                            or any(type(value) is not int for value in field_years)
                            or not set(field_years) <= set(specification["years"])
                        ):
                            raise ValueError(
                                "Field years must be a nonempty subset of profile years"
                            )
                        if year not in field_years:
                            continue
                    metric_id = identifier(field["metric_id"])
                    metric = MetricDefinition.model_validate(
                        repo.read_json(f"research/metrics/{metric_id}/v1.json")
                    )
                    period_type = field.get(
                        "period_type", "instant" if metric.measure_kind == "stock" else "annual"
                    )
                    if period_type not in {"instant", "annual"} and not all(
                        field.get(key) for key in ("period_start_month_day", "period_end_month_day")
                    ):
                        raise ValueError("Non-annual profiles require explicit period boundaries")
                    if period_type not in metric.allowed_period_types:
                        raise ValueError(f"Unsupported period for {metric_id}")
                    dimensions = field.get("dimensions", {})
                    if (
                        not set(metric.required_dimensions)
                        <= set(dimensions)
                        <= set(metric.allowed_dimensions)
                    ):
                        raise ValueError(f"Invalid dimensions for {metric_id}")
                    period_year = year + field.get("year_offset", 0)
                    selectors = dict(
                        metric_id=metric_id,
                        metric_version=metric.version,
                        period_end=date.fromisoformat(
                            f"{period_year}-{field.get('period_end_month_day', '12-31')}"
                        ).isoformat(),
                        period_type=period_type,
                        measure_kind=metric.measure_kind,
                        scope=field.get("scope", "consolidated"),
                        unit=metric.unit,
                        dimensions=dimensions,
                        adjustment_basis="reported",
                        restatement="original",
                    )
                    if period_type != "instant":
                        selectors["period_start"] = date.fromisoformat(
                            f"{period_year}-{field.get('period_start_month_day', '01-01')}"
                        ).isoformat()
                    if metric.unit in {"currency", "currency_per_share"}:
                        selectors["currency"] = company["financial_currency"]
                    if metric.dataset_id == "financial-observations":
                        selectors["accounting_standard"] = field.get(
                            "accounting_standard",
                            specification.get(
                                "accounting_standard", company["accounting_standard"]
                            ),
                        )
                    source_template = field.get(
                        "source_id_template",
                        specification.get("source_id_template", company["source_id_template"]),
                    )
                    source = (
                        source_template.replace("{year}", str(year)) if source_template else None
                    )
                    if source:
                        identifier(source)
                    field_id = identifier(field.get("field_id", metric_id))
                    keys.append(
                        dict(
                            key_id=f"{field_id}-{year}",
                            dataset_id=metric.dataset_id,
                            subject_id=company_id,
                            source_id=source,
                            selectors=selectors,
                            required=True,
                            max_matches=1,
                        )
                    )
            profile = InputRequirementProfile.model_validate(
                dict(
                    profile_id=f"{company_id}-{name}",
                    version=version,
                    purpose=specification.get("purpose", "source_description"),
                    expected_keys=keys,
                    comparison_groups=[],
                    definition_refs=specification.get("definition_refs", []),
                    knowledge_mode="retrospective_explanation",
                )
            )
            path = f"research/input-profiles/{profile.profile_id}/v{version}.json"
            payload = profile.model_dump(mode="json", exclude_none=True)
            if not payload.get("definition_refs"):
                existing = repo.read_json(path) if repo.path(path).exists() else {}
                if "definition_refs" not in existing:
                    payload.pop("definition_refs", None)
            repo.json(path, payload)
            outputs.append(path)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--definition", default="research/input-profile-definitions/dual-company-v1.json"
    )
    args = parser.parse_args()
    repo = Repository(args.workspace)
    if not args.definition.startswith("research/input-profile-definitions/"):
        parser.error("Definition must be registered under research/input-profile-definitions/")
    outputs = build(args.workspace, repo.read_json(args.definition))
    print(json.dumps({"status": "registered", "artifact_refs": outputs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
