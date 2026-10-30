"""Offline acceptance for project host installation and ownership protection."""

import json
from pathlib import Path

import pytest

from investment_ai import HostError, HostManager


@pytest.fixture
def manager(tmp_path: Path) -> HostManager:
    (tmp_path / "AGENTS.md").write_text("root")
    (tmp_path / "CODEBUDDY.md").write_text("root")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/rules.md").write_text("rules")
    skill = tmp_path / "ai/skills/example"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: example\n---\n[Rules](../../../docs/rules.md)\n")
    for host, target in [("codex", ".agents/skills"), ("codebuddy", ".codebuddy/skills")]:
        path = tmp_path / f"ai/adapters/{host}"
        path.mkdir(parents=True)
        (path / "profile.json").write_text(
            json.dumps(
                {
                    "host_id": host,
                    "target_directory": target,
                    "support_level": "experimental-filesystem-only",
                }
            )
        )
    return HostManager(tmp_path)


def install(manager: HostManager, host: str = "codex") -> dict:
    plan = manager.execute("plan", {"host": host, "save": True})
    return manager.execute("apply", {"plan_id": plan["plan_id"]})


def test_readonly_plan_and_idempotent_apply(manager: HostManager):
    before = {p.relative_to(manager.root) for p in manager.root.rglob("*")}
    manager.execute("plan", {})
    assert before == {p.relative_to(manager.root) for p in manager.root.rglob("*")}
    result = install(manager)
    assert result["status"] == "applied"
    assert manager.execute("apply", {"plan_id": result["plan_id"]})["status"] == "noop"
    verification = manager.execute("verify", {})
    assert verification["filesystem"] == "verified"
    assert verification["discovery"] == "unknown"
    assert verification["invocation"] == "not_tested"


def test_rewritten_links_resolve_from_installed_location(manager: HostManager):
    install(manager)
    target = manager.root / ".agents/skills/example/SKILL.md"
    text = target.read_text()
    link = text.split("](")[1].split(")")[0]
    assert (target.parent / link).resolve() == manager.root / "docs/rules.md"


def test_stale_source_plan_rejected(manager: HostManager):
    plan = manager.execute("plan", {"save": True})
    (manager.root / "ai/skills/example/SKILL.md").write_text("changed")
    with pytest.raises(HostError, match="Source or receipt changed"):
        manager.execute("apply", {"plan_id": plan["plan_id"]})


def test_target_created_after_plan_is_not_overwritten(manager: HostManager):
    plan = manager.execute("plan", {"save": True})
    target = manager.root / ".agents/skills/example/SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("user work")
    with pytest.raises(HostError, match="Target changed"):
        manager.execute("apply", {"plan_id": plan["plan_id"]})
    assert target.read_text() == "user work"


def test_user_edit_blocks_repair_and_uninstall(manager: HostManager):
    install(manager)
    target = manager.root / ".agents/skills/example/SKILL.md"
    target.write_text("user work")
    assert manager.execute("repair", {})["status"] == "blocked"
    plan = manager.execute("uninstall", {"save": True})
    with pytest.raises(HostError, match="conflicts"):
        manager.execute("uninstall", {"plan_id": plan["plan_id"]})
    assert target.read_text() == "user work"


def test_uninstall_preserves_unowned_files(manager: HostManager):
    install(manager)
    user = manager.root / ".agents/skills/user.txt"
    user.write_text("mine")
    plan = manager.execute("uninstall", {"save": True})
    manager.execute("uninstall", {"plan_id": plan["plan_id"]})
    assert not (manager.root / ".agents/skills/example/SKILL.md").exists()
    assert user.read_text() == "mine"


def test_source_upgrade_and_no_receipt_adoption(manager: HostManager):
    install(manager)
    source = manager.root / "ai/skills/example/SKILL.md"
    source.write_text(source.read_text() + "New instruction\n")
    assert manager.execute("verify", {})["source_current"] is False
    plan = manager.execute("sync", {"save": True})
    manager.execute("apply", {"plan_id": plan["plan_id"]})
    assert manager.execute("verify", {})["source_current"] is True
    (manager.root / ".research-local/hosts/codex/receipt.json").unlink()
    assert manager.execute("plan", {})["status"] == "blocked"


def test_symlink_target_is_rejected(manager: HostManager, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (manager.root / ".agents").symlink_to(outside, target_is_directory=True)
    with pytest.raises(HostError, match="Symlink"):
        manager.execute("plan", {})


def test_interrupted_apply_can_resume(manager: HostManager, monkeypatch):
    plan = manager.execute("plan", {"save": True})
    original = manager.write
    failed = False

    def interrupt(relative, data):
        nonlocal failed
        original(relative, data)
        if relative.startswith(".agents/") and not failed:
            failed = True
            raise RuntimeError("simulated interruption")

    monkeypatch.setattr(manager, "write", interrupt)
    with pytest.raises(RuntimeError):
        manager.execute("apply", {"plan_id": plan["plan_id"]})
    monkeypatch.setattr(manager, "write", original)
    manager.execute("apply", {"plan_id": plan["plan_id"]})
    assert manager.execute("verify", {})["filesystem"] == "verified"


def test_codebuddy_is_explicitly_unverified(manager: HostManager):
    install(manager, "codebuddy")
    result = manager.execute("verify", {"host": "codebuddy"})
    assert result["filesystem"] == "verified"
    assert result["support_level"] == "experimental-filesystem-only"
    assert result["discovery"] == "unknown"
