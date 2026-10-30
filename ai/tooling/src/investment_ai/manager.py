"""Plan-bound Skill installation. Canonical content is never edited here."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit

TARGETS = {"codex": ".agents/skills", "codebuddy": ".codebuddy/skills"}
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
LINK = re.compile(r"(!?\[[^\]]*\]\()([^\s)]+)(\))")


class HostError(Exception):
    def __init__(self, code: str, message: str, exit_code: int = 4):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


class HostManager:
    def __init__(self, workspace: Path):
        self.root = Path(workspace).resolve()
        if not (self.root / "AGENTS.md").is_file():
            raise HostError("WORKSPACE_INVALID", "Workspace must contain AGENTS.md", 2)

    def path(self, relative: str) -> Path:
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts:
            raise HostError("PATH_INVALID", "Only workspace-relative paths are accepted", 2)
        current = self.root
        for part in rel.parts:
            current /= part
            if current.is_symlink():
                raise HostError("SYMLINK_REJECTED", f"Symlink is not writable: {relative}")
        return current

    def read(self, relative: str) -> bytes | None:
        p = self.path(relative)
        if p.exists() and not p.is_file():
            raise HostError("PATH_CONFLICT", f"Expected file: {relative}")
        return p.read_bytes() if p.exists() else None

    def write(self, relative: str, data: bytes) -> None:
        p = self.path(relative)
        p.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=p.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            self.path(relative)
            os.replace(temporary, p)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def lock(self) -> Iterator[None]:
        import fcntl

        p = self.path(".research-local/hosts/install.lock")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def receipt_path(self, host: str) -> str:
        return f".research-local/hosts/{host}/receipt.json"

    def load_receipt(self, host: str) -> dict[str, Any]:
        raw = self.read(self.receipt_path(host))
        return json.loads(raw) if raw else {"files": {}}

    def profile(self, host: str) -> dict[str, Any]:
        if host not in TARGETS:
            raise HostError("HOST_UNSUPPORTED", f"Unknown host: {host}", 2)
        raw = self.read(f"ai/adapters/{host}/profile.json")
        if raw is None:
            raise HostError("PROFILE_MISSING", f"Missing profile for {host}", 2)
        profile = json.loads(raw)
        if profile.get("host_id") != host or profile.get("target_directory") != TARGETS[host]:
            raise HostError(
                "PROFILE_INVALID", "Profile target must match the registered adapter", 2
            )
        return profile

    def project(self, source: Path, target: Path) -> bytes:
        data = source.read_bytes()
        if source.suffix != ".md":
            return data

        def rewrite(match: re.Match[str]) -> str:
            url = match[2]
            parts = urlsplit(url)
            if parts.scheme or url.startswith("#"):
                return match[0]
            if url.startswith("/"):
                raise HostError("LINK_INVALID", f"Absolute link in {source.name}", 2)
            resolved = (source.parent / unquote(parts.path)).resolve()
            if not resolved.is_relative_to(self.root) or not resolved.exists():
                raise HostError("LINK_INVALID", f"Broken or external relative resource: {url}", 2)
            reference = os.path.relpath(resolved, target.parent).replace(os.sep, "/")
            if parts.query:
                reference += "?" + parts.query
            if parts.fragment:
                reference += "#" + parts.fragment
            return match[1] + reference + match[3]

        return LINK.sub(rewrite, data.decode()).encode()

    def sources(self, host: str) -> tuple[dict[str, str], dict[str, bytes]]:
        snapshots: dict[str, str] = {}
        projection: dict[str, bytes] = {}
        profile = self.profile(host)
        profile_path = f"ai/adapters/{host}/profile.json"
        snapshots[profile_path] = digest(self.read(profile_path) or b"")
        for source in sorted(self.path("ai/skills").rglob("*")):
            if source.is_symlink():
                raise HostError("SYMLINK_REJECTED", "Canonical Skills may not contain symlinks")
            if not source.is_file() or source.name == ".gitkeep":
                continue
            relative = source.relative_to(self.root).as_posix()
            self.path(relative)
            suffix = source.relative_to(self.root / "ai/skills")
            if len(suffix.parts) < 2 or not ID.fullmatch(suffix.parts[0]):
                raise HostError("SKILL_LAYOUT_INVALID", f"Invalid Skill file: {relative}", 2)
            target = f"{profile['target_directory']}/{suffix.as_posix()}"
            snapshots[relative] = digest(source.read_bytes())
            projection[target] = self.project(source, self.path(target))
        if not projection:
            raise HostError("SKILLS_MISSING", "No canonical Skills to install", 2)
        return snapshots, projection

    def plan(self, host: str, action: str = "install") -> dict[str, Any]:
        snapshots, projection = self.sources(host)
        receipt = self.load_receipt(host)
        old_files = receipt.get("files", {})
        candidates = set(old_files) | (set(projection) if action == "install" else set())
        changes = []
        issues = []
        for target in sorted(candidates):
            if not target.startswith(TARGETS[host] + "/"):
                raise HostError("RECEIPT_INVALID", "Receipt contains an unexpected target")
            before = self.read(target)
            before_hash = digest(before) if before is not None else None
            owned_hash = old_files.get(target)
            after = projection.get(target) if action == "install" else None
            after_hash = digest(after) if after is not None else None
            # Never claim ownership of an existing file lacking an install receipt.
            if before is not None and (owned_hash is None or before_hash != owned_hash):
                issues.append({"code": "USER_MODIFIED", "path": target, "severity": "error"})
                continue
            if before_hash != after_hash:
                changes.append(
                    {
                        "path": target,
                        "before": before_hash,
                        "after": after_hash,
                        "content": after.decode()
                        if after is not None and target.endswith(".md")
                        else None,
                        "source": next(
                            (
                                s
                                for s in snapshots
                                if s.startswith("ai/skills/")
                                and target.endswith(s[len("ai/skills/") :])
                            ),
                            None,
                        ),
                    }
                )
        body = {
            "host": host,
            "action": action,
            "sources": snapshots,
            "changes": changes,
            "issues": issues,
            "receipt_hash": digest(encoded(receipt)),
            "desired": {key: digest(value) for key, value in projection.items()}
            if action == "install"
            else {},
        }
        body["plan_id"] = digest(encoded(body))[:24]
        return body

    def apply(self, plan_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[a-f0-9]{24}", plan_id):
            raise HostError("PLAN_INVALID", "Invalid plan ID", 2)
        with self.lock():
            raw = self.read(f".research-local/hosts/plans/{plan_id}.json")
            if raw is None:
                raise HostError("PLAN_MISSING", "Generate a plan before applying", 2)
            plan = json.loads(raw)
            check = dict(plan)
            check.pop("plan_id", None)
            if digest(encoded(check))[:24] != plan_id:
                raise HostError("PLAN_INVALID", "Plan contents changed")
            host = plan["host"]
            self.profile(host)
            if plan["issues"]:
                raise HostError(
                    "USER_MODIFIED", "Plan has conflicts; preserve or relocate user files first"
                )
            receipt = self.load_receipt(host)
            if receipt.get("plan_id") == plan_id:
                result = self.verify(host)
                if result["filesystem"] != "verified":
                    raise HostError("USER_MODIFIED", "Installed files changed after apply")
                pending_path = f".research-local/hosts/{host}/pending.json"
                pending_raw = self.read(pending_path)
                if pending_raw and json.loads(pending_raw).get("plan_id") == plan_id:
                    self.path(pending_path).unlink()
                return self.result("noop", "This plan is already applied", plan_id=plan_id)
            snapshots, projection = self.sources(host)
            if snapshots != plan["sources"] or digest(encoded(receipt)) != plan["receipt_hash"]:
                raise HostError("PLAN_STALE", "Source or receipt changed; generate a new plan")
            journal_path = f".research-local/hosts/{host}/pending.json"
            journal_raw = self.read(journal_path)
            pending = json.loads(journal_raw) if journal_raw else None
            if pending and pending["plan_id"] != plan_id:
                raise HostError(
                    "INSTALL_PENDING", "Resume the pending plan before applying another"
                )
            for change in plan["changes"]:
                target = change["path"]
                if not target.startswith(TARGETS[host] + "/"):
                    raise HostError("PLAN_INVALID", "Unexpected install path")
                current = self.read(target)
                hashed = digest(current) if current is not None else None
                allowed = {change["before"]}
                if pending:
                    allowed.add(change["after"])
                if hashed not in allowed:
                    raise HostError("PLAN_STALE", f"Target changed: {target}")
            self.write(journal_path, encoded({"plan_id": plan_id}))
            for change in plan["changes"]:
                if change["after"] is None:
                    self.path(change["path"]).unlink(missing_ok=True)
                else:
                    data = projection[change["path"]]
                    if digest(data) != change["after"]:
                        raise HostError("PLAN_STALE", "Projection changed")
                    self.write(change["path"], data)
            self.write(
                self.receipt_path(host),
                encoded(
                    {
                        "host": host,
                        "plan_id": plan_id,
                        "sources": snapshots,
                        "files": plan["desired"],
                    }
                ),
            )
            self.path(journal_path).unlink(missing_ok=True)
            return self.result(
                "applied" if plan["changes"] else "noop",
                "Host plan completed",
                plan_id=plan_id,
                files=list(plan["desired"]),
            )

    def verify(self, host: str) -> dict[str, Any]:
        profile = self.profile(host)
        receipt = self.load_receipt(host)
        issues = []
        for target, expected in receipt.get("files", {}).items():
            if not target.startswith(TARGETS[host] + "/"):
                raise HostError("RECEIPT_INVALID", "Unexpected target in receipt")
            data = self.read(target)
            if data is None or digest(data) != expected:
                issues.append({"code": "TARGET_CHANGED", "path": target})
        filesystem = (
            "verified"
            if receipt.get("plan_id") and not issues
            else "not_installed"
            if not receipt.get("plan_id")
            else "conflict"
        )
        snapshots, projection = self.sources(host)
        return {
            "filesystem": filesystem,
            "source_current": snapshots == receipt.get("sources"),
            "discovery": "unknown",
            "invocation": "not_tested",
            "hooks": "disabled",
            "support_level": profile["support_level"],
            "issues": issues,
            "installed_files": len(receipt.get("files", {})),
            "available_files": len(projection),
        }

    def result(self, status: str, summary: str, **values: Any) -> dict[str, Any]:
        return {
            "protocol_version": "1",
            "status": status,
            "summary": summary,
            "artifact_refs": [],
            "issues": [],
            "next_actions": [],
            **values,
        }

    def execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        host = payload.get("host", "codex")
        if operation == "apply" or operation == "uninstall" and payload.get("plan_id"):
            return self.apply(payload.get("plan_id", ""))
        self.profile(host)
        if operation in {"inspect", "verify"}:
            return self.result(
                "ok", "Filesystem checks do not verify host discovery", **self.verify(host)
            )
        if operation in {"plan", "sync", "repair", "uninstall"}:
            action = "uninstall" if operation == "uninstall" else "install"
            plan = self.plan(host, action)
            # Planning is non-mutating unless caller explicitly requests a persisted executable plan.
            if payload.get("save", False):
                self.write(f".research-local/hosts/plans/{plan['plan_id']}.json", encoded(plan))
            return self.result(
                "blocked" if plan["issues"] else "planned",
                "Review plan before apply",
                plan=plan,
                plan_id=plan["plan_id"],
                issues=plan["issues"],
                next_actions=[
                    "apply saved plan" if payload.get("save") else "save plan with save=true"
                ],
            )
        raise HostError("OPERATION_UNSUPPORTED", f"Unknown host operation: {operation}", 2)
