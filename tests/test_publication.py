"""Publication must not accidentally include unrelated work or overwrite evidence."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "publication", Path(__file__).parents[1] / "scripts/check_publication.py"
)
assert spec and spec.loader
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


def test_explicit_manifest_and_history(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    old = tmp_path / "data/inputs/markets/prices/old.csv"
    old.parent.mkdir(parents=True)
    old.write_text("original\n")
    git("add", ".")
    git("commit", "-m", "fixture")
    old.write_text("overwritten\n")
    (tmp_path / "unrelated.txt").write_text("user work")
    git("add", ".")
    result = publication.check(tmp_path, ["data/inputs/markets/prices/old.csv"])
    assert "HISTORY_OVERWRITE: data/inputs/markets/prices/old.csv" in result
    assert "OUTSIDE_MANIFEST: unrelated.txt" in result


@pytest.mark.parametrize(
    ("relative", "blocked"),
    [
        ("data/inputs/source-files/demo/2024/doc-test/v1/original.md", True),
        ("data/inputs/source-files/demo/2024/doc-test/v1/README.md", True),
        ("data/inputs/collection-records/demo/2024/run/README.md", True),
        ("data/inputs/companies/demo/financials/2024/fact.md", True),
        ("data/inputs/companies/demo/README.md", False),
        ("data/inputs/companies/demo/.gitkeep", False),
    ],
)
def test_only_business_navigation_is_exempt_from_history_protection(tmp_path, relative, blocked):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "user.name", "Fixture")
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("original\n")
    git("add", ".")
    git("commit", "-m", "fixture")
    path.write_text("changed\n")
    git("add", ".")
    assert (f"HISTORY_OVERWRITE: {relative}" in publication.check(tmp_path, [relative])) is blocked
