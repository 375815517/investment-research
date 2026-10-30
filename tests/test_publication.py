"""Publication must not accidentally include unrelated work or overwrite evidence."""

import importlib.util
import subprocess
from pathlib import Path

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
