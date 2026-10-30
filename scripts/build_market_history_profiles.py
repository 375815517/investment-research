"""Build exact price-history demand from a versioned session calendar, never observed rows."""

import argparse
import json
from pathlib import Path

from investment_domain import InputRequirementProfile
from investment_repository import Repository, identifier


def build(
    root, calendar, dataset, subject, source, currency="HKD", version="1", definition_refs=None
):
    repo = Repository(root)
    identifier(version)
    sessions = repo.read_json(calendar)["sessions"]
    if not sessions or len(sessions) != len(set(sessions)):
        raise ValueError("Calendar session dates must be unique")
    keys = []
    for day in sessions:
        selectors = (
            dict(index_type="price_index", unit="points")
            if dataset == "benchmark-prices"
            else dict(price_basis="provider-native", session="regular-final", currency=currency)
        )
        keys.append(
            dict(
                key_id=f"{subject}-{day}",
                dataset_id=dataset,
                subject_id=subject,
                source_id=source,
                selectors=dict(trading_date=day, **selectors),
            )
        )
    profile = InputRequirementProfile.model_validate(
        dict(
            profile_id=f"{subject}-history-{min(sessions)[:4]}-{max(sessions)[:4]}",
            expected_keys=keys,
            version=version,
            definition_refs=definition_refs or [],
        )
    ).model_dump(mode="json")
    if not profile["definition_refs"]:
        profile.pop("definition_refs")
    target = f"research/input-profiles/{profile['profile_id']}/v{version}.json"
    repo.json(target, profile)
    repo.json(
        f"research/input-profile-definitions/{profile['profile_id']}{'' if version == '1' else '-v' + version}.json",
        dict(
            calendar_ref=calendar,
            dataset_id=dataset,
            subject_id=subject,
            source_id=source,
            currency=currency if dataset == "daily-prices" else None,
            expected_dates=len(sessions),
            limitations=[
                "Model exchange calendar is not proof of security-specific trading or suspension",
                "Provider-native history coverage does not certify volume units or adjustment basis",
                "Index demand is price index, not total return",
            ],
        ),
    )
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--calendar", required=True)
    parser.add_argument("--dataset", choices=["daily-prices", "benchmark-prices"], required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--currency", default="HKD")
    parser.add_argument("--version", default="1")
    parser.add_argument("--definition-ref", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            dict(
                profile_path=build(
                    args.workspace,
                    args.calendar,
                    args.dataset,
                    args.subject,
                    args.source,
                    args.currency,
                    args.version,
                    args.definition_ref,
                )
            )
        )
    )
