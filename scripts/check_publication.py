"""Validate an explicit Git index before publication; never stage or commit files."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def check(workspace: Path, allowed: list[str]) -> list[str]:
    """Return errors for staged changes outside an explicit list or protected history."""

    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(workspace), *args])

    errors = []
    entries = git("diff", "--cached", "--name-status", "--no-renames", "-z").decode().split("\0")
    permitted = set(allowed)
    for status, path in zip(entries[0:-1:2], entries[1::2]):
        if path not in permitted:
            errors.append(f"OUTSIDE_MANIFEST: {path}")
        if path.startswith("legacy/"):
            errors.append(f"LEGACY_PROTECTED: {path}")
        if path.startswith("data/inputs/") and status != "A":
            # Only business-directory navigation and skeletons may change. Markdown
            # source originals are evidence too, irrespective of file extension.
            parts = Path(path).parts
            navigation = parts[-1] in {"README.md", ".gitkeep"} and parts[2] not in {
                "source-files",
                "collection-records",
            }
            if not navigation:
                errors.append(f"HISTORY_OVERWRITE: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest", type=Path, required=True, help="JSON array of exact staged paths"
    )
    args = parser.parse_args()
    allowed = json.loads(args.manifest.read_text())
    if not isinstance(allowed, list) or not all(isinstance(x, str) for x in allowed):
        parser.error("manifest must be a JSON array of paths")
    errors = check(args.workspace, allowed)
    print(json.dumps({"status": "blocked" if errors else "passed", "issues": errors}))
    return 3 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
